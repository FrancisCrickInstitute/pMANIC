"""Session import re-extracts EICs whose restored window falls outside them."""

import importlib
import sys
import zlib
from pathlib import Path

import numpy as np
import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QFileDialog, QMessageBox

from manic.io.data_provider import DataProvider
from manic.io.eic_importer import import_eics, regenerate_compound_eics
from manic.models import database
from manic.models import session_export
from manic.models.session_activity import PendingRegeneration
from manic.utils.workers import MassToleranceReloadWorker

from conftest import SCHEMA, _gaussian, _make_window

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
synthetic_gcms = importlib.import_module("synthetic_gcms")

LIBRARY_RT = 7.0
DRIFTED_RT = 7.25


def _write_drifted_cdf(path: Path, mass: float = 100.0) -> None:
    scan_time_s = np.arange(6.0, 8.0, 0.01) * 60.0
    intensity = _gaussian(scan_time_s / 60.0, DRIFTED_RT, 0.02, 1000.0) + 1.0
    synthetic_gcms._write_cdf(
        path,
        scan_time_s=scan_time_s,
        mass=np.full(scan_time_s.size, mass),
        intensity=intensity,
        scan_index=np.arange(scan_time_s.size),
        point_count=np.ones(scan_time_s.size, dtype=int),
        total_intensity=intensity,
    )


def _load_fresh_session(db_path: Path, cdf_dir: Path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_FILE", db_path)
    with database.get_connection() as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES ('Pyruvate', ?, 0.05, 0.05, 100.0, 0)",
            (LIBRARY_RT,),
        )
    import_eics(str(cdf_dir), mass_tol=0.2, rt_window=0.2)


def _eic_rt_window(sample_name: str) -> float:
    with database.get_connection() as conn:
        return conn.execute(
            "SELECT rt_window FROM eic WHERE compound_name = 'Pyruvate' "
            "AND sample_name = ?",
            (sample_name,),
        ).fetchone()["rt_window"]


def test_session_round_trip_restores_moved_windows_and_tr_window(
    tmp_path, monkeypatch
):
    cdf_dir = tmp_path / "cdf"
    cdf_dir.mkdir()
    _write_drifted_cdf(cdf_dir / "Bio_001.cdf")
    _write_drifted_cdf(cdf_dir / "Bio_002.cdf")

    _load_fresh_session(tmp_path / "original.db", cdf_dir, monkeypatch)
    regenerate_compound_eics(
        "Pyruvate",
        0.2,
        ["Bio_001"],
        retention_time={"Bio_001": DRIFTED_RT},
        pending_regeneration=PendingRegeneration(
            "Pyruvate", DRIFTED_RT, 0.05, 0.05, ("Bio_001",), ("Bio_001",)
        ),
    )
    regenerate_compound_eics("Pyruvate", 0.5, ["Bio_002"])
    original_areas = DataProvider()._compute_compound_areas("Bio_001", "Pyruvate")
    assert original_areas[0] > 10.0
    assert session_export.export_session_method(str(tmp_path / "session.json"))

    _load_fresh_session(tmp_path / "restored.db", cdf_dir, monkeypatch)
    session_path = tmp_path / "manic_session_export" / "session.json"
    assert session_export.import_session_overrides(str(session_path)) == (True, True)
    result = session_export.reextract_session_eics(str(session_path), mass_tol=0.2)

    assert result.failed == ()
    assert (
        DataProvider()._compute_compound_areas("Bio_001", "Pyruvate")
        == original_areas
    )
    assert _eic_rt_window("Bio_002") == 0.5

    _load_fresh_session(tmp_path / "moved.db", cdf_dir, monkeypatch)
    (cdf_dir / "Bio_001.cdf").rename(tmp_path / "moved.cdf")
    session_export.import_session_overrides(str(session_path))
    result = session_export.reextract_session_eics(str(session_path), mass_tol=0.2)

    assert result == session_export.SessionReextraction(
        1, ("Pyruvate / Bio_001: CDF file not found",)
    )
    assert _eic_rt_window("Bio_002") == 0.5


@pytest.mark.parametrize("reload_fails", [False, True])
def test_session_import_reloads_a_changed_tolerance_then_re_extracts_windows(
    qapp, tmp_path, monkeypatch, reload_fails
):
    # m/z 100.75 reads as 101 at the 0.2 Da load tolerance and as 100 at 0.35 Da.
    cdf_dir = tmp_path / "cdf"
    cdf_dir.mkdir()
    for sample in ("Bio_001", "Bio_002", "Bio_003"):
        _write_drifted_cdf(cdf_dir / f"{sample}.cdf", mass=100.75)

    _load_fresh_session(tmp_path / "original.db", cdf_dir, monkeypatch)
    regenerate_compound_eics(
        "Pyruvate",
        0.2,
        ["Bio_001"],
        retention_time={"Bio_001": DRIFTED_RT},
        pending_regeneration=PendingRegeneration(
            "Pyruvate", DRIFTED_RT, 0.05, 0.05, ("Bio_001",), ("Bio_001",)
        ),
    )
    regenerate_compound_eics("Pyruvate", 0.5, ["Bio_002"])
    assert session_export.export_session_method(
        str(tmp_path / "session.json"), mass_tolerance=0.35
    )

    _load_fresh_session(tmp_path / "restored.db", cdf_dir, monkeypatch)
    window = _make_window(monkeypatch)
    window.compound_data_loaded = window.cdf_data_loaded = True
    session_path = tmp_path / "manic_session_export" / "session.json"
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(session_path), "")
    )
    monkeypatch.setattr(window, "_show_question_dialog", lambda *a, **k: QMessageBox.Yes)
    # Progress updates run a global processEvents(), which can reach objects
    # leaked by earlier tests.
    for slot in ("_update_mass_tolerance_progress", "_update_regeneration_progress"):
        monkeypatch.setattr(window, slot, lambda *a: None)
    titles = []
    monkeypatch.setattr(
        window,
        "_create_message_box",
        lambda _kind, title, *a, **k: (
            titles.append(title) or type("Box", (), {"exec": lambda self: None})()
        ),
    )
    if reload_fails:
        monkeypatch.setattr(
            MassToleranceReloadWorker, "run", lambda self: self.failed.emit("disk gone")
        )
    moved_before = _stored_eic("Bio_001")

    window.import_session()
    thread = None
    for _ in range(1000):
        QCoreApplication.sendPostedEvents(window)
        running = window._running_background_thread()
        if running is None and thread is None:
            break
        if running is None:
            # isRunning() turns false before finished is posted; wait() returns after.
            thread.wait()
            thread = None
            continue
        thread = getattr(window, running)
        QCoreApplication.sendPostedEvents(thread)
        thread.wait(10)

    if reload_fails:
        # Nothing may be extracted at a tolerance the reload never confirmed.
        assert titles == ["Session Import Successful", "Regeneration Failed"]
        assert _stored_eic("Bio_001") == moved_before
    else:
        _assert_reloaded_then_re_extracted(titles, window)
    window.close()
    # Left to the garbage collector, this window can be freed mid-dispatch in a later test.
    shiboken6.delete(window)


def _stored_eic(sample: str) -> bytes:
    with database.get_connection() as conn:
        return conn.execute(
            "SELECT y_axis FROM eic WHERE sample_name = ? AND deleted = 0", (sample,)
        ).fetchone()["y_axis"]


def _assert_reloaded_then_re_extracted(titles, window):
    assert titles == ["Session Import Successful", "Regeneration Complete"]
    assert window.mass_tolerance == 0.35
    with database.get_connection() as conn:
        y_axis = conn.execute(
            "SELECT y_axis FROM eic WHERE sample_name = 'Bio_003'"
        ).fetchone()["y_axis"]
    assert np.frombuffer(zlib.decompress(y_axis), dtype=np.float64).min() >= 1.0
    assert DataProvider()._compute_compound_areas("Bio_001", "Pyruvate")[0] > 10.0
    assert _eic_rt_window("Bio_002") == 0.5
