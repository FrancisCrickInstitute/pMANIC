from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.signal import find_peaks, peak_widths

DeconvolutionStringency = Literal["off", "low", "medium", "high"]


@dataclass(frozen=True)
class DeconvolutionParameters:
    smooth_points: int
    min_prominence_fraction: float
    min_height_fraction: float
    min_width_points: float


@dataclass(frozen=True)
class ComponentWindow:
    left: int
    apex: int
    right: int


@dataclass(frozen=True)
class EICDeconvolutionResult:
    selected: np.ndarray
    selected_mask: np.ndarray
    excluded: list[np.ndarray]
    excluded_masks: list[np.ndarray]
    selected_center: float | None
    component_centers: list[float]


STRINGENCY_PRESETS: dict[str, DeconvolutionParameters] = {
    # Low is deliberately permissive for visible shoulders.
    "low": DeconvolutionParameters(3, 0.03, 0.03, 2.0),
    "medium": DeconvolutionParameters(5, 0.08, 0.05, 3.0),
    "high": DeconvolutionParameters(7, 0.15, 0.08, 4.0),
}


def normalize_stringency(value: str | None) -> str:
    value = (value or "off").lower().strip()
    return value if value in {"off", "low", "medium", "high"} else "off"


def deconvolution_enabled(value: str | None) -> bool:
    return normalize_stringency(value) != "off"


def deconvolve_eic(
    time_data: np.ndarray,
    intensity_data: np.ndarray,
    *,
    retention_time: float | None,
    loffset: float | None = None,
    roffset: float | None = None,
    stringency: str | None = "off",
) -> EICDeconvolutionResult:
    """
    Split an EIC into chromatographic components and select the one nearest RT.

    Multi-isotopologue EICs are evaluated per trace. This catches mass-channel
    specific shoulders that can disappear when traces are summed together.
    """
    mode = normalize_stringency(stringency)
    time = np.asarray(time_data, dtype=np.float64)
    intensity = np.asarray(intensity_data, dtype=np.float64)

    if mode == "off" or time.size < 3 or intensity.size == 0:
        return _unchanged_result(time, intensity)

    matrix, was_1d = _as_trace_matrix(intensity)
    if matrix.shape[1] != time.size:
        return _unchanged_result(time, intensity)

    mask = _window_mask(time, retention_time, loffset, roffset)
    if np.count_nonzero(mask) < 3:
        return _unchanged_result(time, intensity)

    selected, selected_mask, excluded, excluded_masks, centers = _deconvolve_matrix(
        time,
        matrix,
        mask,
        retention_time,
        STRINGENCY_PRESETS[mode],
    )
    if not excluded:
        return _unchanged_result(time, intensity)

    selected_center = min(
        centers,
        key=lambda center: abs(
            center
            - (
                retention_time
                if retention_time is not None
                else float(time[np.argmax(np.sum(matrix, axis=0))])
            )
        ),
    )
    return EICDeconvolutionResult(
        selected=_restore_shape(selected, was_1d),
        selected_mask=_restore_shape(selected_mask, was_1d),
        excluded=[_restore_shape(component, was_1d) for component in excluded],
        excluded_masks=[
            _restore_shape(component, was_1d) for component in excluded_masks
        ],
        selected_center=selected_center,
        component_centers=sorted(set(centers)),
    )


def _deconvolve_matrix(
    time: np.ndarray,
    matrix: np.ndarray,
    mask: np.ndarray,
    retention_time: float | None,
    params: DeconvolutionParameters,
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray], list[np.ndarray], list[float]]:
    selected = matrix.copy()
    selected_mask = np.ones_like(matrix, dtype=bool)
    excluded: list[np.ndarray] = []
    excluded_masks: list[np.ndarray] = []
    centers: list[float] = []
    window_indices = np.flatnonzero(mask)
    window_time = time[mask]

    for trace_index, trace in enumerate(matrix):
        window_trace = trace[mask]
        components = _detect_components(window_trace, params)
        if len(components) <= 1:
            continue

        target_rt = (
            retention_time
            if retention_time is not None
            else float(window_time[np.argmax(window_trace)])
        )
        selected_index = min(
            range(len(components)),
            key=lambda i: abs(float(window_time[components[i].apex]) - float(target_rt)),
        )

        selected[trace_index, :] = 0.0
        selected_mask[trace_index, :] = False
        for component_index, component in enumerate(components):
            local_slice = slice(component.left, component.right + 1)
            global_indices = window_indices[local_slice]
            centers.append(float(window_time[component.apex]))

            if component_index == selected_index:
                selected[trace_index, global_indices] = window_trace[local_slice]
                selected_mask[trace_index, global_indices] = True
            else:
                component_matrix = np.zeros_like(matrix)
                component_matrix[trace_index, global_indices] = window_trace[local_slice]
                component_mask = np.zeros_like(matrix, dtype=bool)
                component_mask[trace_index, global_indices] = True
                excluded.append(component_matrix)
                excluded_masks.append(component_mask)

    return selected, selected_mask, excluded, excluded_masks, centers


def _unchanged_result(time: np.ndarray, intensity: np.ndarray) -> EICDeconvolutionResult:
    if time.size and intensity.size:
        matrix, _ = _as_trace_matrix(np.asarray(intensity, dtype=np.float64))
        trace = np.sum(matrix, axis=0)
        center = float(time[np.argmax(trace)]) if trace.size == time.size else None
    else:
        center = None
    return EICDeconvolutionResult(
        selected=np.asarray(intensity, dtype=np.float64),
        selected_mask=np.ones_like(np.asarray(intensity), dtype=bool),
        excluded=[],
        excluded_masks=[],
        selected_center=center,
        component_centers=[center] if center is not None else [],
    )


def _as_trace_matrix(intensity: np.ndarray) -> tuple[np.ndarray, bool]:
    if intensity.ndim == 1:
        return intensity.reshape(1, -1), True
    if intensity.ndim == 2:
        return intensity, False
    return intensity.reshape(1, -1), True


def _restore_shape(matrix: np.ndarray, was_1d: bool) -> np.ndarray:
    return matrix[0] if was_1d else matrix


def _window_mask(
    time: np.ndarray,
    retention_time: float | None,
    loffset: float | None,
    roffset: float | None,
) -> np.ndarray:
    if retention_time is None or loffset is None or roffset is None:
        return np.ones(time.shape, dtype=bool)
    return (time > retention_time - loffset) & (time < retention_time + roffset)


def _smooth(y: np.ndarray, points: int) -> np.ndarray:
    if points <= 1 or y.size < points:
        return y.astype(np.float64, copy=True)
    if points % 2 == 0:
        points += 1
    pad = points // 2
    padded = np.pad(y, pad_width=pad, mode="edge")
    kernel = np.ones(points, dtype=np.float64) / points
    return np.convolve(padded, kernel, mode="valid")


def _detect_components(
    detection_trace: np.ndarray, params: DeconvolutionParameters
) -> list[ComponentWindow]:
    y = np.maximum(np.asarray(detection_trace, dtype=np.float64), 0.0)
    if y.size < 3 or float(np.max(y)) <= 0:
        return []

    smoothed = _smooth(y, params.smooth_points)
    y_min = float(np.min(smoothed))
    y_range = float(np.max(smoothed) - y_min)
    if y_range <= 0:
        return []

    peaks, properties = find_peaks(
        smoothed,
        height=y_min + params.min_height_fraction * y_range,
        prominence=params.min_prominence_fraction * y_range,
    )
    if peaks.size == 0:
        return []

    widths = peak_widths(smoothed, peaks, rel_height=0.5)[0]
    keep = widths >= params.min_width_points
    peaks = peaks[keep]
    if peaks.size == 0:
        return []

    order = np.argsort(peaks)
    peaks = peaks[order]
    left_bases = properties["left_bases"][keep][order]
    right_bases = properties["right_bases"][keep][order]

    split_points: list[int] = []
    for left_peak, right_peak in zip(peaks[:-1], peaks[1:]):
        valley_offset = int(np.argmin(smoothed[left_peak : right_peak + 1]))
        split_points.append(int(left_peak + valley_offset))

    components: list[ComponentWindow] = []
    for i, peak in enumerate(peaks):
        left = int(left_bases[i]) if i == 0 else split_points[i - 1] + 1
        right = int(right_bases[i]) if i == len(peaks) - 1 else split_points[i]
        if right > left:
            components.append(ComponentWindow(left=left, apex=int(peak), right=right))

    return components
