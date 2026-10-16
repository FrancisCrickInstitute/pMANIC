"""Mass tolerance and peak-validation threshold are recorded and restored (#175)."""

import json
import threading
import zlib
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, Qt
from conftest import _make_window

from manic.io import eic_importer
from manic.io.changelog_writer import generate_changelog
from manic.models import session_export
from manic.models.analysis import AnalysisMode
from manic.models.database import get_connection
from manic.ui.main_window import MainWindow
from manic.validation.peak_verdict import PeakVerdict


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


def test_imported_threshold_never_plots_while_tolerance_regenerates(
    qapp, monkeypatch, tmp_path
):
    cdf = tmp_path / "sample.cdf"
    cdf.touch()
    x = zlib.compress(np.array([0.0, 1.0, 2.0]).tobytes())
    y = zlib.compress(np.array([[0.0, 3.0, 0.0], [0.0, 1.0, 0.0]]).tobytes())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES ('A', 1.0, 0.1, 0.1, 100.0, 1)"
        )
        conn.execute(
            "INSERT INTO samples (sample_name, file_name) VALUES ('S', ?)", (str(cdf),)
        )
        conn.execute(
            "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
            "VALUES ('S', 'A', ?, ?, 1.0)",
            (x, y),
        )
    method = tmp_path / "method.json"
    method.write_text(json.dumps({"mass_tolerance": 0.5, "min_peak_height_ratio": 0.02}))

    # Pause the real worker after it has deleted the sample's EIC rows.
    deleted, release = threading.Event(), threading.Event()

    def paused_reader(_path):
        deleted.set()
        assert release.wait(10)
        return object()

    monkeypatch.setattr(eic_importer, "read_cdf_file", paused_reader)
    monkeypatch.setattr(
        eic_importer,
        "_extract_all_eics_for_file",
        lambda *_args: ([("S", "A", x, y, 1.0)], 0),
    )

    window = _make_window(monkeypatch)
    titles = []
    window._create_message_box = lambda _kind, title, *_a: (
        titles.append(title) or SimpleNamespace(exec=lambda: 0)
    )
    window._peak_verdicts = lambda *_args: {"S": PeakVerdict.PASS}
    window.compound_data_loaded = window.cdf_data_loaded = True
    window.toolbar.update_sample_list(["S"])
    window.toolbar.update_compound_list(["A"])
    window.on_plot_button("A", ["S"])

    def eic_rows():
        with get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM eic").fetchone()[0]

    rows_at_plot = []
    plot = window.on_plot_button
    monkeypatch.setattr(
        window,
        "on_plot_button",
        lambda *args: (rows_at_plot.append(eic_rows()), plot(*args))[1],
    )
    start = window._on_mass_tolerance_changed
    done = threading.Event()

    def start_and_wait_for_delete(value):
        start(value)
        window._mass_tol_worker.finished.connect(
            lambda _count: done.set(), Qt.DirectConnection
        )
        assert deleted.wait(10)

    monkeypatch.setattr(window, "_on_mass_tolerance_changed", start_and_wait_for_delete)

    window._apply_imported_processing_settings(str(method))
    release.set()
    assert done.wait(10)
    # Deliver only the window's queued slots; a global processEvents() can touch
    # objects leaked by earlier tests.
    QCoreApplication.sendPostedEvents(window)
    thread = window._mass_tol_thread
    QCoreApplication.sendPostedEvents(thread)
    assert thread.wait(10_000)

    assert titles == ["Regeneration Complete"]
    assert rows_at_plot[-1] == 1
    assert 0 not in rows_at_plot
    assert (window.mass_tolerance, window.min_peak_height_ratio) == (0.5, 0.02)
    window.close()
