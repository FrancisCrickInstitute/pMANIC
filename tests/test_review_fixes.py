import sqlite3
import zlib
from pathlib import Path

import numpy as np
import pytest

from manic.io.compound_reader import Compound
from manic.models import database
from manic.processors.eic_calculator import EIC
from manic.processors.eic_correction_manager import (
    _process_compound_batch_corrections,
    compute_corrected_intensity,
)
from manic.processors.natural_abundance_correction import (
    NaturalAbundanceCorrectionError,
    NaturalAbundanceCorrector,
)

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
    with pytest.raises(NaturalAbundanceCorrectionError, match="Cl"):
        NaturalAbundanceCorrector().build_correction_matrix("C1Cl1", "C", 1)


def test_label_atoms_exceeding_formula_raises():
    with pytest.raises(NaturalAbundanceCorrectionError, match="label_atoms"):
        NaturalAbundanceCorrector().build_correction_matrix("C3", "C", 6)


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
