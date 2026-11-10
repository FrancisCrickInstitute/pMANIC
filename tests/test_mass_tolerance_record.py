"""Mass tolerance and peak-validation threshold are recorded and restored (#175)."""

import json

import pytest
from conftest import _make_window

from manic.io.changelog_writer import generate_changelog
from manic.models import session_export
from manic.models.analysis import AnalysisMode


def test_session_export_records_tolerance_and_threshold(tmp_path):
    assert session_export.export_session_method(
        str(tmp_path / "method"), mass_tolerance=0.5, min_peak_height_ratio=0.02
    )
    export_dir = tmp_path / "manic_session_export"
    data = json.loads((export_dir / "method.json").read_text(encoding="utf-8"))
    assert data["mass_tolerance"] == 0.5
    assert data["min_peak_height_ratio"] == 0.02

    changelog = next(export_dir.glob("changelog_*.md")).read_text(encoding="utf-8")
    assert "**Mass Tolerance:** 0.5 Da\n" in changelog
    assert "**Peak Validation Threshold:** 0.02\n" in changelog

    assert session_export.read_session_processing_settings(
        str(export_dir / "method.json")
    ) == session_export.SessionProcessingSettings(0.5, 0.02)


@pytest.mark.parametrize(
    "mass_tolerance, ratio",
    [("0.5", "x"), (-1, -0.1), (5.0, 2.0), (True, None), (float("nan"), [0.1])],
)
def test_out_of_range_session_values_are_ignored(tmp_path, mass_tolerance, ratio):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"mass_tolerance": mass_tolerance, "min_peak_height_ratio": ratio})
    )
    assert session_export.read_session_processing_settings(
        str(path)
    ) == session_export.SessionProcessingSettings(None, None)


def test_data_export_changelog_records_tolerance_and_threshold(tmp_path):
    generate_changelog(
        str(tmp_path / "export.xlsx"),
        internal_standard=None,
        use_legacy_integration=False,
        analysis_mode=AnalysisMode.LABELLED,
        mass_tolerance=0.5,
        min_peak_area_ratio=0.0,
    )
    changelog = next(tmp_path.glob("changelog_*.md")).read_text(encoding="utf-8")
    assert "- **Mass Tolerance:** 0.5 Da\n" in changelog
    assert "- **Peak Validation Threshold:** Off\n" in changelog


def _import(monkeypatch, window, session):
    calls = []
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(session), ""),
    )
    monkeypatch.setattr(
        "manic.ui.main_window.validate_method_file", lambda *a, **k: (True, "")
    )
    monkeypatch.setattr(
        "manic.ui.main_window.get_method_info",
        lambda _path: {"session_override_count": 1, "expected_sample_count": 1},
    )
    monkeypatch.setattr(
        "manic.ui.main_window.import_session_overrides", lambda *a, **k: (True, True)
    )
    monkeypatch.setattr(
        "manic.ui.main_window.reextract_session_eics",
        lambda tol: calls.append(("reextract", tol)) or [],
    )
    monkeypatch.setattr(window, "_confirm", lambda *a, **k: True)
    monkeypatch.setattr(
        window,
        "_on_mass_tolerance_changed",
        lambda tol: calls.append(("regenerate", tol)),
    )
    window.cdf_data_loaded = True
    window.import_session()
    return calls


def test_import_applies_session_tolerance_and_threshold(qapp, monkeypatch, tmp_path):
    session = tmp_path / "method.json"
    session.write_text(json.dumps({"mass_tolerance": 0.5, "min_peak_height_ratio": 0.02}))
    window = _make_window(monkeypatch)

    calls = _import(monkeypatch, window, session)

    # Re-extraction runs at the tolerance the stored EICs have, then the full regeneration
    # at the session's: a sample whose regeneration fails keeps EICs of one tolerance.
    assert calls == [("reextract", 0.2), ("regenerate", 0.5)]
    assert (window.mass_tolerance, window.min_peak_height_ratio) == (0.5, 0.02)
    window.close()


def test_import_of_older_session_keeps_current_settings(qapp, monkeypatch, tmp_path):
    session = tmp_path / "legacy.json"
    session.write_text(json.dumps({"compounds": [], "session_overrides": []}))
    window = _make_window(monkeypatch)
    before = (window.mass_tolerance, window.min_peak_height_ratio)

    calls = _import(monkeypatch, window, session)

    assert calls == [("reextract", before[0])]
    assert (window.mass_tolerance, window.min_peak_height_ratio) == before
    window.close()
