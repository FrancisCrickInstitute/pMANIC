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


def _read(variable, key=slice(None), dtype: type | None = None) -> np.ndarray:
    """Read a CDF variable; the one array policy for full and windowed reads."""
    # Plain arrays keep EIC extraction fast. Float64 keeps the upcast masked
    # arithmetic gave float32 files, or bin-edge masses change bin. Arrays
    # with masked points stay masked so spectra and TIC storage skip them.
    values = variable[key]
    if np.ma.is_masked(values):
        return values
    return np.asarray(values, dtype=dtype)


def read_cdf_file(path: str | Path) -> CdfFileData:
    path = Path(path).expanduser()
    with Dataset(path, "r") as cdf:
        variables = cdf.variables
        return CdfFileData(
            sample_name=path.stem,
            file_path=str(path),
            scan_time=_read(variables["scan_acquisition_time"], dtype=np.float64),
            mass=_read(variables["mass_values"], dtype=np.float64),
            intensity=_read(variables["intensity_values"], dtype=np.float64),
            scan_index=_read(variables["scan_index"]),
            point_count=_read(variables["point_count"]),
            total_intensity=_read(variables["total_intensity"], dtype=np.float64),
        )


def read_cdf_window(path: str | Path, t_r: float, rt_window: float) -> CdfFileData:
    """Read only the scans within t_r ± rt_window minutes, with scan_index rebased."""
    path = Path(path).expanduser()
    with Dataset(path, "r") as cdf:
        variables = cdf.variables
        scan_time = _read(variables["scan_acquisition_time"], dtype=np.float64)
        scan_index = _read(variables["scan_index"])
        # Same mask arithmetic as extract_eic, so it selects the same scans.
        times = np.asarray(scan_time / 60.0, dtype=np.float64)
        idx = np.flatnonzero((times >= t_r - rt_window) & (times <= t_r + rt_window))
        # Keep one scan past the window: extract_eic ends each scan at the next
        # scan's start, so trimming at the window would change its last-scan ends.
        first, last = (int(idx[0]), int(idx[-1]) + 2) if idx.size else (0, 0)
        last = min(last, len(scan_index))
        bounds = np.append(scan_index, variables["mass_values"].shape[0])
        start, stop = int(bounds[first]), int(bounds[last])
        return CdfFileData(
            sample_name=path.stem,
            file_path=str(path),
            scan_time=scan_time[first:last],
            mass=_read(variables["mass_values"], slice(start, stop), np.float64),
            intensity=_read(
                variables["intensity_values"], slice(start, stop), np.float64
            ),
            # Masked arithmetic would skip masked offsets; extract_eic reads them raw.
            scan_index=np.asarray(scan_index[first:last]) - start,
            point_count=_read(variables["point_count"], slice(first, last)),
            total_intensity=_read(
                variables["total_intensity"], slice(first, last), np.float64
            ),
        )
