"""Mass tolerance and peak-validation threshold are recorded and restored (#175)."""

import json
from types import SimpleNamespace

import pytest

from manic.io.changelog_writer import generate_changelog
from manic.models import session_export
from manic.models.analysis import AnalysisMode
from manic.ui.main_window import MainWindow


def _recording_window():
    calls = []
    window = SimpleNamespace(
        apply_mass_tolerance=lambda value: calls.append(("mass_tolerance", value)),
        apply_min_peak_area_ratio=lambda value: calls.append(("ratio", value)),
    )
    return window, calls


def test_session_round_trip_restores_tolerance_and_threshold(tmp_path):
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

    window, calls = _recording_window()
    MainWindow._apply_imported_processing_settings(window, str(export_dir / "method.json"))
    assert calls == [("mass_tolerance", 0.5), ("ratio", 0.02)]


def test_legacy_session_without_keys_leaves_settings_unchanged(tmp_path):
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({"compounds": [], "session_overrides": []}))
    window, calls = _recording_window()
    MainWindow._apply_imported_processing_settings(window, str(legacy))
    assert calls == []


@pytest.mark.parametrize(
    "mass_tolerance, ratio",
    [("0.5", "x"), (-1, -0.1), (5.0, 2.0), (True, None), (float("nan"), [0.1])],
)
def test_out_of_range_session_values_are_ignored(tmp_path, mass_tolerance, ratio):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"mass_tolerance": mass_tolerance, "min_peak_height_ratio": ratio})
    )
    window, calls = _recording_window()
    MainWindow._apply_imported_processing_settings(window, str(path))
    assert calls == []


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
