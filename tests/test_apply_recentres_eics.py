"""Apply re-centres every sample's EIC on its new tR (issue 264)."""

import zlib

import numpy as np
import pytest
from netCDF4 import Dataset
from PySide6.QtWidgets import QLineEdit

from manic.io.eic_importer import regenerate_compound_eics
from manic.models import database
from manic.ui.integration_window_widget import IntegrationWindow


def _write_cdf(path, first_scan):
    scans = np.arange(first_scan, 6.0, 0.004)
    with Dataset(path, "w", format="NETCDF3_CLASSIC") as cdf:
        cdf.createDimension("scan_number", scans.size)
        cdf.createDimension("point_number", scans.size)
        values = {
            "scan_acquisition_time": ("scan_number", scans * 60.0),
            "scan_index": ("scan_number", np.arange(scans.size)),
            "point_count": ("scan_number", np.ones(scans.size)),
            "total_intensity": ("scan_number", np.ones(scans.size)),
            "mass_values": ("point_number", np.full(scans.size, 174.0)),
            "intensity_values": ("point_number", np.ones(scans.size)),
        }
        for name, (dimension, data) in values.items():
            dtype = "i4" if name in ("scan_index", "point_count") else "f8"
            cdf.createVariable(name, dtype, (dimension,))[:] = data


def _plot_ranges():
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT x_axis FROM eic WHERE deleted = 0 ORDER BY sample_name"
        ).fetchall()
    times = [np.frombuffer(zlib.decompress(row["x_axis"])) for row in rows]
    return [(round(float(t.min()), 2), round(float(t.max()), 2)) for t in times]


def test_a_tr_change_inside_the_stored_data_re_centres_every_plot(qapp, tmp_path):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES ('Pyruvate', 5.0, 0.035, 0.05, 174.0, 0)"
        )
        # The two files' scans sit half a scan apart, as real files do.
        for sample_name, first_scan in (("S1", 4.0), ("S2", 4.002)):
            _write_cdf(tmp_path / f"{sample_name}.cdf", first_scan)
            conn.execute(
                "INSERT INTO samples (sample_name, file_name) VALUES (?, ?)",
                (sample_name, str(tmp_path / f"{sample_name}.cdf")),
            )
    regenerate_compound_eics("Pyruvate", 0.2, ["S1", "S2"])
    assert _plot_ranges() == [(4.8, 5.2), (4.8, 5.2)]

    window = IntegrationWindow()
    window._show_message = lambda *args: pytest.fail(f"unexpected message {args}")
    re_extracted = []

    def re_extract(compound, tr_window, samples, rts):
        re_extracted.append(samples)
        regenerate_compound_eics(
            compound,
            tr_window,
            samples,
            retention_time=rts,
            pending_regeneration=window._pending_session_update,
        )

    window.data_regeneration_requested.connect(re_extract)
    window.populate_tr_window_field("Pyruvate")
    window.populate_fields_from_plots("Pyruvate", [], ["S1", "S2"])
    window.findChild(QLineEdit, "tr_input").setText("5.1")

    window._on_apply_clicked()

    assert _plot_ranges() == [(4.9, 5.3), (4.9, 5.3)]

    window.findChild(QLineEdit, "ro_input").setText("0.1")
    window._on_apply_clicked()
    assert re_extracted == [["S1", "S2"]]

    window.findChild(QLineEdit, "ro_input").setText("0.3")
    window._on_apply_clicked()
    assert re_extracted == [["S1", "S2"], ["S1", "S2"]]
    assert _plot_ranges() == [(4.7, 5.5), (4.7, 5.5)]
    window.deleteLater()
