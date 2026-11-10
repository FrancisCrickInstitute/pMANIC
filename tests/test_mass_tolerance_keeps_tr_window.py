import time
import zlib

import numpy as np
import pytest
import shiboken6
from netCDF4 import Dataset
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QMessageBox

from conftest import _make_window
from manic.io.eic_importer import import_eics
from manic.models import database


def _write_cdf(path):
    scan_time = np.arange(0.0, 600.0, 0.6)
    with Dataset(path, "w") as cdf:
        cdf.createDimension("scan", scan_time.size)
        cdf.createDimension("point", scan_time.size)
        values = {
            "scan_acquisition_time": ("scan", scan_time),
            "scan_index": ("scan", np.arange(scan_time.size, dtype="i4")),
            "point_count": ("scan", np.ones(scan_time.size, dtype="i4")),
            "total_intensity": ("scan", np.full(scan_time.size, 100.0)),
            "mass_values": ("point", np.full(scan_time.size, 100.0)),
            "intensity_values": ("point", np.full(scan_time.size, 100.0)),
        }
        for name, (dimension, data) in values.items():
            cdf.createVariable(name, data.dtype, (dimension,))[:] = data


def _insert_compound(name, rt_tolerance=None):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset,"
            " mass0, label_atoms, rt_tolerance) VALUES (?, 5.0, 0.02, 0.02, 100.0, 0, ?)",
            (name, rt_tolerance),
        )


def _wait_for(thread):
    deadline = time.monotonic() + 10
    while shiboken6.isValid(thread) and not thread.isFinished():
        assert time.monotonic() < deadline, "worker thread did not finish"
        QCoreApplication.processEvents()
        time.sleep(0.01)
    QCoreApplication.processEvents()


def _stored_windows():
    with database.get_connection() as conn:
        rows = conn.execute("SELECT compound_name, rt_window, x_axis FROM eic").fetchall()
    windows = {}
    for row in rows:
        times = np.frombuffer(zlib.decompress(row["x_axis"]), dtype=np.float64)
        windows[row["compound_name"]] = (
            round(row["rt_window"], 6),
            round(times.min(), 2),
            round(times.max(), 2),
        )
    return windows


@pytest.mark.parametrize("applied", [0.9, 0.15])
def test_mass_tolerance_change_keeps_each_tr_window(qapp, monkeypatch, tmp_path, applied):
    _insert_compound("Glucose")
    _insert_compound("Pyruvate")
    _write_cdf(tmp_path / "s1.cdf")
    import_eics(tmp_path)

    window = _make_window(monkeypatch)
    messages = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: messages.append(box.text()))
    window.compound_data_loaded = window.cdf_data_loaded = True
    window.toolbar.update_sample_list(["s1"])

    integration = window.toolbar.integration
    integration.populate_fields_from_plots("Glucose", ["s1"], ["s1"])
    integration.tr_window_edit.setText(str(applied))
    integration.regenerate_button.click()
    _wait_for(window._regen_thread)

    # Add Compound extracts at the compound's tR tolerance.
    _insert_compound("Lactate", rt_tolerance=0.6)
    window._after_compound_added("Lactate")
    _wait_for(window._regen_thread)

    before = {
        "Glucose": (applied, round(5.0 - applied, 2), round(5.0 + applied, 2)),
        "Lactate": (0.6, 4.4, 5.6),
        "Pyruvate": (0.2, 4.8, 5.2),
    }
    assert _stored_windows() == before

    window.apply_mass_tolerance(0.3)
    _wait_for(window._mass_tol_thread)

    assert _stored_windows() == before
    assert messages == []
