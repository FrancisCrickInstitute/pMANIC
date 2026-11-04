from types import SimpleNamespace

from PySide6.QtCore import QMimeData, QUrl

from manic.models.analysis import AnalysisMode

from conftest import _make_window


def _drop(path) -> SimpleNamespace:
    data = QMimeData()
    data.setUrls([QUrl.fromLocalFile(str(path))])
    return SimpleNamespace(mimeData=lambda: data)


def test_title_start_panel_and_status_before_data(qapp, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        assert window.windowTitle() == "MANIC — Labelled analysis"
        assert window.workspace.currentWidget() is window.start_panel
        assert window.selection_status_label.text() == (
            "No data loaded. Start by loading a compound list."
        )
        assert window.deconvolution_indicator_label.isHidden()
    finally:
        window.close()


def test_view_menu_mirrors_display_checkboxes(qapp, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        actions = {a.text(): a for a in window.view_menu.actions()}
        shared = actions["Shared y-scale"]
        checkbox = window.toolbar.shared_yscale_checkbox

        shared.trigger()
        assert checkbox.isChecked() and shared.isChecked()
        checkbox.setChecked(False)
        assert not shared.isChecked()

        peak_box = window.toolbar.selected_peak_yscale_checkbox
        peak_box.setEnabled(False)
        actions["Scale to selected peak"].trigger()
        assert not peak_box.isChecked()
        assert not actions["Scale to selected peak"].isChecked()
    finally:
        window.close()


def test_drop_accepts_only_what_can_be_loaded_now(qapp, monkeypatch, tmp_path):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    compounds = tmp_path / "compounds.CSV"
    compounds.write_text("x")
    notes = tmp_path / "notes.txt"
    notes.write_text("x")
    try:
        assert window._dropped_path(_drop(compounds)) == compounds
        assert window._dropped_path(_drop(notes)) is None
        # Raw data needs a compound list first, as in the File menu.
        assert window._dropped_path(_drop(tmp_path)) is None
        window.compound_data_loaded = True
        window._update_menu_states()
        assert window._dropped_path(_drop(tmp_path)) == tmp_path
        assert window._dropped_path(_drop(compounds)) is None
        assert window.start_panel.compounds_step.done_label.isVisibleTo(
            window.start_panel
        )
    finally:
        window.close()
