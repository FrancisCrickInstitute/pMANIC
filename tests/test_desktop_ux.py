import os

from PySide6.QtCore import QSettings
from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import QMessageBox

from manic.utils.recent_files import RecentFiles
from manic.utils.workers import ExportWorker

from conftest import _make_window


def test_file_action_shortcuts(qapp, empty_db, monkeypatch):
    window = _make_window(monkeypatch)
    try:
        assert window.quit_action.shortcut() == QKeySequence(QKeySequence.Quit)
        assert window.load_compound_action.shortcut() == QKeySequence(QKeySequence.Open)
        assert window.load_cdf_action.shortcut() == QKeySequence("Ctrl+Shift+O")
        assert window.export_data_action.shortcut() == QKeySequence("Ctrl+E")
        assert window.import_session_action.shortcut() == QKeySequence("Ctrl+I")
    finally:
        window.close()


def test_close_event_ignores_loaded_session_when_declined(
    qapp, empty_db, monkeypatch
):
    window = _make_window(monkeypatch)
    window._skip_close_guard = False
    window.cdf_data_loaded = True
    monkeypatch.setattr(
        window, "_show_question_dialog", lambda *args, **kwargs: QMessageBox.No
    )
    try:
        event = QCloseEvent()
        window.closeEvent(event)
        assert not event.isAccepted()
    finally:
        window._skip_close_guard = True
        window.close()


def test_close_event_accepts_loaded_session_when_confirmed(
    qapp, empty_db, monkeypatch
):
    window = _make_window(monkeypatch)
    window._skip_close_guard = False
    window.cdf_data_loaded = True
    monkeypatch.setattr(
        window, "_show_question_dialog", lambda *args, **kwargs: QMessageBox.Yes
    )
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()


def test_close_event_accepts_empty_session_without_asking(
    qapp, empty_db, monkeypatch
):
    window = _make_window(monkeypatch)
    window._skip_close_guard = False

    def boom(*args, **kwargs):
        raise AssertionError("close guard asked on an empty session")

    monkeypatch.setattr(window, "_show_question_dialog", boom)
    try:
        event = QCloseEvent()
        window.closeEvent(event)
        assert event.isAccepted()
    finally:
        window.close()


def test_recent_files_dedup_limit_and_drops_missing(qapp, tmp_path):
    settings = QSettings(str(tmp_path / "recent.ini"), QSettings.IniFormat)
    recent = RecentFiles("compound_lists", limit=2, settings=settings)
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    third = tmp_path / "third.txt"
    first.write_text("a")
    second.write_text("b")
    third.write_text("c")
    recent.add(str(first))
    recent.add(str(second))
    recent.add(str(first))
    first_abs = os.path.abspath(str(first))
    second_abs = os.path.abspath(str(second))
    third_abs = os.path.abspath(str(third))
    assert recent.paths() == [first_abs, second_abs]
    assert settings.value("recent/compound_lists") == [first_abs, second_abs]
    recent.add(str(third))
    assert recent.paths() == [third_abs, first_abs]
    first.unlink()
    assert recent.paths() == [third_abs]


def test_export_worker_cancel_makes_callback_false_and_emits_finished(
    qapp, monkeypatch
):
    monkeypatch.setattr(
        "manic.utils.workers.ensure_corrections_for_export",
        lambda: None,
    )
    recorded = []

    class StubExporter:
        def export_to_excel(
            self,
            path,
            progress_cb,
            use_legacy_integration=False,
            include_carbon_enrichment=False,
        ):
            recorded.append(progress_cb(50))
            return True

    worker = ExportWorker(StubExporter(), str(os.path.join("tmp", "out.xlsx")))
    finished = []
    worker.finished.connect(finished.append)
    worker.cancel()
    worker.run()
    assert recorded == [False]
    assert finished == [True]
