import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QAction, QDragEnterEvent, QDragLeaveEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from manic.io.compounds_import import CompoundRow, insert_compound
from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.processors.tile_y_scale import YScalePolicy
from manic.ui.main_window import SIDEBAR_OPEN_SETTING, SUMMARY_OPEN_SETTING
from manic.ui.plot_tile import LARGE_TILE, TILE_GAP
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


def test_view_menu_scale_choice_is_exclusive_and_remembered(qapp, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        actions = {a.text(): a for a in window.view_menu.actions()}
        shared, peak = actions["Shared Y-Scale"], actions["Scale to Selected Peak"]
        assert shared.shortcut() == QKeySequence("Ctrl+Shift+Y")
        assert peak.shortcut() == QKeySequence("Ctrl+Shift+P")

        peak.trigger()
        shared.trigger()
        assert shared.isChecked() and not peak.isChecked()
        assert window.graph_view._y_scale_policy is YScalePolicy.SHARED_EXTRACT
    finally:
        window.close()

    again = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        actions = {a.text(): a for a in again.view_menu.actions()}
        assert actions["Shared Y-Scale"].isChecked()
        assert again.graph_view._y_scale_policy is YScalePolicy.SHARED_EXTRACT
    finally:
        again.close()


@pytest.mark.parametrize("mode", [AnalysisMode.LABELLED, AnalysisMode.UNLABELLED])
def test_header_y_scale_toggles_and_the_view_menu_follow_each_other(qapp, monkeypatch, mode):
    window = _make_window(monkeypatch, mode)
    view = window.graph_view
    shared, peak = view.shared_y_button, view.peak_scale_button
    actions = {a.text(): a for a in window.view_menu.actions()}
    try:
        window.show()
        assert shared.isVisibleTo(view)
        key = QKeySequence("Ctrl+Shift+Y").toString(QKeySequence.SequenceFormat.NativeText)
        assert f"Shared Y-Scale ({key})" in shared.toolTip()

        shared.click()
        assert view._y_scale_policy is YScalePolicy.SHARED_EXTRACT
        assert actions["Shared Y-Scale"].isChecked()
        actions["Shared Y-Scale"].trigger()
        assert view._y_scale_policy is YScalePolicy.PER_TILE_EXTRACT
        assert not shared.isChecked()

        assert peak.isVisibleTo(view) == (mode is AnalysisMode.LABELLED)
        if mode is AnalysisMode.LABELLED:
            actions["Scale to Selected Peak"].trigger()
            assert peak.isChecked() and not shared.isChecked()
            assert view._y_scale_policy is YScalePolicy.PER_TILE_SELECTED_PEAK
            shared.click()
            assert not actions["Scale to Selected Peak"].isChecked()
            assert view._y_scale_policy is YScalePolicy.SHARED_EXTRACT
    finally:
        window.close()


def _grid_window(monkeypatch, width: int):
    """A shown window at ``width`` whose workspace shows the plot grid."""
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    window.resize(width, 800)
    window.show()
    QApplication.processEvents()
    window.cdf_data_loaded = True
    window._refresh_shell()
    QApplication.processEvents()
    return window


def test_summary_opens_from_the_view_menu_or_the_grid_header_and_is_remembered(qapp, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    window.resize(1400, 800)
    window.show()
    QApplication.processEvents()
    action, button = window.show_summary_action, window.graph_view.summary_button
    try:
        # Nothing to summarise before the grid shows.
        assert window.summary.isHidden()
        window.cdf_data_loaded = True
        window._refresh_shell()
        assert window.summary.isVisible() and action.isChecked() and button.isChecked()

        button.click()
        assert window.summary.isHidden() and not action.isChecked()
        assert QSettings().value(SUMMARY_OPEN_SETTING, type=bool) is False
        action.trigger()
        assert window.summary.isVisible() and button.isChecked()

        # Dragged 60 px wider, as the splitter handle does.
        sidebar, workspace, _ = window.splitter.sizes()
        window.splitter.moveSplitter(sidebar + workspace + window.splitter.handleWidth() - 60, 2)
        width = window.summary.width()
        assert width > 300
    finally:
        window.close()

    again = _grid_window(monkeypatch, 1400)
    try:
        assert again.summary.isVisible() and again.summary.width() == width
        again.show_summary_action.trigger()
    finally:
        again.close()
    closed = _grid_window(monkeypatch, 1400)
    try:
        assert closed.summary.isHidden() and not closed.graph_view.summary_button.isChecked()
    finally:
        closed.close()


def test_sidebar_hides_from_the_view_menu_or_the_grid_header_and_keeps_its_width(qapp, monkeypatch):
    window = _grid_window(monkeypatch, 1400)
    action, button = window.show_sidebar_action, window.graph_view.sidebar_button
    try:
        assert action.shortcut() == QKeySequence("Ctrl+Alt+S")
        assert window.show_summary_action.shortcut() == QKeySequence("Ctrl+Alt+R")
        shortcuts = [
            key.toString()
            for a in window.findChildren(QAction)
            for key in a.shortcuts()
            if not key.isEmpty()
        ]
        assert len(shortcuts) == len(set(shortcuts))
        assert window.toolbar.isVisible() and button.isChecked()
        window.splitter.moveSplitter(340, 1)
        grid = window.graph_view.width()

        button.click()
        QApplication.processEvents()
        assert window.toolbar.isHidden() and not action.isChecked()
        assert window.graph_view.width() > grid
        assert QSettings().value(SIDEBAR_OPEN_SETTING, type=bool) is False
        # Finding a compound needs the list, so it brings the sidebar back.
        window.find_compound_action.trigger()
        assert window.toolbar.isVisible() and button.isChecked()
        assert window.toolbar.width() == 340

        action.trigger()
    finally:
        window.close()
    again = _grid_window(monkeypatch, 1400)
    try:
        assert again.toolbar.isHidden() and not again.graph_view.sidebar_button.isChecked()
        again.show_sidebar_action.trigger()
        assert again.toolbar.width() == 340
    finally:
        again.close()


def test_a_narrow_window_starts_with_the_summary_closed_and_keeps_two_columns(qapp, monkeypatch):
    window = _grid_window(monkeypatch, 1024)
    try:
        assert window.summary.isHidden() and not window.show_summary_action.isChecked()
        window.show_summary_action.trigger()
        QApplication.processEvents()
        assert window.summary.isVisible()
        two_columns = 2 * LARGE_TILE[0] + TILE_GAP
        assert window.graph_view._grid_viewport()[0] >= two_columns
        # Short of room, the header keeps every control whole, on a second row if need be.
        view = window.graph_view
        for button in (view.shared_y_button, view.peak_scale_button, view.summary_button):
            corner = button.mapTo(view, button.rect().bottomRight())
            assert button.isVisible() and 0 < corner.x() < view.width()
        assert window.toolbar.width() >= window.toolbar.minimumSizeHint().width()
    finally:
        window.close()
    # Opening it in a narrow window was a choice; the next one keeps it.
    again = _grid_window(monkeypatch, 1024)
    try:
        assert again.summary.isVisible()
    finally:
        again.close()


def test_the_summary_closes_rather_than_cut_the_sidebar_or_widen_the_window(qapp, monkeypatch):
    window = _grid_window(monkeypatch, 1024)
    toolbar = window.toolbar
    toolbar.loaded_data.update_status(True, True)
    edit = toolbar.integration.tr_window_edit
    try:
        window.show_summary_action.trigger()
        QApplication.processEvents()
        # All three fit at 1024: the sidebar keeps its content width, nothing is cut.
        assert window.summary.isVisible() and window.width() == 1024
        title = toolbar.loaded_data.compounds_row._title
        assert title.width() >= title.fontMetrics().horizontalAdvance("Compound list")
        assert edit.fontMetrics().horizontalAdvance("0.125") + 16 <= edit.width()

        window.show_sidebar_action.trigger()
        window.resize(820, 800)
        QApplication.processEvents()
        window.show_sidebar_action.trigger()
        QApplication.processEvents()
        assert toolbar.isVisible() and window.width() == 820
        assert window.summary.isHidden() and not window.show_summary_action.isChecked()
        assert QSettings().value(SUMMARY_OPEN_SETTING, type=bool) is True
    finally:
        window.close()
    # The saved choice waits for a window with room; a narrower one opens without it.
    narrow = _grid_window(monkeypatch, 900)
    try:
        assert narrow.summary.isHidden() and not narrow.show_summary_action.isChecked()
        narrow.show_summary_action.trigger()
        assert narrow.summary.isVisible()
    finally:
        narrow.close()


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
        assert page.level_combo.currentText() == "Level 4 (default)"
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


def test_finished_data_export_reports_in_a_toast_not_a_dialog(qapp, monkeypatch, tmp_path):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    dialogs = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: dialogs.append(box.text()))
    try:
        window.show()
        # The export worker reports back through _export_finished.
        window._export_path = str(tmp_path / "manic_data_export.xlsx")
        window._export_finished(True)
        toast = _toast(window)
        assert toast.findChild(QLabel, "toastLabel").text() == "Exported manic_data_export.xlsx"
        assert toast.action_button.text() == "Show in Folder"
        assert dialogs == []
    finally:
        window.close()


def test_long_session_name_toast_stays_inside_the_window(qapp, monkeypatch, tmp_path):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    chosen = tmp_path / f"{'labelled-pyruvate-lactate-review-' * 3}final.json"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName", lambda *a, **k: (str(chosen), "")
    )
    try:
        window.resize(1008, 633)
        window.show()
        window.export_method()
        QApplication.processEvents()
        bar = window.statusBar()
        toast = _toast(window)
        assert bar.rect().contains(toast.geometry())
        for button in (toast.action_button, toast.findChild(QPushButton, "toastCloseButton")):
            assert button.isVisible() and toast.rect().contains(button.geometry())
        label = toast.findChild(QLabel, "toastLabel")
        written = tmp_path / "manic_session_export" / chosen.name
        assert "…" in label.text() and label.text().endswith("manic_session_export")
        assert label.toolTip() == str(written)
    finally:
        window.close()


def test_destructive_confirmations_default_to_cancel(qapp, monkeypatch, tmp_path):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    session = tmp_path / "week3.json"
    asked = []

    def decline(box):
        asked.append(
            (
                box.text(),
                [button.text() for button in box.buttons()],
                box.defaultButton().text(),
                box.informativeText(),
            )
        )
        return QMessageBox.Cancel

    monkeypatch.setattr(QMessageBox, "exec", decline)
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName", lambda *a, **k: (str(session), "")
    )
    monkeypatch.setattr("manic.ui.main_window.validate_method_file", lambda *a, **k: (True, ""))
    monkeypatch.setattr(
        "manic.ui.main_window.get_method_info",
        lambda _path: {"session_override_count": 4, "expected_sample_count": 30},
    )
    monkeypatch.setattr(
        "manic.ui.main_window.import_session_overrides",
        lambda *a, **k: pytest.fail("imported after Cancel"),
    )
    monkeypatch.setattr(
        "manic.ui.integration_window_widget.SessionActivityService.restore_samples_to_defaults",
        lambda *a, **k: pytest.fail("reset after Cancel"),
    )
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES ('Alanine', 1.0, 0.1, 0.1, 217.0, 0)"
        )
    try:
        window.clear_session()
        window.import_session()
        window.toolbar.integration.populate_fields_from_plots("Alanine", ["S2"], ["S1", "S2"])
        window.toolbar.integration.restore_button.click()
        (clear, clear_buttons, clear_default, _), (text, buttons, default, info), reset = asked
        assert sorted(clear_buttons) == ["Cancel", "Clear Session"] and clear_default == "Cancel"
        assert text == "Import week3.json?"
        assert sorted(buttons) == ["Cancel", "Import Overrides"] and default == "Cancel"
        assert "?" not in info
        assert (reset[0], sorted(reset[1]), reset[2]) == (
            "Reset S2 to the compound's default peak window?",
            ["Cancel", "Reset Peak Window"],
            "Cancel",
        )
    finally:
        window.close()


def test_import_session_says_what_it_needs_while_disabled(qapp, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        action = window.import_session_action
        assert not action.isEnabled()
        assert action.toolTip() == "Load the session's compound list and raw data first"
        window.compound_data_loaded = window.cdf_data_loaded = True
        window._update_menu_states()
        # Cleared, a menu shows no tooltip (toolTip() then falls back to the action's text).
        assert action.isEnabled() and action.toolTip() == "Import Session"
    finally:
        window.close()


def test_successful_session_import_reports_in_a_toast(qapp, monkeypatch, tmp_path):
    from manic.models.session_export import InternalStandardRestore, InternalStandardRestoreKind

    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    session = tmp_path / "week3.json"
    dialogs = []

    def answer(box):
        dialogs.append(box.text())
        importing = [b for b in box.buttons() if b.text() == "Import Overrides"]
        if importing:
            importing[0].click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", answer)
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName", lambda *a, **k: (str(session), "")
    )
    monkeypatch.setattr("manic.ui.main_window.validate_method_file", lambda *a, **k: (True, ""))
    monkeypatch.setattr(
        "manic.ui.main_window.get_method_info",
        lambda _path: {"session_override_count": 4, "expected_sample_count": 30},
    )
    monkeypatch.setattr(
        "manic.ui.main_window.import_session_overrides", lambda *a, **k: (True, True)
    )
    monkeypatch.setattr(
        window,
        "_apply_imported_internal_standard",
        lambda _path: InternalStandardRestore(InternalStandardRestoreKind.RESTORED, "Pyruvate", 1),
    )
    monkeypatch.setattr(window, "_refresh_after_session_import", lambda: None)
    try:
        window.show()
        window.import_session()
        assert dialogs == ["Import week3.json?"]
        label = _toast(window).findChild(QLabel, "toastLabel")
        assert label.full_text() == "Imported week3.json · Internal standard: Pyruvate (M+1)"
    finally:
        window.close()
