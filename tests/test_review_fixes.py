import sqlite3
import zlib
from pathlib import Path

import numpy as np
import pytest

from manic.io.compound_reader import Compound
from manic.models import database
from manic.processors.eic_calculator import EIC
from manic.io.data_provider import DataProvider
from manic.processors.eic_correction_manager import (
    _process_compound_batch_corrections,
    compute_corrected_intensity,
    ensure_corrections_for_export,
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


def test_batch_correction_skips_channel_shortfall_and_writes_valid_row(review_db):
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

    corrector = NaturalAbundanceCorrector()
    with database.get_connection() as conn:
        short_row = conn.execute(
            "SELECT formula, label_type, label_atoms, tbdms, meox, me "
            "FROM compounds WHERE compound_name = ?",
            ("Short",),
        ).fetchone()
        valid_row = conn.execute(
            "SELECT formula, label_type, label_atoms, tbdms, meox, me "
            "FROM compounds WHERE compound_name = ?",
            ("Valid",),
        ).fetchone()
        short_result = _process_compound_batch_corrections(
            "Short", short_row, corrector, conn
        )
        valid_result = _process_compound_batch_corrections(
            "Valid", valid_row, corrector, conn
        )
        short_corrected = conn.execute(
            "SELECT 1 FROM eic_corrected WHERE compound_name = ? AND sample_name = ?",
            ("Short", "S1"),
        ).fetchone()
        valid_corrected = conn.execute(
            "SELECT y_axis_corrected FROM eic_corrected "
            "WHERE compound_name = ? AND sample_name = ?",
            ("Valid", "S1"),
        ).fetchone()

    assert short_result["successful"] == 0
    assert short_corrected is None
    assert valid_result["successful"] == 1
    assert valid_corrected is not None
    stored = np.frombuffer(zlib.decompress(valid_corrected["y_axis_corrected"]), dtype=np.float64)
    assert stored.size == 10
    assert np.any(stored != np.arange(1, 11, dtype=np.float64))


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


def test_load_bulk_omits_labelled_without_corrected_keeps_unlabelled_raw(
    review_db,
):
    time = np.linspace(0.0, 1.0, 5)
    with database.get_connection() as conn:
        conn.execute("INSERT INTO samples (sample_name) VALUES ('S1')")
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms, formula, label_type, deconvolution_level) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("Labeled", 1.0, 0.2, 0.2, 100.0, 1, "C1", "C", "off"),
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


def test_ravelled_eic_matches_reshaped_time_series():
    matrix = np.array(
        [
            [100.0, 110.0, 120.0, 110.0, 100.0],
            [10.0, 11.0, 12.0, 11.0, 10.0],
        ],
        dtype=np.float64,
    )
    eic = EIC("X", "S1", np.linspace(0.0, 1.0, 5), matrix.ravel(), 1)
    compound = Compound(
        compound_name="X",
        retention_time=1.0,
        loffset=0.2,
        roffset=0.2,
        label_atoms=1,
        mass0=100.0,
        formula="C1",
        label_type="C",
    )
    got = compute_corrected_intensity(eic, compound)
    expected = NaturalAbundanceCorrector().correct_time_series(matrix, "C1", "C", 1)
    assert got is not None
    np.testing.assert_allclose(got, expected)


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
