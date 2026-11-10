import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QSettings
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from manic.models import database
from manic.models.analysis import AnalysisContext, AnalysisMode
from manic.ui.main_window import MainWindow

SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def empty_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    with database.get_connection() as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return db_path


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path):
    """Every QSettings() starts empty, in an INI file under the test's tmp_path."""
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "settings"))
    QSettings().clear()


def _make_window(monkeypatch, mode=None):
    if mode is None:
        mode = AnalysisMode.LABELLED
    monkeypatch.setattr(MainWindow, "_check_for_updates", lambda self: None)
    window = MainWindow(AnalysisContext(mode))
    window._skip_close_guard = True
    return window


def _gaussian(time, center, width, height):
    return height * np.exp(-0.5 * ((time - center) / width) ** 2)


@pytest.fixture(autouse=True)
def cleanup_env():
    yield
    if "MANIC_DB_PATH" in os.environ:
        del os.environ["MANIC_DB_PATH"]


@pytest.fixture(autouse=True)
def delete_test_windows():
    """A scheme switch restyles every live widget, so windows a test leaves behind slow
    every later switch: thousands of widgets by the end of the suite."""
    app = QApplication.instance()
    before = set(app.topLevelWidgets()) if app is not None else set()
    yield
    app = QApplication.instance()
    if app is None:
        return
    for widget in app.topLevelWidgets():
        if widget not in before:
            widget.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
