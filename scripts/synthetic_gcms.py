"""Shared GC-MS chromatogram primitives used by the synthetic data generators."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
from netCDF4 import Dataset
from scipy.stats import exponnorm

# Silicone column bleed ions (nominal m/z → base amplitude in counts).
BLEED_IONS = {73.0: 260.0, 147.0: 420.0, 207.0: 350.0, 281.0: 520.0}

_EMPTY_I32 = np.zeros(0, dtype=np.int32)
_EMPTY_F64 = np.zeros(0, dtype=np.float64)


@lru_cache(maxsize=256)
def _emg_normalization(sigma: float, tau: float) -> tuple[float, float, float]:
    """Return shape, mode offset, and apex density independent of sample grid."""
    shape = max(tau / sigma, 1e-3)
    standard_time = np.linspace(-8.0, max(8.0, shape + 8.0), 32769)
    standard_density = exponnorm.pdf(standard_time, shape)
    mode_index = int(np.argmax(standard_density))
    return (
        shape,
        float(standard_time[mode_index] * sigma),
        float(standard_density[mode_index] / sigma),
    )


def _emg_trace(
    time_min: np.ndarray,
    center: float,
    amplitude: float,
    sigma: float,
    tau: float,
) -> np.ndarray:
    """Tailed chromatographic peak (exponentially modified Gaussian).

    Scaled so the apex lands on ``center`` with height ``amplitude``.
    """
    if amplitude <= 0 or sigma <= 0:
        return np.zeros_like(time_min)
    shape, mode_offset, apex_density = _emg_normalization(float(sigma), float(tau))
    raw = exponnorm.pdf(
        time_min,
        shape,
        loc=center - mode_offset,
        scale=sigma,
    )
    if apex_density <= 0:
        return np.zeros_like(time_min)
    return amplitude * raw / apex_density


def _baseline_trace(
    time_min: np.ndarray, rng: np.random.Generator, level: float
) -> np.ndarray:
    """Low wavy chemical baseline: sine wander + upward drift + noise."""
    duration = float(time_min[-1] - time_min[0])
    phase = rng.uniform(0.0, 2.0 * np.pi)
    wander = 0.55 * level * np.sin(
        2.0 * np.pi * time_min / rng.uniform(4.0, 9.0) + phase
    )
    drift = 0.5 * level * (time_min - time_min[0]) / duration
    noise = rng.normal(0.0, 0.12 * level, size=time_min.size)
    return np.clip(level + wander + drift + noise, 1.0, None)


def _write_cdf(
    path: Path,
    *,
    scan_time_s: np.ndarray,
    mass: np.ndarray,
    intensity: np.ndarray,
    scan_index: np.ndarray,
    point_count: np.ndarray,
    total_intensity: np.ndarray,
) -> None:
    with Dataset(path, "w", format="NETCDF3_CLASSIC") as cdf:
        n_scans = len(scan_time_s)
        n_points = len(mass)
        cdf.createDimension("scan_number", n_scans)
        cdf.createDimension("point_number", n_points)

        v_time = cdf.createVariable("scan_acquisition_time", "f8", ("scan_number",))
        v_mass = cdf.createVariable("mass_values", "f8", ("point_number",))
        v_inten = cdf.createVariable("intensity_values", "f8", ("point_number",))
        v_index = cdf.createVariable("scan_index", "i4", ("scan_number",))
        v_count = cdf.createVariable("point_count", "i4", ("scan_number",))
        v_tic = cdf.createVariable("total_intensity", "f8", ("scan_number",))

        v_time[:] = scan_time_s
        v_mass[:] = mass
        v_inten[:] = intensity
        v_index[:] = scan_index
        v_count[:] = point_count
        v_tic[:] = total_intensity


def _add_channel(
    masses_by_scan: list[list[float]],
    intens_by_scan: list[list[float]],
    time_min: np.ndarray,
    mz: float,
    trace: np.ndarray,
    rng: np.random.Generator,
    *,
    active_fraction: float = 1e-4,
) -> None:
    """Materialise a trace as jittered mass/intensity points per scan."""
    amplitude = float(trace.max()) if trace.size else 0.0
    if amplitude <= 0:
        return
    active = np.where(trace > amplitude * active_fraction)[0]
    for idx in active:
        signal = float(trace[idx])
        noise = float(rng.normal(0.0, 1.5 + 0.012 * signal))
        mass_jitter = float(np.clip(rng.normal(0.0, 0.02), -0.05, 0.05))
        masses_by_scan[idx].append(mz + mass_jitter)
        intens_by_scan[idx].append(max(1.0, signal + noise))


def channel_points(
    trace: np.ndarray,
    mz: float,
    rng: np.random.Generator,
    *,
    scan_offset: int = 0,
    shot_scale: float = 1.0,
    clip: float | None = None,
    active_fraction: float = 1e-4,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised counterpart of ``_add_channel``.

    Returns ``(scan_index, mass, intensity)`` arrays for scans above
    ``active_fraction`` of the trace apex.
    """
    if trace.size == 0:
        return _EMPTY_I32, _EMPTY_F64, _EMPTY_F64
    amplitude = float(trace.max())
    if amplitude <= 0:
        return _EMPTY_I32, _EMPTY_F64, _EMPTY_F64
    if active_fraction <= 0:
        active = np.arange(trace.size, dtype=np.int64)
    else:
        active = np.flatnonzero(trace > amplitude * active_fraction)
    if active.size == 0:
        return _EMPTY_I32, _EMPTY_F64, _EMPTY_F64
    signal = trace[active]
    noise = rng.normal(0.0, (1.5 + 0.012 * signal) * shot_scale)
    jitter = np.clip(rng.normal(0.0, 0.02, size=active.size), -0.05, 0.05)
    intensity = np.maximum(1.0, signal + noise)
    if clip is not None:
        intensity = np.minimum(intensity, clip)
    return (
        (active + scan_offset).astype(np.int32),
        np.asarray(mz + jitter, dtype=np.float64),
        np.asarray(intensity, dtype=np.float64),
    )


def assemble_scan_arrays(
    n_scans: int,
    scan_ids: np.ndarray,
    masses: np.ndarray,
    intensities: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sort points by scan then mass and build ANDI index arrays."""
    if scan_ids.size == 0:
        return (
            _EMPTY_F64,
            _EMPTY_F64,
            np.zeros(n_scans, dtype=np.int32),
            np.zeros(n_scans, dtype=np.int32),
            np.zeros(n_scans, dtype=np.float64),
        )
    order = np.lexsort((masses, scan_ids))
    scan_ids = scan_ids[order]
    masses = masses[order]
    intensities = intensities[order]
    point_count = np.bincount(scan_ids, minlength=n_scans).astype(np.int32)
    scan_index = np.zeros(n_scans, dtype=np.int32)
    scan_index[1:] = np.cumsum(point_count[:-1])
    total_intensity = np.zeros(n_scans, dtype=np.float64)
    np.add.at(total_intensity, scan_ids, intensities)
    return masses, intensities, scan_index, point_count, total_intensity
