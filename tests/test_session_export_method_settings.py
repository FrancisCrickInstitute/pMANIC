"""Session export/import of per-compound analytical method settings.

Verifies that deconvolution settings (level, fit type, noise gate) and the
baseline-correction flag survive an export -> reset -> import round-trip, and
that importing an older method file that lacks these keys is backward
compatible (no crash, existing settings preserved).
"""

import json
import sqlite3
from pathlib import Path

import pytest

from manic.models import database
from manic.models import session_export


SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"


@pytest.fixture
def temp_method_db(tmp_path, monkeypatch):
    db_path = tmp_path / "method.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO compounds (compound_name, retention_time, mass0, label_atoms, "
        "baseline_correction, deconvolution_level, deconvolution_fit_type, "
        "deconvolution_noise_gate) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("Alanine", 2.5, 89.0, 3, 0, "6", "emg", "aggressive"),
    )
    conn.execute(
        "INSERT INTO samples (sample_name) VALUES (?)", ("S1",)
    )
    conn.commit()
    conn.close()
    return db_path, tmp_path


def _read_compound(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT baseline_correction, deconvolution_level, deconvolution_fit_type, "
        "deconvolution_noise_gate FROM compounds WHERE compound_name = 'Alanine'"
    ).fetchone()
    conn.close()
    return row


def test_session_export_includes_method_settings(temp_method_db):
    db_path, tmp_path = temp_method_db

    assert session_export.export_session_method(str(tmp_path / "method"))

    json_path = tmp_path / "manic_session_export" / "method.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    compound = data["compounds"][0]

    assert compound["deconvolution_level"] == "6"
    assert compound["deconvolution_fit_type"] == "emg"
    assert compound["deconvolution_noise_gate"] == "aggressive"
    assert compound["baseline_correction"] == 0


def test_session_import_restores_method_settings(temp_method_db):
    db_path, tmp_path = temp_method_db

    assert session_export.export_session_method(str(tmp_path / "method"))
    json_path = tmp_path / "manic_session_export" / "method.json"

    # Reset the compound's settings to defaults, simulating a fresh re-import.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE compounds SET baseline_correction = 1, deconvolution_level = '4', "
        "deconvolution_fit_type = 'auto', deconvolution_noise_gate = 'balanced' "
        "WHERE compound_name = 'Alanine'"
    )
    conn.commit()
    conn.close()

    ok, _ = session_export.import_session_overrides(str(json_path))
    assert ok

    row = _read_compound(db_path)
    assert row["deconvolution_level"] == "6"
    assert row["deconvolution_fit_type"] == "emg"
    assert row["deconvolution_noise_gate"] == "aggressive"
    assert row["baseline_correction"] == 0


def test_session_import_backward_compatible_without_settings(temp_method_db):
    db_path, tmp_path = temp_method_db

    # An older method file: compounds carry no deconvolution/baseline keys.
    legacy = {
        "compounds": [
            {
                "compound_name": "Alanine",
                "retention_time": 2.5,
                "loffset": 0.2,
                "roffset": 0.3,
                "mass0": 89.0,
                "label_atoms": 3,
                "deleted": 0,
            }
        ],
        "session_overrides": [],
        "deleted_samples": [],
    }
    legacy_path = tmp_path / "legacy_method.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")

    ok, _ = session_export.import_session_overrides(str(legacy_path))
    assert ok

    # Existing settings are preserved (not overwritten by defaults).
    row = _read_compound(db_path)
    assert row["deconvolution_level"] == "6"
    assert row["deconvolution_fit_type"] == "emg"
    assert row["deconvolution_noise_gate"] == "aggressive"
    assert row["baseline_correction"] == 0
