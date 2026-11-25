from __future__ import annotations

import os
import subprocess
import sys

from manic.models import database


def _imported_after(code: str, probe_modules: tuple[str, ...]) -> list[str]:
    script = (
        f"{code}\n"
        "import json, sys\n"
        f"mods = {list(probe_modules)!r}\n"
        "print(json.dumps([m for m in mods if m in sys.modules]))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    import json

    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_mode_dialog_startup_skips_heavy_modules():
    loaded = _imported_after(
        (
            "import manic.main\n"
            "from PySide6.QtWidgets import QApplication\n"
            "from manic.ui.analysis_mode_dialog import AnalysisModeDialog\n"
            "from manic.utils.utils import apply_app_stylesheet\n"
        ),
        (
            "numpy",
            "scipy",
            "pandas",
            "pydantic",
            "netCDF4",
            "xlsxwriter",
            "matplotlib",
            "PySide6.QtCharts",
        ),
    )
    assert loaded == []


def test_main_window_import_skips_heavy_io_modules():
    loaded = _imported_after(
        "from manic.ui.main_window import MainWindow",
        ("scipy", "pandas", "pydantic", "netCDF4", "xlsxwriter", "matplotlib"),
    )
    assert loaded == []


def test_reset_database_removes_stale_sidecars(tmp_path, monkeypatch):
    db_path = tmp_path / "manic.db"
    wal_path = tmp_path / "manic.db-wal"
    shm_path = tmp_path / "manic.db-shm"
    monkeypatch.setattr(database, "DB_FILE", db_path)

    database.init_db()
    database._close_cached_connection()
    wal_path.write_bytes(b"stale-wal")
    shm_path.write_bytes(b"stale-shm")

    database.reset_database()

    assert db_path.is_file()
    assert not wal_path.exists()
    assert not shm_path.exists()


def test_reset_database_closes_cached_connection_before_unlink(tmp_path, monkeypatch):
    db_path = tmp_path / "manic.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)

    database.init_db()
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, mass0) VALUES (?, ?, ?)",
            ("Alanine", 4.2, 116.1),
        )
    assert getattr(database._conn_local, "conn", None) is not None

    real_unlink = type(db_path).unlink
    conn_state_at_unlink: list[object] = []

    def _check_closed_before_unlink(self, *args, **kwargs):
        if self == db_path:
            conn_state_at_unlink.append(getattr(database._conn_local, "conn", None))
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(type(db_path), "unlink", _check_closed_before_unlink)
    database.reset_database()

    assert conn_state_at_unlink == [None]
    assert db_path.is_file()
    with database.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    assert count == 0


def test_reset_database_falls_back_when_file_locked(tmp_path, monkeypatch):
    db_path = tmp_path / "manic.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)

    database.init_db()
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, mass0) VALUES (?, ?, ?)",
            ("Alanine", 4.2, 116.1),
        )

    real_unlink = type(db_path).unlink

    def _deny_db_unlink(self, *args, **kwargs):
        if self == db_path:
            raise PermissionError("locked by another process")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(type(db_path), "unlink", _deny_db_unlink)

    database.reset_database()

    with database.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    assert count == 0


def test_smoke_test_flag_succeeds_from_source(tmp_path):
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "USERPROFILE": str(tmp_path),
    }
    proc = subprocess.run(
        [sys.executable, "-m", "manic.main", "--smoke-test"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
