import os
import subprocess
import sys
from pathlib import Path

from conftest import SCHEMA

REPO_ROOT = Path(__file__).resolve().parents[1]

# A subprocess, because the bug is Qt aborting the whole process on exit.
CLOSE_DURING_CHECK = """
import sys, threading
from pathlib import Path
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication
from manic.models import database
from manic.models.analysis import AnalysisContext, AnalysisMode
from manic.ui.main_window import MainWindow
from manic.utils import update_check

QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, sys.argv[3])
database.DB_FILE = Path(sys.argv[1])
with database.get_connection() as conn:
    conn.executescript(Path(sys.argv[2]).read_text(encoding="utf-8"))
# A network that never answers.
update_check.fetch_manifest = lambda: threading.Event().wait()
app = QApplication([])
window = MainWindow(AnalysisContext(AnalysisMode.LABELLED))
window.show()
QTimer.singleShot(100, window.close)
app.exec()
del window
print("exited", flush=True)
"""


def test_closing_during_the_update_check_exits_at_once(tmp_path):
    script = tmp_path / "close_during_check.py"
    script.write_text(CLOSE_DURING_CHECK)
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }
    args = [str(tmp_path / "test.db"), str(SCHEMA), str(tmp_path / "settings")]
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert (proc.returncode, proc.stdout) == (0, "exited\n")
