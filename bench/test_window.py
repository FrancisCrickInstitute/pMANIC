"""Window-level actions a user waits on: startup, sessions, regeneration, layout, dialogs.

Every stage drives the real MainWindow on the offscreen platform. Modal message
boxes, questions, and file pickers are replaced with stubs that answer at once,
so the timing covers the application work and none of the waiting for a click.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from test_plot import _assert_grid, _clear_fit_caches, _make_window

from manic.io.list_compound_names import list_compound_names
from manic.io.sample_reader import list_active_samples
from manic.models import database
from manic.ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parents[1]
WAIT_TIMEOUT_MS = 120_000


class _Box:
    """Stands in for a QMessageBox: records its title and answers Yes."""

    def __init__(self, log, title):
        self._log = log
        self._title = title

    def exec(self):
        self._log.append(self._title)
        return QMessageBox.Yes

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


@pytest.fixture
def boxes(monkeypatch):
    log: list[str] = []
    monkeypatch.setattr(
        MainWindow,
        "_create_message_box",
        lambda self, msg_type, title, *args, **kwargs: _Box(log, title),
    )
    monkeypatch.setattr(
        MainWindow,
        "_show_question_dialog",
        lambda self, title, *args, **kwargs: _Box(log, title).exec(),
    )
    return log


def _wait_for_box(qapp, boxes: list[str], title: str, failure: str) -> None:
    """Run the event loop until a background job posts its completion box."""
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: (title in boxes or failure in boxes) and loop.quit())
    timer.start()
    QTimer.singleShot(WAIT_TIMEOUT_MS, loop.quit)
    loop.exec()
    timer.stop()
    assert failure not in boxes, boxes
    assert title in boxes, f"timed out waiting for {title!r}: {boxes}"


def _fresh_db(db: Path, tmp_path: Path, rounds: list) -> Path:
    path = tmp_path / f"round-{len(rounds)}.db"
    shutil.copyfile(db, path)
    database.DB_FILE = path
    return path


def _plotted_window(case, qapp):
    _clear_fit_caches()
    window, names, samples = _make_window(case, qapp)
    window.compound_data_loaded = True
    window.cdf_data_loaded = True
    window.toolbar.compound_list.setCurrentRow(0)
    qapp.processEvents()
    _assert_grid(window, case, names[0])
    return window, names, samples


def _close_all(qapp, windows) -> None:
    for window in windows:
        window._skip_close_guard = True
        window.close()
    qapp.processEvents()


@pytest.fixture
def restore_db(db):
    yield
    database.DB_FILE = db


_STARTUP = """
import sys, time
from pathlib import Path
import manic.main as entry
from manic.models import database
from manic.models.analysis import AnalysisMode
import manic.ui.analysis_mode_dialog as mode_dialog
from manic.ui.main_window import MainWindow
from PySide6.QtWidgets import QApplication

database.DB_FILE = Path(sys.argv[1])
mode_dialog.choose_analysis_mode = lambda parent=None: AnalysisMode(sys.argv[2])
MainWindow._check_for_updates = lambda self: None

def shown(app):
    app.processEvents()
    windows = [w for w in app.topLevelWidgets() if isinstance(w, MainWindow) and w.isVisible()]
    print(f"shown {len(windows)} {windows[0].analysis_mode.value}", flush=True)
    return 0

QApplication.exec = shown
sys.exit(entry.main())
"""


def test_startup(case, benchmark, repeat, tmp_path):
    """Cold start in a new interpreter, from spawn until the main window is shown."""
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "HOME": str(tmp_path),
    }
    children = []

    def start():
        child = subprocess.Popen(
            [sys.executable, "-c", _STARTUP, str(tmp_path / "startup.db"), case.mode.value],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        children.append(child)
        return child.stdout.readline()

    line = benchmark.pedantic(start, rounds=repeat)
    for child in children:
        assert child.wait(timeout=60) == 0
    assert line.split() == ["shown", "1", case.mode.value]


def test_session_roundtrip(case, db, qapp, boxes, benchmark, repeat, tmp_path, monkeypatch, restore_db):
    """Export the session from one window, then import it into a freshly opened one."""
    windows = []
    rounds = []
    chosen = str(tmp_path / "session.json")
    written = str(tmp_path / "manic_session_export" / "session.json")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (chosen, ""))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (written, ""))

    def setup():
        _fresh_db(db, tmp_path, rounds)
        source, _names, _samples = _plotted_window(case, qapp)
        target, _names, _samples = _plotted_window(case, qapp)
        windows.extend([source, target])
        rounds.append(target)
        boxes.clear()
        return (source, target), {}

    def roundtrip(source, target):
        source.export_method()
        target.import_session()
        qapp.processEvents()

    try:
        benchmark.pedantic(roundtrip, setup=setup, rounds=repeat)
        assert boxes == [
            "Session Export Successful",
            "Import Session Overrides",
            "Session Import Successful",
        ], boxes
        _assert_grid(rounds[-1], case, list_compound_names()[0])
    finally:
        _close_all(qapp, windows)


def test_regenerate(case, db, qapp, boxes, benchmark, repeat, tmp_path, restore_db):
    """Widen the tR window for one compound, then change the mass tolerance for all."""
    windows = []
    rounds = []

    def setup():
        _fresh_db(db, tmp_path, rounds)
        window, _names, _samples = _plotted_window(case, qapp)
        windows.append(window)
        rounds.append(window)
        boxes.clear()
        tr_window = float(window.toolbar.integration.tr_window_edit.text().split(" - ")[0])
        return (window, tr_window + 0.1, window.mass_tolerance + 0.05), {}

    def regenerate(window, tr_window, mass_tol):
        window.toolbar.integration.tr_window_edit.setText(f"{tr_window:.3f}")
        window.toolbar.integration.regenerate_button.click()
        _wait_for_box(qapp, boxes, "Regeneration Complete", "Regeneration Failed")
        boxes.clear()
        window.apply_mass_tolerance(mass_tol)
        _wait_for_box(qapp, boxes, "Regeneration Complete", "Regeneration Failed")

    try:
        benchmark.pedantic(regenerate, setup=setup, rounds=repeat)
        window = rounds[-1]
        _assert_grid(window, case, list_compound_names()[0])
        with sqlite3.connect(database.DB_FILE) as conn:
            regenerated = conn.execute(
                "SELECT COUNT(*) FROM eic WHERE deleted = 0"
            ).fetchone()[0]
        assert regenerated == case.n_samples * case.n_compounds
    finally:
        _close_all(qapp, windows)


def test_resize(case, db, qapp, benchmark, repeat):
    """Shrink, then enlarge, the window with a full tile grid."""
    windows = []

    def setup():
        window, _names, _samples = _plotted_window(case, qapp)
        windows.append(window)
        return (window,), {}

    def resize(window):
        window.resize(1100, 700)
        qapp.processEvents()
        window.resize(1920, 1080)
        qapp.processEvents()

    try:
        benchmark.pedantic(resize, setup=setup, rounds=repeat)
        window = windows[-1]
        assert window.size().width() == 1920
        _assert_grid(window, case, list_compound_names()[0])
    finally:
        _close_all(qapp, windows)


def test_select_samples(case, db, qapp, benchmark, repeat):
    """Focus a subset of samples, then select all of them again."""
    windows = []
    focused = []

    def setup():
        window, _names, samples = _plotted_window(case, qapp)
        windows.append(window)
        return (window, samples[: len(samples) // 3]), {}

    def select(window, subset):
        window.focus_on_samples(subset)
        qapp.processEvents()
        focused.append(len(window.graph_view._current_plots))
        window.show_all_samples()
        qapp.processEvents()

    try:
        benchmark.pedantic(select, setup=setup, rounds=repeat)
        assert focused == [case.n_samples // 3] * repeat
        _assert_grid(windows[-1], case, list_compound_names()[0])
    finally:
        _close_all(qapp, windows)


def test_detailed_plot(case, db, qapp, benchmark, repeat, monkeypatch):
    """Open the EIC, TIC, and MS dialog for one tile."""
    # Imported after the QApplication exists, as the app does; matplotlib's Qt
    # backend refuses to load on a display-less machine before that.
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    windows = []
    dialogs = []

    def show(dialog):
        dialog.show()
        qapp.processEvents()
        dialogs.append(dialog)
        return 0

    monkeypatch.setattr(DetailedPlotDialog, "exec", show)

    def setup():
        window, names, samples = _plotted_window(case, qapp)
        windows.append(window)
        return (window, names[0], samples[0]), {}

    def open_dialog(window, compound, sample):
        window.graph_view._show_detailed_view(compound, sample)

    try:
        benchmark.pedantic(open_dialog, setup=setup, rounds=repeat)
        assert len(dialogs) == repeat
        for dialog in dialogs:
            assert dialog.eic_data is not None
            assert dialog.tic_data is not None
            assert dialog.ms_data is not None
    finally:
        for dialog in dialogs:
            dialog.close()
        _close_all(qapp, windows)


def test_clear_session(case, db, qapp, boxes, benchmark, repeat, tmp_path, restore_db):
    """Clear a loaded session, then start a new one in the same mode."""
    windows = []
    rounds = []

    def setup():
        _fresh_db(db, tmp_path, rounds)
        window, _names, _samples = _plotted_window(case, qapp)
        windows.append(window)
        rounds.append(window)
        boxes.clear()
        return (window,), {}

    def clear(window):
        window.clear_session()
        window.new_analysis_session(preset_mode=case.mode)
        qapp.processEvents()

    try:
        benchmark.pedantic(clear, setup=setup, rounds=repeat)
        assert boxes == ["Clear Session", "Session Cleared"], boxes
        fresh = QApplication.instance()._manic_main_window
        assert fresh not in windows and fresh.isVisible()
        windows.append(fresh)
        assert fresh.analysis_mode is case.mode
        assert list_active_samples() == [] and list_compound_names() == []
    finally:
        _close_all(qapp, windows)
