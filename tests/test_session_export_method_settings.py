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
from manic.ui.main_window import MainWindow


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


def _exported_method(tmp_path, **export_kwargs):
    assert session_export.export_session_method(str(tmp_path / "method"), **export_kwargs)
    json_path = tmp_path / "manic_session_export" / "method.json"
    return json_path, json.loads(json_path.read_text(encoding="utf-8"))


def test_session_export_writes_internal_standard(temp_method_db):
    _, tmp_path = temp_method_db
    _, data = _exported_method(
        tmp_path,
        internal_standard="Alanine",
        internal_standard_reference_isotope=2,
    )
    assert data["internal_standard"] == "Alanine"
    assert data["internal_standard_reference_isotope"] == 2
    changelog = next(
        (tmp_path / "manic_session_export").glob("changelog_*.md")
    ).read_text(encoding="utf-8")
    assert "**Internal Standard:** Alanine" in changelog
    assert "**Internal Standard Reference Peak:** M+2" in changelog


def test_session_export_writes_null_standard_by_default(temp_method_db):
    _, tmp_path = temp_method_db
    json_path, data = _exported_method(tmp_path)
    assert data["internal_standard"] is None
    assert data["internal_standard_reference_isotope"] == 0
    changelog = next(json_path.parent.glob("changelog_*.md")).read_text(encoding="utf-8")
    assert "None selected" in changelog


def test_session_export_writes_internal_standard_in_unlabelled_mode(temp_method_db):
    _, tmp_path = temp_method_db
    _, data = _exported_method(
        tmp_path,
        analysis_mode="unlabelled",
        internal_standard="Alanine",
    )
    assert data["analysis_mode"] == "unlabelled"
    assert data["internal_standard"] == "Alanine"
    assert data["internal_standard_reference_isotope"] == 0


def test_read_session_internal_standard_round_trip(temp_method_db):
    _, tmp_path = temp_method_db
    json_path, _ = _exported_method(
        tmp_path,
        internal_standard="Alanine",
        internal_standard_reference_isotope=1,
    )
    parsed = session_export.read_session_internal_standard(str(json_path))
    assert parsed is not None
    assert parsed.compound_name == "Alanine"
    assert parsed.reference_isotope == 1


def test_read_session_internal_standard_absent_key(tmp_path):
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(
        json.dumps({"compounds": [], "session_overrides": []}),
        encoding="utf-8",
    )
    assert session_export.read_session_internal_standard(str(legacy_path)) is None


def test_read_session_internal_standard_unreadable_file_returns_none(tmp_path):
    missing = tmp_path / "missing.json"
    assert session_export.read_session_internal_standard(str(missing)) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    assert session_export.read_session_internal_standard(str(bad)) is None
    listed = tmp_path / "list.json"
    listed.write_text("[]", encoding="utf-8")
    assert session_export.read_session_internal_standard(str(listed)) is None


def test_read_session_internal_standard_explicit_null_clears(tmp_path):
    path = tmp_path / "cleared.json"
    path.write_text(
        json.dumps({"internal_standard": None, "internal_standard_reference_isotope": 3}),
        encoding="utf-8",
    )
    parsed = session_export.read_session_internal_standard(str(path))
    assert parsed is not None
    assert parsed.compound_name is None
    assert parsed.reference_isotope == 0


def test_resolve_session_internal_standard_skips_missing_key():
    assert session_export.resolve_session_internal_standard(None, ["Alanine"]) is None


def test_resolve_session_internal_standard_clears_deleted_name():
    parsed = session_export.SessionInternalStandard("scyllo-Ins", 2)
    resolved = session_export.resolve_session_internal_standard(parsed, ["Alanine"])
    assert resolved is not None
    assert resolved.compound_name is None
    assert resolved.reference_isotope == 0


def test_resolve_session_internal_standard_keeps_active_name():
    parsed = session_export.SessionInternalStandard("Alanine", 2)
    resolved = session_export.resolve_session_internal_standard(parsed, ["Alanine"])
    assert resolved == parsed


def test_clamp_reference_isotope_rejects_out_of_range():
    assert session_export.clamp_reference_isotope(2, 4) == 2
    assert session_export.clamp_reference_isotope(0, 4) == 0
    assert session_export.clamp_reference_isotope(3, 4) == 3
    assert session_export.clamp_reference_isotope(99, 4) == 0
    assert session_export.clamp_reference_isotope(-1, 4) == 0
    assert session_export.clamp_reference_isotope(1, 0) == 0


def test_import_session_overrides_still_returns_two_tuple(temp_method_db):
    _, tmp_path = temp_method_db
    json_path, _ = _exported_method(tmp_path, internal_standard="Alanine")
    result = session_export.import_session_overrides(str(json_path))
    assert isinstance(result, tuple)
    assert len(result) == 2
    ok, has_deletion_data = result
    assert ok is True
    assert has_deletion_data is True


class _FakeStandard:
    def __init__(self):
        self.internal_standard = "keep-me"

    def set_internal_standard(self, name):
        self.internal_standard = name

    def clear_internal_standard(self):
        self.internal_standard = None


class _FakeToolbar:
    def __init__(self):
        self.standard = _FakeStandard()


class _FakeWindow:
    def __init__(self):
        self.toolbar = _FakeToolbar()
        self.internal_standard_reference_isotope = 7
        self._validation_provider = None
        self.menu_updated = False

    def _update_menu_states(self):
        self.menu_updated = True


def test_apply_imported_standard_restores_name_and_isotope(temp_method_db):
    _, tmp_path = temp_method_db
    json_path, _ = _exported_method(
        tmp_path,
        internal_standard="Alanine",
        internal_standard_reference_isotope=2,
    )
    host = _FakeWindow()
    MainWindow._apply_imported_internal_standard(host, str(json_path))
    assert host.toolbar.standard.internal_standard == "Alanine"
    assert host.internal_standard_reference_isotope == 2
    assert host.menu_updated is True


def test_apply_imported_standard_leaves_toolbar_when_key_absent(tmp_path):
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(
        json.dumps({"compounds": [], "session_overrides": []}),
        encoding="utf-8",
    )
    host = _FakeWindow()
    MainWindow._apply_imported_internal_standard(host, str(legacy_path))
    assert host.toolbar.standard.internal_standard == "keep-me"
    assert host.internal_standard_reference_isotope == 7
    assert host.menu_updated is False


def test_apply_imported_standard_clears_on_explicit_null(temp_method_db):
    _, tmp_path = temp_method_db
    path = tmp_path / "cleared.json"
    path.write_text(
        json.dumps({"internal_standard": None, "internal_standard_reference_isotope": 3}),
        encoding="utf-8",
    )
    host = _FakeWindow()
    MainWindow._apply_imported_internal_standard(host, str(path))
    assert host.toolbar.standard.internal_standard is None
    assert host.internal_standard_reference_isotope == 0
    assert host.menu_updated is True


def test_apply_imported_standard_clamps_out_of_range_isotope(temp_method_db):
    _, tmp_path = temp_method_db
    json_path, _ = _exported_method(
        tmp_path,
        internal_standard="Alanine",
        internal_standard_reference_isotope=99,
    )
    host = _FakeWindow()
    MainWindow._apply_imported_internal_standard(host, str(json_path))
    assert host.toolbar.standard.internal_standard == "Alanine"
    assert host.internal_standard_reference_isotope == 0
    assert host.menu_updated is True


def test_apply_imported_standard_leaves_toolbar_when_restore_fails(
    temp_method_db, monkeypatch
):
    _, tmp_path = temp_method_db
    json_path, _ = _exported_method(tmp_path, internal_standard="Alanine")

    def _boom(_name):
        raise LookupError("compound missing")

    monkeypatch.setattr("manic.ui.main_window.read_compound", _boom)
    host = _FakeWindow()
    MainWindow._apply_imported_internal_standard(host, str(json_path))
    assert host.toolbar.standard.internal_standard == "keep-me"
    assert host.internal_standard_reference_isotope == 7
    assert host.menu_updated is False


def test_apply_imported_standard_clears_deleted_name(temp_method_db):
    _, tmp_path = temp_method_db
    path = tmp_path / "deleted_is.json"
    path.write_text(
        json.dumps(
            {
                "internal_standard": "scyllo-Ins",
                "internal_standard_reference_isotope": 2,
            }
        ),
        encoding="utf-8",
    )
    host = _FakeWindow()
    MainWindow._apply_imported_internal_standard(host, str(path))
    assert host.toolbar.standard.internal_standard is None
    assert host.internal_standard_reference_isotope == 0
    assert host.menu_updated is True
