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


def read_cdf_file(path: str | Path) -> CdfFileData:
    path = Path(path).expanduser()
    with Dataset(path, "r") as cdf:
        # Plain arrays keep EIC extraction fast. Float64 keeps the upcast masked
        # arithmetic gave float32 files, or bin-edge masses change bin. Arrays
        # with masked points stay masked so spectra and TIC storage skip them.
        def read(name: str, dtype: type | None = None) -> np.ndarray:
            values = cdf.variables[name][:]
            if np.ma.is_masked(values):
                return values
            return np.asarray(values, dtype=dtype)

        return CdfFileData(
            sample_name=path.stem,
            file_path=str(path),
            scan_time=read("scan_acquisition_time", np.float64),
            mass=read("mass_values", np.float64),
            intensity=read("intensity_values", np.float64),
            scan_index=read("scan_index"),
            point_count=read("point_count"),
            total_intensity=read("total_intensity", np.float64),
        )


def read_cdf_window(path: str | Path, t_r: float, rt_window: float) -> CdfFileData:
    """Read only the scans within t_r ± rt_window minutes, with scan_index rebased."""
    path = Path(path).expanduser()
    with Dataset(path, "r") as cdf:
        variables = cdf.variables
        scan_time = variables["scan_acquisition_time"][:]
        scan_index = variables["scan_index"][:]
        # Same mask arithmetic as extract_eic, so it selects the same scans.
        times = np.asarray(scan_time / 60.0, dtype=np.float64)
        idx = np.flatnonzero((times >= t_r - rt_window) & (times <= t_r + rt_window))
        first, last = (int(idx[0]), int(idx[-1]) + 1) if idx.size else (0, 0)
        bounds = np.append(scan_index, variables["mass_values"].shape[0])
        start, stop = int(bounds[first]), int(bounds[last])
        return CdfFileData(
            sample_name=path.stem,
            file_path=str(path),
            scan_time=scan_time[first:last],
            mass=variables["mass_values"][start:stop],
            intensity=variables["intensity_values"][start:stop],
            scan_index=scan_index[first:last] - start,
            point_count=variables["point_count"][first:last],
            total_intensity=variables["total_intensity"][first:last],
        )
