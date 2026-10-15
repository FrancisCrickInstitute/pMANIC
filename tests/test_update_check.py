import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from manic.utils import update_check
from manic.utils.update_check import (
    FAILED,
    UpdateCheckResult,
    check_for_update,
    compare_manifest,
    parse_version,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_parse_version_strips_prefix_and_suffix():
    assert parse_version("v5.1.2-beta") == (5, 1, 2)
    assert parse_version("garbage") is None


def test_compare_manifest_reports_newer_release():
    manifest = {"version": "5.1.0", "url": "https://example.test/v5.1.0"}
    assert compare_manifest(manifest, current=(5, 0, 0)) == UpdateCheckResult(
        True, True, "5.1.0", "https://example.test/v5.1.0"
    )


def test_compare_manifest_older_or_equal_is_not_an_update():
    assert compare_manifest({"version": "v4.1.0"}, current=(5, 0, 0)).has_update is False
    assert compare_manifest({"version": "5.0.0"}, current=(5, 0, 0)).has_update is False


def test_compare_manifest_without_a_valid_version_fails():
    assert compare_manifest({}, current=(5, 0, 0)) == FAILED
    assert compare_manifest({"version": "garbage"}, current=(5, 0, 0)) == FAILED


def test_check_for_update_swallows_network_errors(monkeypatch):
    def boom(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(update_check, "fetch_manifest", boom)
    assert check_for_update() == FAILED


def test_committed_manifest_matches_the_worker_schema():
    manifest = json.loads((REPO_ROOT / "releases" / "latest.json").read_text())
    outcome = compare_manifest(manifest, current=(0, 0, 0))
    assert outcome.success
    assert outcome.has_update
    assert outcome.url.startswith("https://github.com/FrancisCrickInstitute/pMANIC/releases/")


CLOSE_DURING_CHECK = """
import sys, time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from manic.models import database
from manic.models.analysis import AnalysisContext, AnalysisMode
from manic.ui.main_window import MainWindow
from manic.utils import update_check

database.DB_FILE = Path(sys.argv[1])
with database.get_connection() as conn:
    conn.executescript(Path(sys.argv[2]).read_text(encoding="utf-8"))
update_check.fetch_manifest = lambda: (time.sleep(2), {"version": "99.0.0"})[1]
MainWindow._on_update_check_finished = lambda self, *args: print("late result", flush=True)
app = QApplication([])
window = MainWindow(AnalysisContext(AnalysisMode.LABELLED))
window._skip_close_guard = sys.argv[3] == "new-session"
window.show()
QTimer.singleShot(100, window.close)
app.exec()
del window
print("exited", flush=True)
"""


@pytest.mark.parametrize("close_path", ["user-close", "new-session"])
def test_closing_during_update_check_exits_cleanly(tmp_path, close_path):
    script = tmp_path / "close_during_check.py"
    script.write_text(CLOSE_DURING_CHECK)
    schema = REPO_ROOT / "src" / "manic" / "models" / "schema.sql"
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }
    args = [str(script), str(tmp_path / "test.db"), str(schema), close_path]
    proc = subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, timeout=60, env=env
    )
    assert "Destroyed while thread" not in proc.stderr
    assert proc.returncode == 0
    assert proc.stdout.splitlines() == ["exited"]
