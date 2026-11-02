from dataclasses import dataclass
from pathlib import Path

import numpy as np
from netCDF4 import Dataset


@dataclass(slots=True)
class CdfFileData:
    sample_name: str  # stem, e.g. "sample_01"
    file_path: str  # full path as str
    scan_time: np.ndarray
    mass: np.ndarray
    intensity: np.ndarray
    scan_index: np.ndarray
    point_count: np.ndarray
    total_intensity: np.ndarray


def read_cdf_file(
    path: str | Path, rt_range: tuple[float, float] | None = None
) -> CdfFileData:
    """Read a CDF file, or only the scans inside ``rt_range`` (minutes)."""
    path = Path(path).expanduser()
    with Dataset(path, "r") as cdf:
        variables = cdf.variables
        scan_time = variables["scan_acquisition_time"][:]
        scan_index = variables["scan_index"][:]
        scans = slice(None)
        first_point, end_point = 0, None
        if rt_range is not None:
            minutes = scan_time / 60.0
            inside = np.flatnonzero(
                (minutes >= rt_range[0]) & (minutes <= rt_range[1])
            )
            if inside.size == 0:
                scans = slice(0, 0)
                end_point = 0
            else:
                first, end = int(inside[0]), int(inside[-1]) + 1
                scans = slice(first, end)
                first_point = int(scan_index[first])
                if end < len(scan_index):
                    end_point = int(scan_index[end])
        return CdfFileData(
            sample_name=path.stem,
            file_path=str(path),
            scan_time=scan_time[scans],
            mass=variables["mass_values"][first_point:end_point],
            intensity=variables["intensity_values"][first_point:end_point],
            scan_index=scan_index[scans] - first_point,
            point_count=variables["point_count"][scans],
            total_intensity=variables["total_intensity"][scans],
        )
