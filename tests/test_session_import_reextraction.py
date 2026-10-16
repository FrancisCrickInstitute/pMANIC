"""Session import re-extracts EICs whose restored window falls outside them."""

import importlib
import sys
from pathlib import Path

import numpy as np

from manic.io.data_provider import DataProvider
from manic.io.eic_importer import import_eics, regenerate_compound_eics
from manic.models import database
from manic.models import session_export
from manic.models.session_activity import PendingRegeneration

from conftest import SCHEMA, _gaussian

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
synthetic_gcms = importlib.import_module("synthetic_gcms")

LIBRARY_RT = 7.0
DRIFTED_RT = 7.25


def _write_drifted_cdf(path: Path) -> None:
    scan_time_s = np.arange(6.0, 8.0, 0.01) * 60.0
    intensity = _gaussian(scan_time_s / 60.0, DRIFTED_RT, 0.02, 1000.0) + 1.0
    synthetic_gcms._write_cdf(
        path,
        scan_time_s=scan_time_s,
        mass=np.full(scan_time_s.size, 100.0),
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
