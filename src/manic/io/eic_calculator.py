from dataclasses import dataclass

import numpy as np

from .cdf_reader import CdfFileData


@dataclass(slots=True)
class EIC:
    compound_name: str
    sample_name: str
    time: np.ndarray  # minutes
    intensity: np.ndarray


def extract_eic(
    compound_name: str,
    t_r: float,
    target_mz: float,
    cdf: CdfFileData,
    mass_tol: float = 0.25,
    rt_window: float = 0.2,
) -> EIC:
    """Return an EIC for `compound_name` or raise ValueError if empty."""

    # Convert seconds → minutes
    times = cdf.scan_time / 60.0
    # boolean matrix with each value being true/false for whether the
    # `scan_time/60` is within the time window
    time_mask = (times >= t_r - rt_window) & (times <= t_r + rt_window)
    # get the indices of all scans within the retention time window
    # [0] required as np.where returns a tuple containing an array
    idx = np.where(time_mask)[0]
    if idx.size == 0:
        raise ValueError("no scans inside RT window")

    # Start spectrum indices for each scan
    starts = cdf.scan_index[idx]
    # If idx[-1] is the last scan in the file:
    if idx[-1] + 1 < len(cdf.scan_index):
        ends = cdf.scan_index[idx + 1]
    else:
        # For the last scan, append len(cdf.mass)
        ends = np.append(cdf.scan_index[idx[1:]], len(cdf.mass))

    # get the intenisty values for the eic
    eic_int = np.zeros(idx.size, dtype=float)
    for i, (s, e) in enumerate(zip(starts, ends)):
        scan_mass = cdf.mass[s:e]
        scan_intensity = cdf.intensity[s:e]
        scan_mass_mask = (scan_mass >= target_mz - mass_tol) & (
            scan_mass <= target_mz + mass_tol
        )
        eic_int[i] = scan_intensity[scan_mass_mask].sum()

    return EIC(compound_name, cdf.sample_name, times[time_mask], eic_int)
