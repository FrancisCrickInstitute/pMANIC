from dataclasses import dataclass

import numpy as np

from manic.io.cdf_reader import CdfFileData
from manic.io.compound_reader import read_compound


@dataclass(slots=True)
class EIC:
    compound_name: str
    sample_name: str
    time: np.ndarray  # minutes
    intensity: np.ndarray
    label_atoms: int


def extract_eic(
    compound_name: str,
    t_r: float,
    target_mz: float,
    cdf: CdfFileData,
    mass_tol: float = 0.20,
    rt_window: float = 0.2,
    label_atoms: int = 0,
) -> EIC:
    """Return an EIC for `compound_name` or raise ValueError if empty."""

    # Use provided label_atoms or default to 0
    label_atoms = int(label_atoms) if label_atoms else 0

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

    # convert the two start/end arrays into single array
    # conatining sub-arrays of [start, end] pairs
    start_end_array = np.array([starts, ends]).T  # T transposes

    # array of all detected masses for the relevant scans
    # each item in the array is a mass (m/z)
    #  its indexcorresponds with an the index in the intensity array
    # All relevant masses concatenated into one big 1D array
    all_relevent_mass = np.concatenate([cdf.mass[s:e] for s, e in start_end_array])

    # Corresponding intensities (slice from cdf.intensity using start_end_array)
    all_relevant_intensity = np.concatenate(
        [cdf.intensity[s:e] for s, e in start_end_array]
    )

    # Array indicating which scan each mass/intensity belongs to
    # (Repeats scan index i for all points in scan i)
    # E.g. [0, 0, 0, 1, 1, 1, 2, 2, 2, 2]
    # So if scan 1 (which would be index 0) runs from 0-3 then the
    # first three points are 0. The second scan is 3-6, so the next three are 1
    scan_indices = np.concatenate(
        [np.full(e - s, i, dtype=int) for i, (s, e) in enumerate(start_end_array)]
    )

    # Total number of scans being used in EIC
    num_scans = len(idx)

    # num labels
    num_labels = label_atoms + 1

    # empty 2D array for intensities for each label ion
    intensities_arr = np.zeros((num_labels, num_scans), dtype=np.float64)

    # array containg numer of label ions
    label_ions = np.arange(num_labels)

    # array of target mzs
    target_mzs = target_mz + label_ions  # (e.g. 174, 175, 176, 177 for Pyruvate)

    # MATLAB-style asymmetric matching via offset-and-round
    # Compute integer targets for each label state using half-up rounding (MATLAB compatible)
    target_mzs_int = np.floor(target_mzs + 0.5).astype(int)

    # Precompute rounded masses: round(mass - offset) with half-up behavior
    # Use floor(x + 0.5) since masses are positive
    rounded_masses = np.floor((all_relevent_mass - mass_tol) + 0.5).astype(int)

    for label in label_ions:
        target_int = target_mzs_int[label]
        # Vectorized mask across ALL data points (no loop over scans)
        mask = (rounded_masses == target_int)

        # Sum intensities per scan (for all falling in mass range) using bincount (vectorized grouping/summation)
        # minlength ensures all scans are covered (even if sum is 0)
        intensities_arr[label] = np.bincount(
            scan_indices[mask], all_relevant_intensity[mask], minlength=num_scans
        )

    # Final concatenation for compression into the DB blob object
    # (handles label_atoms == 0 case automatically)
    concat_intensities_array = intensities_arr.ravel()  # Flattens to 1D array

    return EIC(
        compound_name,
        cdf.sample_name,
        times[time_mask],
        concat_intensities_array,
        label_atoms,
    )
