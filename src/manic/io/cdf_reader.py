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


def _values(variable) -> np.ndarray:
    # netCDF4 returns masked arrays, and slicing one per scan is slow; keep the
    # mask only where a fill value actually hides data.
    values = variable[:]
    if np.ma.is_masked(values):
        return values
    data = np.ma.getdata(values)
    # Masked-array arithmetic promotes float32 to float64, so plain data must
    # too, or float32 files would round differently.
    return data.astype(np.float64, copy=False) if data.dtype.kind == "f" else data


def read_cdf_file(path: str | Path) -> CdfFileData:
    path = Path(path).expanduser()
    with Dataset(path, "r") as cdf:
        return CdfFileData(
            sample_name=path.stem,
            file_path=str(path),
            scan_time=_values(cdf.variables["scan_acquisition_time"]),
            mass=_values(cdf.variables["mass_values"]),
            intensity=_values(cdf.variables["intensity_values"]),
            scan_index=_values(cdf.variables["scan_index"]),
            point_count=_values(cdf.variables["point_count"]),
            total_intensity=_values(cdf.variables["total_intensity"]),
        )
