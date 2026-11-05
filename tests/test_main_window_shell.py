from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from manic.io.compounds_import import CompoundRow, insert_compound
from manic.models.analysis import AnalysisMode
from manic.ui.settings_window import DeconvolutionPage

from conftest import _make_window


def test_title_start_panel_and_quiet_status_bar_before_data(qapp, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        assert window.windowTitle() == "MANIC — Labelled analysis"
        assert window.workspace.currentWidget() is window.start_panel
        # The canvas owns the next step; the status bar keeps only transient messages.
        status_text = [
            label.text()
            for label in window.statusBar().findChildren(QLabel)
            if label.isVisibleTo(window) and label.text()
        ]
        assert status_text == []
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


def test_drop_zone_lights_only_for_a_drop_the_window_takes(qapp, monkeypatch, tmp_path):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    loaded = []
    monkeypatch.setattr(window, "_load_compound_list_from", lambda p: loaded.append(p))
    monkeypatch.setattr(window, "_load_cdf_folder", lambda p: loaded.append(p))
    zone = window.start_panel.drop_zone

    def mime(path) -> QMimeData:
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(path))])
        return data

    def drag(path=None) -> bool:
        """Drag `path` over the window, or leave without one; True if the zone lights."""
        if path is None:
            QApplication.sendEvent(window, QDragLeaveEvent())
        else:
            data = mime(path)  # the event does not own it; keep it alive
            event = QDragEnterEvent(
                QPoint(10, 10), Qt.CopyAction, data, Qt.LeftButton, Qt.NoModifier
            )
            QApplication.sendEvent(window, event)
        return zone.property("dragOver") == "true"

    def drop(path) -> None:
        data = mime(path)
        # Qt delivers a drop only to a live drag's target, so call the handler it would.
        window.dropEvent(
            QDropEvent(QPointF(10, 10), Qt.CopyAction, data, Qt.LeftButton, Qt.NoModifier)
        )

    compounds = tmp_path / "compounds.CSV"
    compounds.write_text("x")
    notes = tmp_path / "notes.txt"
    notes.write_text("x")
    try:
        assert drag(compounds)
        assert not drag()
        assert not drag(notes)
        # A raw data folder is refused until a compound list is loaded, as in the File menu.
        assert not drag(tmp_path)
        for path in (compounds, notes, tmp_path):
            drop(path)
        assert loaded == [str(compounds)]

        window.compound_data_loaded = True
        window._update_menu_states()
        window._refresh_shell()
        assert window.start_panel.primary_button.text() == "Load raw data folder…"
        assert drag(tmp_path)
        assert not drag(compounds)
        for path in (compounds, tmp_path):
            drop(path)
        assert loaded == [str(compounds), str(tmp_path)]
    finally:
        window.close()


def test_deconvolution_status_opens_its_settings_page(qapp, monkeypatch):
    insert_compound(
        CompoundRow(
            compound_name="Pyruvate", retention_time=6.37, mass0=174.0, loffset=0.1,
            roffset=0.15, label_atoms=3, formula="C3H4O3", label_type="C", tbdms=1,
            meox=0, me=0, amount_in_std_mix=10.0, int_std_amount=1.5, mm_files="*MM*",
        )
    )
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        # Loading selects the first compound without the user picking it.
        window.toolbar.update_compound_list(["Pyruvate"], selected_name="Pyruvate")
        window.compound_data_loaded = True
        window._refresh_shell()

        status = window.deconvolution_indicator_label
        assert not status.isHidden()
        assert status.text() == (
            "Deconvolution level 4 · automatic peak shape · balanced noise gate"
        )

        status.click()
        settings = window.settings_window
        assert settings.isVisible()
        assert settings.page_list.currentItem().text() == "Deconvolution"
        page = settings.findChild(DeconvolutionPage)
        assert page.isVisible()
        assert page.compound_label.text() == "Compound: Pyruvate"
        assert page.level_combo.currentText() == (
            "Level 4 - default, high-resolution overlap splitting"
        )
    finally:
        if window.settings_window is not None:
            window.settings_window.close()
        window.close()


def _toast(window):
    from manic.ui.toast_notification import ToastNotification

    toasts = [t for t in window.statusBar().findChildren(ToastNotification) if t.isVisibleTo(window)]
    assert len(toasts) == 1
    return toasts[0]


def test_session_export_names_the_file_it_wrote_and_opens_its_folder(
    qapp, monkeypatch, tmp_path
):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    chosen = tmp_path / "labelled-session.json"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName", lambda *a, **k: (str(chosen), "")
    )
    opened, dialogs = [], []
    monkeypatch.setattr(
        "manic.ui.main_window.QDesktopServices.openUrl", lambda url: opened.append(url)
    )
    monkeypatch.setattr(QMessageBox, "exec", lambda box: dialogs.append(box.text()))
    try:
        window.show()
        window.export_method()
        assert dialogs == []
        written = tmp_path / "manic_session_export" / "labelled-session.json"
        assert written.is_file()
        toast = _toast(window)
        assert toast.findChild(QLabel, "toastLabel").text() == (
            "Exported labelled-session.json to manic_session_export"
        )
        toast.action_button.click()
        assert [url.toLocalFile() for url in opened] == [str(written.parent)]
    finally:
        window.close()
