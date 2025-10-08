from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def integrate_peak(intensity_data: np.ndarray, time_data: Optional[np.ndarray] = None, *, use_legacy: bool = False) -> float:
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


def calculate_peak_areas(
    time_data: np.ndarray,
    intensity_data: np.ndarray,
    label_atoms: int,
    retention_time: Optional[float] = None,
    loffset: Optional[float] = None,
    roffset: Optional[float] = None,
    *,
    use_legacy: bool = False,
) -> List[float]:
    """
    Calculate integrated peak areas for each isotopologue from EIC data.

    This is a faithful extraction of the original logic from DataExporter.
    """

    # Helper function to apply integration boundaries
    def apply_integration_boundaries(td: np.ndarray, idata: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
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
        peak_area = integrate_peak(idata, td, use_legacy=use_legacy)
        return [float(peak_area)]

    # Labeled compound - multiple isotopologue traces
    num_time_points = len(time_data)
    try:
        # Reshape intensity data for isotopologues FIRST
        intensity_reshaped = intensity_data.reshape(num_isotopologues, num_time_points)

        # THEN apply integration boundaries to the reshaped data
        td, intensity_reshaped = apply_integration_boundaries(time_data, intensity_reshaped)
        if len(td) == 0:
            return [0.0] * num_isotopologues

        # Integrate each isotopologue using selected method
        peak_areas = []
        for i in range(num_isotopologues):
            peak_area = integrate_peak(intensity_reshaped[i], td, use_legacy=use_legacy)
            peak_areas.append(float(peak_area))
        return peak_areas
    except ValueError as e:
        # If reshaping fails, log the issue and return zeros
        logger.warning(
            "Failed to reshape intensity data for isotopologue integration. "
            f"Expected shape: ({num_isotopologues}, {num_time_points}), "
            f"Got total elements: {len(intensity_data)}. Error: {e}"
        )
        return [0.0] * num_isotopologues
