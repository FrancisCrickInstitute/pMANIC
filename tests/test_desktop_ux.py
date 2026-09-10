import os
import time

from PySide6.QtCore import QObject, QSettings, Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import QMessageBox

from manic.utils.recent_files import RecentFiles
from manic.utils.workers import ExportWorker

from conftest import _make_window


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


def test_recent_files_paths_from_single_str(qapp, tmp_path):
    settings = QSettings(str(tmp_path / "recent.ini"), QSettings.IniFormat)
    one = tmp_path / "one.txt"
    one.write_text("a")
    one_abs = os.path.abspath(str(one))
    settings.setValue("recent/compound_lists", one_abs)
    recent = RecentFiles("compound_lists", settings=settings)
    assert recent.paths() == [one_abs]


def test_export_worker_cancel_crosses_threads_and_quit_unblocks_wait(
    qapp, monkeypatch
):
    monkeypatch.setattr(
        "manic.utils.workers.ensure_corrections_for_export",
        lambda: None,
    )

    class BlockingExporter:
        def export_to_excel(
            self,
            path,
            progress_cb,
            use_legacy_integration=False,
            include_carbon_enrichment=False,
        ):
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                if progress_cb(1) is False:
                    return False
                time.sleep(0.005)
            return True

    class Canceller(QObject):
        canceled = Signal()

    thread = QThread()
    worker = ExportWorker(BlockingExporter(), os.path.join("tmp", "out.xlsx"))
    worker.moveToThread(thread)
    canceller = Canceller()
    canceller.canceled.connect(worker.cancel, Qt.DirectConnection)
    finished = []
    worker.finished.connect(finished.append, Qt.DirectConnection)
    worker.finished.connect(thread.quit, Qt.DirectConnection)
    thread.started.connect(worker.run)
    thread.start()
    canceller.canceled.emit()
    assert thread.wait(1000), "quit must reach the thread while the GUI thread blocks"
    assert finished == [False]


def test_load_cdf_folder_noop_when_cdf_already_loaded(
    qapp, empty_db, monkeypatch, tmp_path
):
    window = _make_window(monkeypatch)
    settings = QSettings(str(tmp_path / "recent.ini"), QSettings.IniFormat)
    window._recent_cdf = RecentFiles("cdf_folders", settings=settings)
    window.compound_data_loaded = True
    window.cdf_data_loaded = True
    window._update_menu_states()
    folder = tmp_path / "cdfs"
    folder.mkdir()
    try:
        window._load_cdf_folder(str(folder))
        assert window._thread is None
        assert window._recent_cdf.paths() == []
    finally:
        window.close()


# Every File-menu action that offers a shortcut, with the portable text it must
# bind. Qt maps "Ctrl" to Command on macOS and to Ctrl on Windows, so one
# portable string covers both platforms.
FILE_MENU_SHORTCUTS = {
    "load_compound_action": "Ctrl+O",
    "load_cdf_action": "Ctrl+Shift+O",
    "import_session_action": "Ctrl+I",
    "export_data_action": "Ctrl+E",
    "quit_action": "Ctrl+Q",
}

# Standard keys Qt does not bind on every platform. Quit and Preferences have
# no Windows row in the keyBindings table in qtbase/src/gui/kernel/
# qplatformtheme.cpp, so an action relying on one alone ships with no shortcut
# on Windows while looking correct on macOS and Linux.
PLATFORM_INCOMPLETE_STANDARD_KEYS = {
    "quit_action": QKeySequence.StandardKey.Quit,
    "settings_action": QKeySequence.StandardKey.Preferences,
}


def test_file_menu_actions_bind_their_expected_shortcuts(qapp, empty_db, monkeypatch):
    window = _make_window(monkeypatch)
    try:
        for attr, expected in FILE_MENU_SHORTCUTS.items():
            bound = {
                sequence.toString(QKeySequence.PortableText)
                for sequence in getattr(window, attr).shortcuts()
            }
            assert expected in bound, f"{attr} should bind {expected}, got {bound or 'nothing'}"
    finally:
        window.close()


def test_actions_using_platform_incomplete_standard_keys_have_a_literal_fallback(
    qapp, empty_db, monkeypatch
):
    """A bare standard key from the incomplete set would be empty on Windows.

    Asserting the resolved shortcut is non-empty cannot catch this, because the
    test platform resolves these keys fine. Instead require that the action
    binds more sequences than the standard key supplies on its own, which holds
    on every platform only when an explicit literal was added alongside it.
    """
    window = _make_window(monkeypatch)
    try:
        for attr, standard_key in PLATFORM_INCOMPLETE_STANDARD_KEYS.items():
            action = getattr(window, attr)
            from_standard_key = QKeySequence.keyBindings(standard_key)
            assert len(action.shortcuts()) > len(from_standard_key), (
                f"{attr} relies only on {standard_key}, which Qt leaves unbound "
                f"on Windows; pair it with an explicit literal sequence"
            )
    finally:
        window.close()
