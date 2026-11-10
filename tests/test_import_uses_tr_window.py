import time
import zlib

import numpy as np
import shiboken6
from netCDF4 import Dataset
from PySide6.QtCore import QCoreApplication

from conftest import _make_window
from manic.io.compounds_import import (
    UnlabelledCompoundRecord,
    import_compound_excel,
    insert_unlabelled_compound,
)
from manic.io.eic_importer import import_eics
from manic.models import database
from manic.models.analysis import AnalysisMode, IonChannel, IonRole

LIST_HEADER = "name,tR,lOffset,rOffset,quant_ion,qualifier_ion_1,tR Window\n"


def _write_cdf(path, masses=(100.0, 101.0)):
    scan_time = np.arange(0.0, 600.0, 0.6)
    points = scan_time.size * len(masses)
    with Dataset(path, "w") as cdf:
        cdf.createDimension("scan", scan_time.size)
        cdf.createDimension("point", points)
        values = {
            "scan_acquisition_time": ("scan", scan_time),
            "scan_index": ("scan", np.arange(scan_time.size, dtype="i4") * len(masses)),
            "point_count": ("scan", np.full(scan_time.size, len(masses), dtype="i4")),
            "total_intensity": ("scan", np.full(scan_time.size, 100.0 * len(masses))),
            "mass_values": ("point", np.tile(np.asarray(masses), scan_time.size)),
            "intensity_values": ("point", np.full(points, 100.0)),
        }
        for name, (dimension, data) in values.items():
            cdf.createVariable(name, data.dtype, (dimension,))[:] = data


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


def test_listed_compound_extracts_its_tr_window_like_add_compound(
    qapp, monkeypatch, tmp_path
):
    compound_list = tmp_path / "targets.csv"
    compound_list.write_text(
        LIST_HEADER
        + "Listed,5.0,0.02,0.02,100,101,0.6\n"
        + "Default,5.0,0.02,0.02,100,101,\n"
    )
    import_compound_excel(compound_list, AnalysisMode.UNLABELLED)
    cdf_dir = tmp_path / "cdf"
    cdf_dir.mkdir()
    _write_cdf(cdf_dir / "s1.cdf")
    import_eics(cdf_dir)

    window = _make_window(monkeypatch, AnalysisMode.UNLABELLED)
    window.compound_data_loaded = window.cdf_data_loaded = True
    window.toolbar.update_sample_list(["s1"])

    # The same compound, entered through Add Compound after the CDFs are loaded.
    insert_unlabelled_compound(
        UnlabelledCompoundRecord(
            compound_name="Added",
            retention_time=5.0,
            loffset=0.02,
            roffset=0.02,
            rt_window=0.6,
            amount_in_std_mix=None,
            int_std_amount=None,
            mm_files=None,
            channels=(
                IonChannel(mz=100.0, role=IonRole.QUANTIFIER, ordinal=0),
                IonChannel(mz=101.0, role=IonRole.QUALIFIER, ordinal=1),
            ),
        )
    )
    window._after_compound_added("Added")
    _wait_for(window._regen_thread)

    assert _stored_windows() == {
        "Added": (0.6, 4.4, 5.6),
        "Default": (0.2, 4.8, 5.2),
        "Listed": (0.6, 4.4, 5.6),
    }

    # A compound with no stored EIC yet takes the same window on a reload.
    with database.get_connection() as conn:
        conn.execute("DELETE FROM eic WHERE compound_name = 'Listed'")
    window.apply_mass_tolerance(0.3)
    _wait_for(window._mass_tol_thread)

    assert _stored_windows() == {
        "Added": (0.6, 4.4, 5.6),
        "Default": (0.2, 4.8, 5.2),
        "Listed": (0.6, 4.4, 5.6),
    }
