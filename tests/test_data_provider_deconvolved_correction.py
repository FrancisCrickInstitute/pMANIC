import sqlite3
import zlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from manic.io import data_provider
from manic.io.data_provider import DataProvider
from manic.models import database


SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "deconvolved_correction.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    yield conn
    conn.close()


def _blob(values: np.ndarray) -> bytes:
    return zlib.compress(np.asarray(values, dtype=np.float64).tobytes())


def test_corrected_export_uses_deconvolved_raw_component(temp_db, monkeypatch):
    time = np.array([0, 1, 2, 3, 4], dtype=np.float64)
    raw = np.vstack(
        [
            [0, 20, 20, 0, 0],
            [0, 8, 8, 0, 0],
        ]
    )
    stored_full_trace_correction = np.vstack(
        [
            [100, 100, 100, 100, 100],
            [50, 50, 50, 50, 50],
        ]
    )
    selected_component = np.vstack(
        [
            [0, 10, 10, 0, 0],
            [0, 4, 4, 0, 0],
        ]
    )
    selected_mask = np.tile(np.array([False, True, True, True, False]), (2, 1))

    temp_db.execute("INSERT INTO samples (sample_name) VALUES ('S1')")
    temp_db.execute(
        "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
        "mass0, label_atoms, formula, label_type, baseline_correction, "
        "deconvolution_level, deconvolution_fit_type, deconvolution_noise_gate) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("Urea", 2.0, 2.0, 2.0, 189.0, 1, "C1", "C", 0, "4", "auto", "balanced"),
    )
    temp_db.execute(
        "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis) VALUES (?, ?, ?, ?)",
        ("S1", "Urea", _blob(time), _blob(raw.ravel())),
    )
    temp_db.execute(
        "INSERT INTO eic_corrected "
        "(sample_name, compound_name, x_axis, y_axis_corrected, correction_applied, deleted) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("S1", "Urea", _blob(time), _blob(stored_full_trace_correction.ravel()), 1, 0),
    )
    temp_db.commit()

    deconvolution_calls = []

    def fake_deconvolve(*args, **kwargs):
        deconvolution_calls.append((args, kwargs))
        return SimpleNamespace(
            selected=selected_component,
                selected_mask=selected_mask,
            model=None,
        )

    monkeypatch.setattr(data_provider, "deconvolve_eic", fake_deconvolve)

    class IdentityCorrector:
        def correct_time_series(self, matrix, *args, **kwargs):
            return np.asarray(matrix, dtype=np.float64)

    monkeypatch.setattr(data_provider, "NaturalAbundanceCorrector", IdentityCorrector)

    provider = DataProvider()
    corrected = provider.load_bulk_sample_data()["S1"]["Urea"]
    raw_export = provider.get_sample_raw_data("S1")["Urea"]

    # Strict integration boundaries include times 1, 2, 3. The selected
    # component integrates to 15 and 6; the stored corrected full trace would
    # have integrated to 200 and 100 under the old ordering.
    assert corrected == pytest.approx([15.0, 6.0])
    assert raw_export == pytest.approx([15.0, 6.0])
    assert len(deconvolution_calls) == 1


def test_model_path_raw_and_corrected_differ_only_by_correction():
    """Raw and corrected model-path areas use one shared integration route."""
    grid_left, grid_right = 1.0, 3.0

    class FakeModel:
        integration_left = grid_left
        integration_right = grid_right

        def evaluate_selected(self, grid):
            grid = np.asarray(grid, dtype=np.float64)
            base = np.exp(-((grid - 2.0) ** 2) / 0.2)
            return np.vstack([10.0 * base, 4.0 * base])

    selected_mask = np.tile(np.array([False, True, True, True, False]), (2, 1))
    deconvolved = SimpleNamespace(
        selected=np.zeros((2, 5)),
        selected_mask=selected_mask,
        model=FakeModel(),
    )
    row = {
        "label_atoms": 1,
        "retention_time": 2.0,
        "loffset": 1.0,
        "roffset": 1.0,
        "formula": "C1",
        "label_type": "C",
        "tbdms": 0,
        "meox": 0,
        "me": 0,
    }

    provider = DataProvider()
    # Identity correction: raw and corrected must be bit-for-bit identical
    # because they now flow through the same integration routine.
    provider._correct_time_series = lambda matrix, r: np.asarray(
        matrix, dtype=np.float64
    )
    raw_areas, corrected_areas = provider._areas_from_deconvolved(
        np.array([0, 1, 2, 3, 4], dtype=np.float64),
        deconvolved,
        row,
        use_legacy=False,
        baseline_correction=False,
    )
    assert raw_areas == pytest.approx(corrected_areas)

    # A pure channel-wise scaling correction scales the integrated areas by the
    # same factor, proving correction is the only thing that differs.
    provider._correct_time_series = lambda matrix, r: np.asarray(
        matrix, dtype=np.float64
    ) * np.array([[0.5], [2.0]])
    raw_areas2, corrected_areas2 = provider._areas_from_deconvolved(
        np.array([0, 1, 2, 3, 4], dtype=np.float64),
        deconvolved,
        row,
        use_legacy=False,
        baseline_correction=False,
    )
    assert raw_areas2 == pytest.approx(raw_areas)
    assert corrected_areas2[0] == pytest.approx(raw_areas2[0] * 0.5)
    assert corrected_areas2[1] == pytest.approx(raw_areas2[1] * 2.0)
