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
        # Masked-array indexing dominated EIC extraction. Masked arithmetic also
        # upcast float32 to float64; keep that, or bin-edge masses change bin.
        cdf.set_auto_mask(False)

        def floats(name: str) -> np.ndarray:
            return np.asarray(cdf.variables[name][:], dtype=np.float64)

        return CdfFileData(
            sample_name=path.stem,
            file_path=str(path),
            scan_time=floats("scan_acquisition_time"),
            mass=floats("mass_values"),
            intensity=floats("intensity_values"),
            scan_index=cdf.variables["scan_index"][:],
            point_count=cdf.variables["point_count"][:],
            total_intensity=floats("total_intensity"),
        )
