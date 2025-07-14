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
        return CdfFileData(
            sample_name=path.stem,
            file_path=str(path),
            scan_time=cdf.variables["scan_acquisition_time"][:],
            mass=cdf.variables["mass_values"][:],
            intensity=cdf.variables["intensity_values"][:],
            scan_index=cdf.variables["scan_index"][:],
            point_count=cdf.variables["point_count"][:],
            total_intensity=cdf.variables["total_intensity"][:],
        )
