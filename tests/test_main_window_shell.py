import pytest
from PySide6.QtWidgets import QLabel, QMessageBox

from manic.models import database
from manic.models.analysis import AnalysisMode

from conftest import _make_window


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
        # The label cuts a message short where the platform's font is wider.
        assert toast.findChild(QLabel, "toastLabel").full_text() == (
            "Exported labelled-session.json to manic_session_export"
        )
        toast.action_button.click()
        assert [url.toLocalFile() for url in opened] == [str(written.parent)]
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


def test_sample_list_opened_from_the_menu_is_remembered_and_shown_checked(qapp, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    assert not window.show_samples_action.isChecked()
    window.show_samples_action.trigger()
    assert window.toolbar.samples_section.is_expanded()
    window.close()

    reopened = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        assert reopened.toolbar.samples_section.is_expanded()
        assert reopened.show_samples_action.isChecked()
    finally:
        reopened.close()
