from dataclasses import dataclass
from typing import Sequence

import numpy as np

from manic.io.cdf_reader import CdfFileData


class EmptyRtWindowError(ValueError):
    pass


@dataclass(slots=True)
class EIC:
    compound_name: str
    sample_name: str
    time: np.ndarray  # minutes
    intensity: np.ndarray
    label_atoms: int
    target_mzs: tuple[float, ...] = ()


def extract_eic(
    compound_name: str,
    t_r: float,
    target_mz: float,
    cdf: CdfFileData,
    mass_tol: float = 0.20,
    rt_window: float = 0.2,
    label_atoms: int = 0,
    target_mzs: Sequence[float] | None = None,
) -> EIC:
    """Return an EIC for `compound_name` or raise ValueError if empty."""

    times = cdf.scan_time / 60.0
    return _extract_eic_with_times(
        compound_name,
        t_r,
        target_mz,
        cdf,
        times,
        mass_tol,
        rt_window,
        label_atoms,
        target_mzs,
    )


def _extract_eic_with_times(
    compound_name: str,
    t_r: float,
    target_mz: float,
    cdf: CdfFileData,
    times: np.ndarray,
    mass_tol: float,
    rt_window: float,
    label_atoms: int = 0,
    target_mzs: Sequence[float] | None = None,
) -> EIC:
    """Shared extraction kernel for direct and cached-time import paths."""

    label_atoms = int(label_atoms) if label_atoms else 0
    times = np.asarray(times, dtype=np.float64)
    if times.shape != cdf.scan_time.shape:
        raise ValueError("times must contain one value per CDF scan")

    time_mask = (times >= t_r - rt_window) & (times <= t_r + rt_window)
    idx = np.where(time_mask)[0]
    if idx.size == 0:
        raise EmptyRtWindowError("no scans inside RT window")

    bounds = np.append(cdf.scan_index, len(cdf.mass))
    starts, ends = bounds[idx], bounds[idx + 1]
    if idx[-1] - idx[0] + 1 == idx.size:
        # Monotonic scan times make the in-window scans one contiguous slice.
        points = slice(starts[0], ends[-1])
    else:
        points = np.concatenate([np.arange(s, e) for s, e in zip(starts, ends)])
    # EICs have always ignored CDF masks. Float64 matches masked arithmetic.
    all_relevant_mass = np.ma.getdata(cdf.mass[points]).astype(np.float64, copy=False)
    all_relevant_intensity = np.ma.getdata(cdf.intensity[points])
    scan_indices = np.repeat(np.arange(idx.size), ends - starts)

    num_scans = len(idx)
    if target_mzs is None:
        target_mzs_array = target_mz + np.arange(label_atoms + 1, dtype=np.float64)
    else:
        target_mzs_array = np.asarray(tuple(target_mzs), dtype=np.float64)
        if target_mzs_array.ndim != 1 or target_mzs_array.size == 0:
            raise ValueError("target_mzs must contain at least one m/z value")

    num_channels = int(target_mzs_array.size)
    intensities_arr = np.zeros((num_channels, num_scans), dtype=np.float64)
    target_mzs_int = np.floor(target_mzs_array + 0.5).astype(int)
    rounded_masses = np.floor((all_relevant_mass - mass_tol) + 0.5).astype(int)

    for channel_index in range(num_channels):
        target_int = target_mzs_int[channel_index]
        mask = rounded_masses == target_int
        intensities_arr[channel_index] = np.bincount(
            scan_indices[mask], all_relevant_intensity[mask], minlength=num_scans
        )

    return EIC(
        compound_name,
        cdf.sample_name,
        times[time_mask],
        intensities_arr.ravel(),
        label_atoms,
        tuple(float(mz) for mz in target_mzs_array),
    )
