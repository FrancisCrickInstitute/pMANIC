import sqlite3
import zlib
from pathlib import Path

import numpy as np
import pytest
from netCDF4 import Dataset

from manic.io.compound_reader import Compound
from manic.io.eic_importer import regenerate_all_eics_with_mass_tolerance
from manic.models import database
from manic.io.data_provider import DataProvider
from manic.processors.eic_correction_manager import (
    ensure_corrections_for_export,
    uncorrectable_reason,
)
from manic.processors.natural_abundance_correction import (
    NaturalAbundanceCorrectionError,
    NaturalAbundanceCorrector,
)
from manic.utils import workers

SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"


@pytest.fixture
def review_db(tmp_path, monkeypatch):
    db_path = tmp_path / "review_fixes.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    database.init_db()
    return db_path


def _blob(values: np.ndarray) -> bytes:
    return zlib.compress(np.asarray(values, dtype=np.float64).tobytes())


def _insert_labelled_eic(conn, *, sample, compound, formula, label_atoms, channels, n_times=5):
    time = np.linspace(0.0, 1.0, n_times)
    intensity = np.arange(1, channels * n_times + 1, dtype=np.float64)
    conn.execute("INSERT OR IGNORE INTO samples (sample_name) VALUES (?)", (sample,))
    conn.execute(
        "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
        "mass0, label_atoms, formula, label_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (compound, 1.0, 0.2, 0.2, 100.0, label_atoms, formula, "C"),
    )
    conn.execute(
        "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis) VALUES (?, ?, ?, ?)",
        (sample, compound, _blob(time), _blob(intensity)),
    )


def test_ensure_corrections_for_export_raises_naming_uncorrectable(review_db):
    with database.get_connection() as conn:
        _insert_labelled_eic(
            conn,
            sample="S1",
            compound="Short",
            formula="C3H6O3",
            label_atoms=3,
            channels=2,
        )
        _insert_labelled_eic(
            conn,
            sample="S1",
            compound="Valid",
            formula="C1",
            label_atoms=1,
            channels=2,
        )

    with pytest.raises(
        RuntimeError,
        match=(
            "Natural abundance correction failed for: Short. "
            "Fix the formula or label_atoms for these compounds, "
            "or delete them, then export again."
        ),
    ):
        ensure_corrections_for_export()


@pytest.mark.parametrize("formula", ["C1Se1", None])
@pytest.mark.parametrize("deconvolution_level", ["off", "4"])
def test_load_bulk_omits_labelled_when_correction_fails_keeps_unlabelled_raw(
    review_db, formula, deconvolution_level
):
    time = np.linspace(0.0, 1.0, 5)
    with database.get_connection() as conn:
        conn.execute("INSERT INTO samples (sample_name) VALUES ('S1')")
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms, formula, label_type, deconvolution_level) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("Labeled", 1.0, 0.2, 0.2, 100.0, 1, formula, "C", deconvolution_level),
        )
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms, formula, label_type, deconvolution_level) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("Unlabeled", 1.0, 0.2, 0.2, 200.0, 0, "C1", "C", "off"),
        )
        conn.execute(
            "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis) "
            "VALUES (?, ?, ?, ?)",
            ("S1", "Labeled", _blob(time), _blob(np.arange(1, 11, dtype=np.float64))),
        )
        conn.execute(
            "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis) "
            "VALUES (?, ?, ?, ?)",
            ("S1", "Unlabeled", _blob(time), _blob(np.arange(1, 6, dtype=np.float64))),
        )

    provider = DataProvider()
    corrected = provider.load_bulk_sample_data()
    raw = provider.get_sample_raw_data("S1")
    assert "Labeled" not in corrected["S1"]
    assert "Unlabeled" in corrected["S1"]
    assert corrected["S1"]["Unlabeled"] == raw["Unlabeled"]


def test_unknown_element_raises():
    with pytest.raises(NaturalAbundanceCorrectionError, match="Fe"):
        NaturalAbundanceCorrector().build_correction_matrix("C1Fe1", "C", 1)


def test_label_atoms_exceeding_formula_raises():
    with pytest.raises(NaturalAbundanceCorrectionError, match="label_atoms"):
        NaturalAbundanceCorrector().build_correction_matrix("C3", "C", 6)


def test_derivatisation_carbons_do_not_pad_the_label_budget():
    corrector = NaturalAbundanceCorrector()
    with pytest.raises(NaturalAbundanceCorrectionError, match="label_atoms=6"):
        corrector._get_cached_correction_matrix("C3H6O3", "C", 6, tbdms=2, meox=0, me=0)


def test_unknown_element_survives_derivatisation():
    corrector = NaturalAbundanceCorrector()
    with pytest.raises(NaturalAbundanceCorrectionError, match="Se"):
        corrector._get_cached_correction_matrix("C3Se1", "C", 3, tbdms=1, meox=0, me=0)


@pytest.mark.parametrize("formula", ["C6H11FO5", "C6H4I2NO", "C6H5NaO7", "C10H16N5O13P3"])
def test_monoisotopic_elements_do_not_block_correction(formula):
    """F, I, Na and P cannot change the isotope pattern, so they must not raise.

    The unknown-element guard exists to catch elements whose distribution would
    be silently dropped. A single stable isotope contributes a delta function,
    so refusing these would block a correct compound list, and because
    ensure_corrections_for_export refuses the whole workbook that would make
    the export impossible.
    """
    NaturalAbundanceCorrector()._get_cached_correction_matrix(
        formula, "C", 2, tbdms=0, meox=0, me=0
    )


def test_monoisotopic_element_leaves_the_matrix_unchanged():
    corrector = NaturalAbundanceCorrector()
    without = corrector.build_correction_matrix("C6H12O6", "C", 6)
    with_fluorine = corrector.build_correction_matrix("C6H12O6F1", "C", 6)
    np.testing.assert_array_equal(
        without,
        with_fluorine,
        err_msg="19F is 100% abundant, so convolving with it is the identity",
    )


def test_c1_correction_matrix_columns():
    matrix = NaturalAbundanceCorrector().build_correction_matrix("C1", "C", 1)
    np.testing.assert_allclose(matrix[:, 0], [0.9893, 0.0107], atol=5e-5)
    np.testing.assert_allclose(matrix[:, 1], [0.01, 0.99], atol=5e-5)


def test_existing_database_gains_eic_index(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    schema_text = SCHEMA.read_text(encoding="utf-8")
    schema_text = schema_text.replace(
        "CREATE INDEX IF NOT EXISTS idx_eic_compound_sample\n"
        "          ON eic(compound_name, sample_name);\n\n",
        "",
    )
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_text)
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        assert "idx_eic_compound_sample" not in names

    database.init_db()

    with sqlite3.connect(db_path) as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    assert "idx_eic_compound_sample" in names


def test_regeneration_worker_uses_the_session_mass_tolerance(monkeypatch):
    seen = {}

    def fake_regenerate(**kwargs):
        seen.update(kwargs)
        return 1

    monkeypatch.setattr(workers, "regenerate_compound_eics", fake_regenerate)
    worker = workers.EicRegenerationWorker("Glucose", 0.2, ["s1"], 7.1, mass_tol=0.15)
    worker.run()
    assert seen["mass_tol"] == 0.15


def _write_cdf_with_corrupt_scan_index(path):
    with Dataset(path, "w") as cdf:
        cdf.createDimension("scan_number", 3)
        cdf.createDimension("point_number", 6)
        variables = {
            "scan_acquisition_time": ("scan_number", [294.0, 300.0, 306.0]),
            "scan_index": ("scan_number", [0, 4, 2]),
            "point_count": ("scan_number", [2, 2, 2]),
            "total_intensity": ("scan_number", [20.0, 20.0, 20.0]),
            "mass_values": ("point_number", [100.0] * 6),
            "intensity_values": ("point_number", [10.0] * 6),
        }
        for name, (dimension, values) in variables.items():
            cdf.createVariable(name, np.asarray(values).dtype, (dimension,))[:] = values


@pytest.mark.parametrize(
    "write_cdf",
    [
        lambda path: path.write_bytes(b"corrupted CDF"),
        _write_cdf_with_corrupt_scan_index,
    ],
    ids=["unreadable-file", "corrupt-scan-index"],
)
def test_mass_tolerance_reload_keeps_eics_of_an_unreadable_cdf(
    review_db, tmp_path, write_cdf
):
    cdf_path = tmp_path / "s1.cdf"
    write_cdf(cdf_path)
    x_axis = _blob(np.array([4.9, 5.0, 5.1]))
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, mass0, label_atoms) "
            "VALUES ('Glucose', 5.0, 100.0, 0)"
        )
        conn.execute(
            "INSERT INTO samples (sample_name, file_name) VALUES ('s1', ?)",
            (str(cdf_path),),
        )
        conn.execute(
            "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
            "VALUES ('s1', 'Glucose', ?, ?, 0.2)",
            (x_axis, _blob(np.array([1.0, 10.0, 1.0]))),
        )

    result = regenerate_all_eics_with_mass_tolerance(0.15)

    with database.get_connection() as conn:
        rows = conn.execute("SELECT x_axis FROM eic WHERE sample_name = 's1'").fetchall()
    assert [row["x_axis"] for row in rows] == [x_axis]
    assert result == (0, ["s1"])


def test_bulk_load_cancel_stops_pulling_and_closes_the_task_stream(
    review_db, monkeypatch
):
    """A cancel must abandon the remaining tasks, not drain the whole queue.

    Closing the map generator is what cancels the not-yet-started futures on a
    real executor, so the fake here asserts both halves: the loop stops pulling
    at the first refusal, and the stream is closed on the way out.
    """
    time = np.linspace(0.0, 1.0, 5)
    intensity = np.arange(1, 6, dtype=np.float64)
    task_count = 40
    with database.get_connection() as conn:
        conn.execute("INSERT INTO samples (sample_name) VALUES ('S1')")
        for index in range(task_count):
            name = f"C{index:02d}"
            conn.execute(
                "INSERT INTO compounds (compound_name, retention_time, loffset, "
                "roffset, mass0, label_atoms, formula, label_type, "
                "deconvolution_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, 1.0, 0.2, 0.2, 100.0, 0, "C1", "C", "off"),
            )
            conn.execute(
                "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis) "
                "VALUES (?, ?, ?, ?)",
                ("S1", name, _blob(time), _blob(intensity)),
            )

    pulled: list = []
    closed: list = []

    class LazyExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def map(self, worker, tasks):
            def stream():
                try:
                    for task in tasks:
                        pulled.append(task)
                        yield worker(task)
                finally:
                    closed.append(True)

            return stream()

    monkeypatch.setattr(
        "manic.io.data_provider.ThreadPoolExecutor", LazyExecutor
    )

    class Cancelled(Exception):
        pass

    def refuse(_value):
        raise Cancelled()

    provider = DataProvider()
    with pytest.raises(Cancelled):
        provider.load_bulk_sample_data(progress_callback=refuse)

    assert closed == [True], "the task stream must be closed so pending work is cancelled"
    assert len(pulled) == 25, (
        f"expected the loop to stop at the first refused progress tick, "
        f"pulled {len(pulled)} of {task_count}"
    )


@pytest.mark.parametrize(
    "formula, label_atoms, expected",
    [("C1", 1, None), (None, 0, None), (None, 1, "no formula"), ("C1Se1", 1, "Se")],
)
def test_uncorrectable_reason_names_why_no_corrected_area_exists(
    formula, label_atoms, expected
):
    compound = Compound(
        compound_name="X", retention_time=1.0, loffset=0.2, roffset=0.2,
        label_atoms=label_atoms, mass0=100.0, formula=formula, label_type="C",
    )
    reason = uncorrectable_reason(compound)
    assert reason is None if expected is None else expected in reason


def test_ill_conditioned_correction_matrix_is_refused():
    corrector = NaturalAbundanceCorrector()
    with pytest.raises(NaturalAbundanceCorrectionError, match="ill-conditioned"):
        corrector._get_cached_correction_matrix("C2000", "C", 10, 0, 0, 0)
    compound = Compound(
        compound_name="Giant", retention_time=1.0, loffset=0.2, roffset=0.2,
        label_atoms=10, mass0=100.0, formula="C2000", label_type="C",
    )
    reason = uncorrectable_reason(compound)
    assert reason is not None and "ill-conditioned" in reason


def test_ensure_corrections_for_export_refuses_bad_formula_without_eic_corrected(review_db):
    with database.get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "eic_corrected" not in tables
        _insert_labelled_eic(
            conn,
            sample="S1",
            compound="BadElem",
            formula="C1Se1",
            label_atoms=1,
            channels=2,
        )
        _insert_labelled_eic(
            conn,
            sample="S1",
            compound="NoFormula",
            formula=None,
            label_atoms=1,
            channels=2,
        )

    with pytest.raises(RuntimeError, match="BadElem.*Se.*NoFormula.*no formula"):
        ensure_corrections_for_export()


def test_display_bars_show_no_corrected_ratios_when_correction_fails(qapp, review_db):
    from manic.io.eic_reader import EIC
    from manic.processors.display_deconvolution import apply_display_correction
    from manic.ui.isotopologue_ratio_widget import IsotopologueRatioWidget

    compound = Compound(
        compound_name="Seleno", retention_time=1.0, loffset=0.2, roffset=0.2,
        label_atoms=1, mass0=100.0, formula="C1Se1", label_type="C",
    )
    assert apply_display_correction(
        [100.0, 10.0], compound, use_corrected=True, is_multi_trace=True
    ) == []
    assert apply_display_correction(
        [100.0, 10.0], compound, use_corrected=False, is_multi_trace=True
    ) == [100.0, 10.0]

    with database.get_connection() as conn:
        _insert_labelled_eic(
            conn,
            sample="S1",
            compound="Seleno",
            formula="C1Se1",
            label_atoms=1,
            channels=2,
        )

    widget = IsotopologueRatioWidget()
    widget.use_corrected = True
    eic = EIC(
        "S1",
        "Seleno",
        np.linspace(0.0, 1.0, 5),
        np.array([[100.0] * 5, [10.0] * 5], dtype=np.float64),
    )
    widget.update_ratios("Seleno", [eic], raw_areas_by_sample={"S1": [100.0, 10.0]})
    assert widget._current_ratios is None
    assert widget.get_last_total_abundances()[0] is None
    widget.close()


def test_in_memory_provider_raises_on_uncorrectable_compound():
    from manic.io.in_memory_provider import InMemoryDataProvider

    provider = InMemoryDataProvider(
        compounds=[
            {
                "compound_name": "Seleno",
                "retention_time": 1.0,
                "mass0": 100.0,
                "loffset": 0.1,
                "roffset": 0.1,
                "label_atoms": 1,
                "formula": "C1Se1",
                "label_type": "C",
                "tbdms": 0,
                "meox": 0,
                "me": 0,
            }
        ],
        samples=["S1"],
        raw_data={"S1": {"Seleno": [100.0, 10.0]}},
    )
    with pytest.raises(NaturalAbundanceCorrectionError, match="Seleno"):
        provider.get_sample_corrected_data("S1")


def test_graph_header_names_uncorrectable_internal_standard(qapp, review_db):
    from manic.ui.graphs import GraphView

    with database.get_connection() as conn:
        _insert_labelled_eic(
            conn,
            sample="S1",
            compound="Target",
            formula="C1",
            label_atoms=1,
            channels=2,
        )
        _insert_labelled_eic(
            conn,
            sample="S1",
            compound="BadIS",
            formula=None,
            label_atoms=1,
            channels=2,
        )

    view = GraphView()
    try:
        view.set_internal_standard("BadIS")
        view.plot_compound("Target", ["S1"])
        assert "BadIS" in view.qc_note.text()
        assert "no formula" in view.qc_note.text()

        view.set_internal_standard(None)
        assert view.qc_note.text() == ""

        view.set_internal_standard("BadIS")
        assert "BadIS" in view.qc_note.text()

        view.clear_all_plots()
        assert view.qc_note.text() == ""
        assert view._uncorrectable is None
        assert view._internal_standard_uncorrectable is None
    finally:
        view.deleteLater()
