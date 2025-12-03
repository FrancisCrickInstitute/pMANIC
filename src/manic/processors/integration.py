from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

BASELINE_NUM_POINTS = 3  # Number of points to sample at each edge for baseline fitting


def _fit_baseline_coefficients(
    time_data: np.ndarray,
    intensity_data: np.ndarray,
    *,
    n_points: int = BASELINE_NUM_POINTS,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Fit slope/intercept pairs for one or more traces using boundary samples."""
    if time_data is None or intensity_data is None:
        return None

    td = np.asarray(time_data, dtype=np.float64)
    idata = np.asarray(intensity_data, dtype=np.float64)

    if td.ndim != 1 or idata.size == 0:
        return None
    if len(td) < 2 * n_points:
        logger.debug(
            f"Insufficient points for baseline: {len(td)} < {2 * n_points}"
        )
        return None

    if idata.ndim == 1:
        idata = idata.reshape(1, -1)
    elif idata.ndim != 2:
        return None

    if idata.shape[1] != len(td):
        logger.warning(
            "Intensity array length %s does not match time array length %s",
            idata.shape[1],
            len(td),
        )
        return None

    left_idx = slice(0, n_points)
    right_idx = slice(-n_points, None)

    x_points = np.concatenate([td[left_idx], td[right_idx]])
    y_left = idata[:, left_idx]
    y_right = idata[:, right_idx]
    y_points = np.concatenate([y_left, y_right], axis=1).T  # Shape: (2*n, traces)

    try:
        coeffs = np.polyfit(x_points, y_points, 1)
        slopes, intercepts = coeffs[0], coeffs[1]
        return slopes, intercepts
    except Exception as e:
        logger.warning(f"Failed to fit baseline: {e}")
        return None


def _baseline_endpoints(
    time_data: np.ndarray, slopes: np.ndarray, intercepts: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Return baseline values at the first and last time points."""
    first = slopes * time_data[0] + intercepts
    last = slopes * time_data[-1] + intercepts
    return first, last


def _baseline_width(time_data: np.ndarray, use_legacy: bool) -> float:
    """Compute the baseline width for geometric area calculations."""
    if len(time_data) < 2:
        return 0.0
    if use_legacy:
        return float(len(time_data) - 1)
    return float(time_data[-1] - time_data[0])


def integrate_peak(
    intensity_data: np.ndarray,
    time_data: Optional[np.ndarray] = None,
    *,
    use_legacy: bool = False,
) -> float:
    """
    Integrate peak using either time-based or legacy unit-spacing method.

    This mirrors the integration behavior previously embedded in DataExporter.
    """
    if use_legacy or time_data is None:
        # MATLAB-style: unit spacing (produces ~100× larger values)
        return float(np.trapezoid(intensity_data))
    else:
        # Scientific: time-based integration (physically meaningful)
        return float(np.trapezoid(intensity_data, time_data))


def compute_linear_baseline(
    time_data: np.ndarray,
    intensity_data: np.ndarray,
    *,
    n_points: int = BASELINE_NUM_POINTS,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """
    Fit a first-degree polynomial (straight line) through boundary points.

    Samples n_points at each edge of the integration window (left and right),
    fits a linear baseline through all 2*n_points, and returns the baseline
    values at each time point.

    Args:
        time_data: Time array (already windowed to integration bounds)
        intensity_data: Intensity array (1D, already windowed)
        n_points: Number of points to sample at each edge (default: 3)

    Returns:
        Tuple of (time_data, baseline_y) or None if insufficient points
    """
    coeffs = _fit_baseline_coefficients(time_data, intensity_data, n_points=n_points)
    if coeffs is None:
        return None

    slopes, intercepts = coeffs
    slope = float(np.asarray(slopes).flat[0])
    intercept = float(np.asarray(intercepts).flat[0])

    td = np.asarray(time_data, dtype=np.float64)
    baseline_y = slope * td + intercept
    return td, baseline_y


def compute_baseline_area(
    time_data: np.ndarray,
    intensity_data: np.ndarray,
    *,
    use_legacy: bool = False,
    n_points: int = BASELINE_NUM_POINTS,
) -> Optional[float]:
    """
    Compute area under the fitted baseline line using geometric integration.

    Args:
        time_data: Time array (already windowed to integration bounds)
        intensity_data: Intensity array (1D, already windowed)
        use_legacy: If True, use unit-spacing integration
        n_points: Number of points to sample at each edge (default: 3)

    Returns:
        Area under baseline, or None if baseline cannot be computed
    """
    coeffs = _fit_baseline_coefficients(time_data, intensity_data, n_points=n_points)
    if coeffs is None:
        return None

    td = np.asarray(time_data, dtype=np.float64)
    if len(td) == 0:
        return 0.0

    slopes, intercepts = coeffs
    first, last = _baseline_endpoints(td, slopes, intercepts)
    width = _baseline_width(td, use_legacy)
    area = 0.5 * (float(np.asarray(first).flat[0]) + float(np.asarray(last).flat[0])) * width
    return float(area)

 
def _compute_baseline_areas_vectorized(
    time_data: np.ndarray,
    intensity_data: np.ndarray,
    *,
    use_legacy: bool = False,
    n_points: int = BASELINE_NUM_POINTS,
) -> np.ndarray:
    """Compute baseline areas for multiple traces simultaneously."""
    td = np.asarray(time_data, dtype=np.float64)
    if td.size == 0:
        num_traces = intensity_data.shape[0] if intensity_data.ndim > 1 else 1
        return np.zeros(num_traces, dtype=np.float64)

    coeffs = _fit_baseline_coefficients(time_data, intensity_data, n_points=n_points)
    if coeffs is None:
        num_traces = intensity_data.shape[0] if intensity_data.ndim > 1 else 1
        return np.full(num_traces, np.nan, dtype=np.float64)

    slopes, intercepts = coeffs
    first, last = _baseline_endpoints(td, slopes, intercepts)
    width = _baseline_width(td, use_legacy)
    areas = 0.5 * (first + last) * width
    return np.asarray(areas, dtype=np.float64)

 
def calculate_peak_areas(

    time_data: np.ndarray,
    intensity_data: np.ndarray,
    label_atoms: int,
    retention_time: Optional[float] = None,
    loffset: Optional[float] = None,
    roffset: Optional[float] = None,
    *,
    use_legacy: bool = False,
    baseline_correction: bool = False,
) -> List[float]:
    """
    Calculate integrated peak areas for each isotopologue from EIC data.

    This is a faithful extraction of the original logic from DataExporter.

    Args:
        time_data: Array of time points
        intensity_data: Array of intensity values (1D for unlabeled, flattened for labeled)
        label_atoms: Number of labeled atoms (0 for unlabeled compounds)
        retention_time: Center of integration window
        loffset: Left offset from retention time
        roffset: Right offset from retention time
        use_legacy: If True, use unit-spacing integration (MATLAB v3.3.0 compatible)
        baseline_correction: If True, subtract linear baseline from peak area

    Returns:
        List of integrated peak areas, one per isotopologue
    """

    # Helper function to apply integration boundaries
    def apply_integration_boundaries(
        td: np.ndarray, idata: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        if retention_time is not None and loffset is not None and roffset is not None:
            l_boundary = retention_time - loffset
            r_boundary = retention_time + roffset

            # Debug logging to understand integration window sizes
            original_points = len(td)
            time_range = (td.max() - td.min()) if len(td) > 0 else 0
            window_size = r_boundary - l_boundary

            # Strict boundaries to match MATLAB GVISO behavior (exclude endpoints)
            integration_mask = (td > l_boundary) & (td < r_boundary)
            points_in_window = int(np.sum(integration_mask))

            logger.debug(
                f"Integration boundaries: rt={retention_time:.3f}, loffset={loffset:.3f}, roffset={roffset:.3f}"
            )
            logger.debug(
                f"Boundaries: {l_boundary:.3f} to {r_boundary:.3f} (window={window_size:.3f} min)"
            )
            logger.debug(
                f"Data points: {points_in_window}/{original_points} in window (time_range={time_range:.3f} min)"
            )

            # Apply mask to trim data to integration window
            if np.any(integration_mask):
                td = td[integration_mask]
                if idata.ndim == 1:
                    idata = idata[integration_mask]
                else:
                    # For multi-dimensional data, apply mask to time axis (last dimension)
                    idata = idata[..., integration_mask]
                return td, idata
            else:
                # No data in integration window - return empty arrays
                logger.warning(
                    f"No data points in integration window {l_boundary:.3f} to {r_boundary:.3f}"
                )
                return np.array([]), np.array([])
        return td, idata

    num_isotopologues = (label_atoms or 0) + 1

    # Unlabeled compound - single trace
    if (label_atoms or 0) == 0:
        td, idata = apply_integration_boundaries(time_data, intensity_data)
        if len(td) == 0:
            return [0.0]
        total_area = integrate_peak(idata, td, use_legacy=use_legacy)

        # Apply baseline correction if enabled
        if baseline_correction:
            baseline_area = compute_baseline_area(td, idata, use_legacy=use_legacy)
            if baseline_area is not None:
                total_area = max(0.0, total_area - baseline_area)
                logger.debug(
                    f"Baseline correction applied: total={total_area + baseline_area:.2f}, "
                    f"baseline={baseline_area:.2f}, corrected={total_area:.2f}"
                )

        return [float(total_area)]

    # Labeled compound - multiple isotopologue traces
    num_time_points = len(time_data)
    try:
        # Reshape intensity data for isotopologues FIRST
        intensity_reshaped = intensity_data.reshape(num_isotopologues, num_time_points)

        # THEN apply integration boundaries to the reshaped data
        td, intensity_reshaped = apply_integration_boundaries(
            time_data, intensity_reshaped
        )
        if len(td) == 0:
            return [0.0] * num_isotopologues

        intensity_matrix = np.asarray(intensity_reshaped, dtype=np.float64)

        if use_legacy:
            total_areas = np.trapezoid(intensity_matrix, axis=1)
        else:
            total_areas = np.trapezoid(intensity_matrix, x=td, axis=1)

        if baseline_correction:
            baseline_areas = _compute_baseline_areas_vectorized(
                td, intensity_matrix, use_legacy=use_legacy
            )
            valid_mask = ~np.isnan(baseline_areas)
            if np.any(valid_mask):
                total_areas = np.asarray(total_areas, dtype=np.float64)
                total_areas[valid_mask] = np.maximum(
                    0.0, total_areas[valid_mask] - baseline_areas[valid_mask]
                )

        return [float(area) for area in total_areas]
    except ValueError as e:
        # If reshaping fails, log the issue and return zeros
        logger.warning(
            "Failed to reshape intensity data for isotopologue integration. "
            f"Expected shape: ({num_isotopologues}, {num_time_points}), "
            f"Got total elements: {len(intensity_data)}. Error: {e}"
        )
        return [0.0] * num_isotopologues
