import json
import re
import zlib

import numpy as np
import pytest

from manic.io.cdf_reader import CdfFileData
from manic.io.eic_importer import regenerate_all_eics_with_mass_tolerance
from manic.models.session_export import import_session_overrides
from manic.models.database import (
    get_connection,
    restore_compounds,
    restore_samples,
    soft_delete_compound,
    soft_delete_samples,
)
from manic.ui.sample_recovery_dialog import SampleRecoveryDialog

FORMULA = "C6 O3 N1 H12 Si1 S0 P0"


def _cdf(path):
    # m/z 100.75 rounds to channel 100 only when the tolerance is above 0.25.
    return CdfFileData(
        sample_name=path.stem,
        file_path=str(path),
        scan_time=np.array([60.0, 70.0, 80.0]),
        mass=np.array([100.0, 100.75] * 3),
        intensity=np.array([1.0, 10.0] * 3),
        scan_index=np.array([0, 2, 4]),
        point_count=np.array([2, 2, 2]),
        total_intensity=np.array([11.0, 11.0, 11.0]),
    )


def _eic_intensities():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT compound_name, sample_name, y_axis FROM eic WHERE deleted = 0"
        ).fetchall()
    return {
        (row["compound_name"], row["sample_name"]): np.frombuffer(
            zlib.decompress(row["y_axis"]), dtype=np.float64
        ).tolist()
        for row in rows
    }


def _corrected_keys():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT compound_name, sample_name FROM eic_corrected WHERE deleted = 0"
        ).fetchall()
    return {(row["compound_name"], row["sample_name"]) for row in rows}


def _load_session(tmp_path, monkeypatch):
    monkeypatch.setattr("manic.io.eic_importer.read_cdf_file", _cdf)
    with get_connection() as conn:
        for name in ("Pyruvate", "Lactate"):
            conn.execute(
                "INSERT INTO compounds (compound_name, retention_time, mass0, "
                "label_atoms, formula) VALUES (?, 70.0 / 60.0, 100.0, 1, ?)",
                (name, FORMULA),
            )
        for sample in ("s1", "s2"):
            cdf_path = tmp_path / f"{sample}.cdf"
            cdf_path.write_bytes(b"cdf")
            conn.execute(
                "INSERT INTO samples (sample_name, file_name) VALUES (?, ?)",
                (sample, str(cdf_path)),
            )
    regenerate_all_eics_with_mass_tolerance(0.2)


def _delete_s2_and_lose_its_cdf_across_a_tolerance_change(tmp_path):
    soft_delete_samples(["s2"])
    (tmp_path / "s2.cdf").unlink()
    regenerate_all_eics_with_mass_tolerance(0.3)


def _deleted_samples():
    with get_connection() as conn:
        rows = conn.execute("SELECT sample_name FROM samples WHERE deleted = 1")
        return {row["sample_name"] for row in rows}


STALE_MESSAGE = (
    "Cannot restore s2: the CDF file was missing at the last mass tolerance "
    "change, so its EICs use an older tolerance. Put the CDF file back and "
    "change the mass tolerance to rebuild them."
)


def _pyruvate_deleted():
    with get_connection() as conn:
        return conn.execute(
            "SELECT deleted FROM compounds WHERE compound_name = 'Pyruvate'"
        ).fetchone()["deleted"]


def _write_session(tmp_path, pyruvate_deleted, deleted_samples):
    session = tmp_path / "session.json"
    session.write_text(
        json.dumps(
            {
                "compounds": [
                    {"compound_name": "Pyruvate", "deleted": pyruvate_deleted},
                    {"compound_name": "Lactate", "deleted": 0},
                ],
                "session_overrides": [
                    {
                        "compound_name": "Lactate",
                        "sample_name": sample,
                        "retention_time": 70.0 / 60.0,
                        "loffset": 0.1,
                        "roffset": 0.1,
                    }
                    for sample in ("s1", "s2")
                ],
                "deleted_samples": deleted_samples,
            }
        ),
        encoding="utf-8",
    )
    return str(session)


def test_restored_items_have_eics_at_the_current_tolerance(tmp_path, monkeypatch):
    _load_session(tmp_path, monkeypatch)

    soft_delete_compound("Pyruvate")
    soft_delete_samples(["s2"])
    regenerate_all_eics_with_mass_tolerance(0.3)
    restore_compounds(["Pyruvate"])
    restore_samples(["s2"])

    # M+0 picks up the 100.75 peak at 0.3; M+1 is empty.
    current_tolerance = [11.0, 11.0, 11.0, 0.0, 0.0, 0.0]
    assert _eic_intensities() == {
        ("Pyruvate", "s1"): current_tolerance,
        ("Pyruvate", "s2"): current_tolerance,
        ("Lactate", "s1"): current_tolerance,
        ("Lactate", "s2"): current_tolerance,
    }
    assert _corrected_keys() == {
        ("Pyruvate", "s1"),
        ("Pyruvate", "s2"),
        ("Lactate", "s1"),
        ("Lactate", "s2"),
    }


def test_recovery_dialog_refuses_a_sample_with_stale_eics(
    qapp, tmp_path, monkeypatch
):
    _load_session(tmp_path, monkeypatch)
    _delete_s2_and_lose_its_cdf_across_a_tolerance_change(tmp_path)
    warnings = []
    monkeypatch.setattr(
        "manic.ui.sample_recovery_dialog.QMessageBox.warning",
        lambda parent, title, text: warnings.append((title, text)),
    )

    dialog = SampleRecoveryDialog()
    dialog.sample_list.item(0).setSelected(True)
    dialog.restore_btn.click()

    assert warnings == [("Restore Refused", STALE_MESSAGE)]
    assert _deleted_samples() == {"s2"}


def test_session_import_refuses_a_sample_with_stale_eics(tmp_path, monkeypatch):
    _load_session(tmp_path, monkeypatch)
    soft_delete_compound("Pyruvate")
    _delete_s2_and_lose_its_cdf_across_a_tolerance_change(tmp_path)
    session = _write_session(tmp_path, pyruvate_deleted=0, deleted_samples=[])

    with pytest.raises(Exception, match=re.escape(STALE_MESSAGE)):
        import_session_overrides(session)

    assert _deleted_samples() == {"s2"}
    assert _pyruvate_deleted() == 1
