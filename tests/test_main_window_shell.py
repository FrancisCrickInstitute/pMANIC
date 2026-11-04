from types import SimpleNamespace

from PySide6.QtCore import QEvent, QMimeData, QPoint, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent
from PySide6.QtWidgets import QApplication

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
        shared = actions["Shared Y-Scale"]
        checkbox = window.toolbar.shared_yscale_checkbox

        shared.trigger()
        assert checkbox.isChecked() and shared.isChecked()
        checkbox.setChecked(False)
        assert not shared.isChecked()

        peak_box = window.toolbar.selected_peak_yscale_checkbox
        peak_box.setEnabled(False)
        actions["Scale to Selected Peak"].trigger()
        assert not peak_box.isChecked()
        assert not actions["Scale to Selected Peak"].isChecked()
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
        window._refresh_shell()
        assert window.start_panel.primary_button.text() == "Load raw data folder…"
    finally:
        window.close()


def test_drop_zone_lights_only_for_a_drop_the_window_takes(qapp, monkeypatch, tmp_path):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    zone = window.start_panel.drop_zone

    def drag(kind, path=None):
        if kind == QEvent.Type.DragLeave:
            event = QDragLeaveEvent()
        else:
            data = _drop(path).mimeData()  # the event does not own it; keep it alive
            event = QDragEnterEvent(
                QPoint(10, 10),
                Qt.DropAction.CopyAction,
                data,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        QApplication.sendEvent(window, event)
        return zone.property("dragOver") == "true"

    compounds = tmp_path / "compounds.csv"
    compounds.write_text("x")
    try:
        assert drag(QEvent.Type.DragEnter, compounds)
        assert not drag(QEvent.Type.DragLeave)
        # A raw data folder is refused until a compound list is loaded.
        assert not drag(QEvent.Type.DragEnter, tmp_path)
    finally:
        window.close()
