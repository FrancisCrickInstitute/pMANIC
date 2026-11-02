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
        if rt_range is None:
            scans = points = slice(None)
        else:
            scans, points = _window_slices(scan_time, scan_index, rt_range)
        index = scan_index[scans]
        if points.start:
            index = index - index.dtype.type(points.start)
        return CdfFileData(
            sample_name=path.stem,
            file_path=str(path),
            scan_time=scan_time[scans],
            mass=variables["mass_values"][points],
            intensity=variables["intensity_values"][points],
            scan_index=index,
            point_count=variables["point_count"][scans],
            total_intensity=variables["total_intensity"][scans],
        )


def _window_slices(scan_time, scan_index, rt_range: tuple[float, float]):
    minutes = np.asarray(scan_time / 60.0, dtype=np.float64)
    inside = np.flatnonzero((minutes >= rt_range[0]) & (minutes <= rt_range[1]))
    if inside.size == 0:
        return slice(0, 0), slice(0, 0)
    starts = np.asarray(scan_index)
    # Keep one scan past the window so extract_eic ends every scan where a whole-file read does.
    end = min(int(inside[-1]) + 2, starts.size)
    end_point = int(starts[end]) if end < starts.size else None
    return slice(int(inside[0]), end), slice(int(starts[inside[0]]), end_point)
