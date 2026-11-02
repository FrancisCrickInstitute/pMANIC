import numpy as np
import pytest
from netCDF4 import Dataset

from manic.io.cdf_reader import read_cdf_file
from manic.processors.eic_calculator import EmptyRtWindowError, extract_eic


def _write_cdf(path):
    scan_minutes = np.arange(6.0, 8.0, 0.05)
    points_per_scan = 3
    with Dataset(path, "w", format="NETCDF3_CLASSIC") as cdf:
        cdf.createDimension("scan_number", scan_minutes.size)
        cdf.createDimension("point_number", scan_minutes.size * points_per_scan)
        values = {
            "scan_acquisition_time": ("scan_number", scan_minutes * 60.0),
            "scan_index": ("scan_number", np.arange(scan_minutes.size) * points_per_scan),
            "point_count": ("scan_number", np.full(scan_minutes.size, points_per_scan)),
            "total_intensity": ("scan_number", np.arange(scan_minutes.size, dtype=float)),
            "mass_values": ("point_number", np.tile([174.0, 175.0, 176.0], scan_minutes.size)),
            "intensity_values": ("point_number", np.arange(scan_minutes.size * points_per_scan, dtype=float)),
        }
        for name, (dimension, data) in values.items():
            dtype = "i4" if name in ("scan_index", "point_count") else "f8"
            cdf.createVariable(name, dtype, (dimension,))[:] = data


@pytest.mark.parametrize("t_r", [7.0, 7.9, 6.0])
def test_window_read_extracts_the_same_eic_as_a_whole_file_read(tmp_path, t_r):
    path = tmp_path / "s1.cdf"
    _write_cdf(path)

    whole = extract_eic("Pyruvate", t_r, 174.0, read_cdf_file(path), 0.2, 0.2, 2)
    window = extract_eic(
        "Pyruvate",
        t_r,
        174.0,
        read_cdf_file(path, (t_r - 0.2, t_r + 0.2)),
        0.2,
        0.2,
        2,
    )

    assert window.time.tolist() == whole.time.tolist()
    assert window.intensity.tolist() == whole.intensity.tolist()


def test_window_read_outside_the_run_has_no_scans(tmp_path):
    path = tmp_path / "s1.cdf"
    _write_cdf(path)

    with pytest.raises(EmptyRtWindowError):
        extract_eic("Pyruvate", 9.0, 174.0, read_cdf_file(path, (8.8, 9.2)), 0.2, 0.2, 2)
