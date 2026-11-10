"""Apply re-centres every sample's EIC on its new tR (issue 264)."""

import zlib

import numpy as np
import pytest
from netCDF4 import Dataset
from PySide6.QtWidgets import QLineEdit

from manic.io.eic_importer import (
    regenerate_compound_eics,
    samples_needing_reextraction,
)
from manic.models import database
from manic.ui.integration_window_widget import IntegrationWindow


def _write_cdf(path, first_scan, scans=None):
    if scans is None:
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


def _add_samples(tmp_path, first_scans):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES ('Pyruvate', 5.0, 0.035, 0.05, 174.0, 0)"
        )
        for sample_name, first_scan in first_scans.items():
            _write_cdf(tmp_path / f"{sample_name}.cdf", first_scan)
            conn.execute(
                "INSERT INTO samples (sample_name, file_name) VALUES (?, ?)",
                (sample_name, str(tmp_path / f"{sample_name}.cdf")),
            )


def _stored_windows():
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT sample_name, rt_window FROM eic WHERE deleted = 0 ORDER BY sample_name"
        ).fetchall()
    return {row["sample_name"]: round(row["rt_window"], 3) for row in rows}


def _window_that_re_extracts(samples):
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
    window.populate_fields_from_plots("Pyruvate", [], samples)
    return window, re_extracted


def test_a_tr_change_inside_the_stored_data_re_centres_every_plot(qapp, tmp_path):
    # The two files' scans sit half a scan apart, as real files do.
    _add_samples(tmp_path, {"S1": 4.0, "S2": 4.002})
    regenerate_compound_eics("Pyruvate", 0.2, ["S1", "S2"])
    assert _plot_ranges() == [(4.8, 5.2), (4.8, 5.2)]

    window, re_extracted = _window_that_re_extracts(["S1", "S2"])
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


def test_a_tr_change_keeps_each_samples_own_tr_window(qapp, tmp_path):
    _add_samples(tmp_path, {"S1": 4.0, "S2": 4.0})
    regenerate_compound_eics("Pyruvate", 0.2, ["S1"])
    regenerate_compound_eics("Pyruvate", 0.4, ["S2"])

    window, _ = _window_that_re_extracts(["S1", "S2"])
    assert window.findChild(QLineEdit, "tr_window_input").text() == "0.2 - 0.4"
    window.findChild(QLineEdit, "tr_input").setText("5.02")
    window._on_apply_clicked()

    assert _stored_windows() == {"S1": 0.2, "S2": 0.4}
    assert _plot_ranges() == [(4.82, 5.22), (4.62, 5.42)]
    window.deleteLater()


def test_apply_re_extracts_only_the_samples_whose_data_no_longer_fits(qapp, tmp_path):
    # S2's run starts after its window opens, so its stored trace is cut short.
    _add_samples(tmp_path, {"S1": 4.0, "S2": 4.7, "S3": 4.0})
    regenerate_compound_eics("Pyruvate", 0.2, ["S1"])
    regenerate_compound_eics("Pyruvate", 0.4, ["S2"])

    window, re_extracted = _window_that_re_extracts(["S1", "S2", "S3"])
    window.findChild(QLineEdit, "ro_input").setText("0.3")
    window._on_apply_clicked()

    # S1's window is narrower than the offset and S3 has no EIC yet.
    assert re_extracted == [["S1", "S3"]]
    assert _stored_windows() == {"S1": 0.4, "S2": 0.4, "S3": 0.4}
    window.deleteLater()


def test_irregular_scans_re_extract_when_the_tr_moves(tmp_path):
    scans = np.concatenate([[4.799], np.arange(4.81, 5.2, 0.02)])
    _add_samples(tmp_path, {})
    _write_cdf(tmp_path / "S1.cdf", None, scans)
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO samples (sample_name, file_name) VALUES ('S1', ?)",
            (str(tmp_path / "S1.cdf"),),
        )
    regenerate_compound_eics("Pyruvate", 0.2, ["S1"])

    # A fresh extraction at 4.995 also takes the scan at 4.799.
    assert samples_needing_reextraction("Pyruvate", {"S1": (4.995, 0.035, 0.05)}) == [
        "S1"
    ]
    assert samples_needing_reextraction("Pyruvate", {"S1": (5.0, 0.035, 0.05)}) == []
