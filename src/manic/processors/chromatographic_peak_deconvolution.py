from __future__ import annotations

import dataclasses
import functools
import warnings
from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.optimize import least_squares, nnls
from scipy.signal import find_peaks, peak_widths
from scipy.special import erfcx

ChromatographicPeakDeconvolutionStringency = Literal[
    "off",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "low",
    "medium",
    "high",
]
PeakShapeModel = Literal["gaussian", "bi_gaussian", "emg"]
PeakShapeFitType = Literal["auto", "gaussian", "bi_gaussian", "emg"]
PEAK_SHAPE_FIT_TYPES: tuple[PeakShapeFitType, ...] = (
    "auto",
    "gaussian",
    "bi_gaussian",
    "emg",
)
DEFAULT_DECONVOLUTION_LEVEL = "4"
DEFAULT_DECONVOLUTION_FIT_TYPE = "auto"
MIN_DECONVOLUTION_CONTEXT_MINUTES = 0.25


@dataclass(frozen=True)
class ChromatographicPeakDeconvolutionParameters:
    smooth_points: int
    min_prominence_fraction: float
    min_height_fraction: float
    min_width_points: float
    max_components: int
    bic_improvement: float
    min_component_fraction: float
    shape_models: tuple[PeakShapeModel, ...]
    max_nfev: int
    # Curvature-prominence threshold (fraction of the trace's curvature range)
    # for detecting *shoulders* - overlapping components that ride on a flank
    # without forming their own local maximum. 0.0 disables shoulder detection;
    # smaller positive values are more sensitive. Only the higher levels enable
    # it, so the conservative levels keep their summit-only behaviour.
    shoulder_curvature_fraction: float = 0.0


@dataclass(frozen=True)
class ComponentWindow:
    left: int
    apex: int
    right: int


@dataclass(frozen=True)
class FittedComponentModel:
    baseline: np.ndarray
    components: np.ndarray
    centers: np.ndarray
    bic: float
    rss: float
    shape_model: PeakShapeModel
    # Continuous-model parameters, so the fitted curve can be re-evaluated on any
    # time grid (rather than only at the acquisition scan points). Centers are in
    # window-relative coordinates (add x0 to get absolute time); norms hold the
    # per-component normalization (max of the raw shape over the fit window).
    shape_params: np.ndarray | None = None
    norms: np.ndarray | None = None
    weights: np.ndarray | None = None
    intercept: np.ndarray | None = None
    x0: float = 0.0


@dataclass(frozen=True)
class DeconvolutionModel:
    """The continuous fitted model, evaluable on any time grid.

    This lets both display and integration use the exact same smooth curve the
    optimiser found, instead of its values sampled at the acquisition scans.
    """

    x0: float
    shape_model: PeakShapeModel
    shape_params: np.ndarray  # (n_components, n_shape_params), centers in x_rel
    norms: np.ndarray  # (n_components,)
    intercept: np.ndarray  # (n_channels,) >= 0
    weights: np.ndarray  # (n_channels, n_components) >= 0
    selected_index: int
    fit_left: float
    fit_right: float
    integration_left: float
    integration_right: float
    was_1d: bool = False

    @property
    def n_components(self) -> int:
        return int(self.shape_params.shape[0])

    def evaluate(self, time_grid: np.ndarray, component_index: int) -> np.ndarray:
        """Return baseline + component on ``time_grid`` for every channel.

        Shape is (n_channels, len(grid)), or (len(grid),) for 1-D inputs.
        """
        grid = np.asarray(time_grid, dtype=np.float64)
        raw = _component_shape_raw(
            grid - self.x0, self.shape_model, self.shape_params[component_index]
        )
        norm = float(self.norms[component_index])
        unit = raw / norm if norm > 0 and np.isfinite(norm) else np.zeros_like(raw)
        component = self.weights[:, component_index][:, None] * unit[None, :]
        out = np.maximum(self.intercept[:, None] + component, 0.0)
        return out[0] if self.was_1d else out

    def evaluate_selected(self, time_grid: np.ndarray) -> np.ndarray:
        return self.evaluate(time_grid, self.selected_index)


@dataclass(frozen=True)
class EICChromatographicPeakDeconvolutionResult:
    selected: np.ndarray
    selected_mask: np.ndarray
    excluded: list[np.ndarray]
    excluded_masks: list[np.ndarray]
    selected_center: float | None
    component_centers: list[float]
    model: DeconvolutionModel | None = None
    empty: bool = False


@dataclass(frozen=True)
class ChannelDeconvolution:
    index: int
    result: EICChromatographicPeakDeconvolutionResult


@dataclass(frozen=True)
class ChannelDeconvolutionBundle:
    time: np.ndarray
    channels: tuple[ChannelDeconvolution, ...]

    def uses_model_areas(self) -> bool:
        active = tuple(
            channel for channel in self.channels if not channel.result.empty
        )
        return bool(active) and all(
            channel.result.model is not None for channel in active
        )

    def has_any_model(self) -> bool:
        return any(channel.result.model is not None for channel in self.channels)

    def shows_model_overlays(self, *, independent_channels: bool) -> bool:
        if independent_channels:
            return self.has_any_model()
        return self.uses_model_areas()

    def evaluate_selected_stack(self, grid: np.ndarray) -> np.ndarray:
        """Evaluate every channel's selected component on a shared time grid."""
        grid = np.asarray(grid, dtype=np.float64)
        time = np.asarray(self.time, dtype=np.float64)
        rows: list[np.ndarray] = []
        for channel in self.channels:
            if channel.result.empty:
                rows.append(np.zeros(grid.size, dtype=np.float64))
                continue
            model = channel.result.model
            if model is not None:
                values = np.asarray(model.evaluate_selected(grid), dtype=np.float64)
                rows.append(np.ravel(values))
                continue
            selected = np.asarray(channel.result.selected, dtype=np.float64).reshape(-1)
            mask = np.asarray(channel.result.selected_mask, dtype=bool).reshape(-1)
            sampled = np.zeros(time.size, dtype=np.float64)
            sampled[mask] = selected[mask]
            rows.append(np.interp(grid, time, sampled, left=0.0, right=0.0))
        if not rows:
            return np.zeros((0, grid.size), dtype=np.float64)
        return np.vstack(rows)


# The ladder is recentred so the default level "4" is as *selective* (aggressive
# at splitting overlaps) as the old level "6", while keeping a modest compute
# budget at the low/mid levels. Selectivity is driven by the detection fields
# (smooth_points, min_prominence_fraction, min_height_fraction, min_width_points,
# bic_improvement, min_component_fraction); cost is driven by max_components,
# shape_models (EMG is the expensive one) and max_nfev. Raising selectivity
# without inflating the cost fields keeps export and interactive browsing fast
# even though the default now resolves weaker shoulders. Levels 5-7 push beyond
# the old top end (more components, EMG, larger optimizer budget).
STRINGENCY_PRESETS: dict[str, ChromatographicPeakDeconvolutionParameters] = {
    "1": ChromatographicPeakDeconvolutionParameters(
        13, 0.20, 0.10, 6.0, 2, 12.0, 0.030, ("gaussian",), 160, 0.0
    ),
    "2": ChromatographicPeakDeconvolutionParameters(
        9, 0.12, 0.07, 4.5, 2, 8.0, 0.020, ("gaussian", "bi_gaussian"), 200, 0.0
    ),
    "3": ChromatographicPeakDeconvolutionParameters(
        5, 0.06, 0.05, 3.0, 3, 4.0, 0.012, ("gaussian", "bi_gaussian"), 240, 0.0
    ),
    "4": ChromatographicPeakDeconvolutionParameters(
        3, 0.03, 0.03, 2.0, 3, 2.0, 0.0075, ("gaussian", "bi_gaussian"), 280, 0.0
    ),
    "5": ChromatographicPeakDeconvolutionParameters(
        3, 0.02, 0.025, 1.8, 4, 1.0, 0.006, ("gaussian", "bi_gaussian", "emg"), 340, 0.30
    ),
    "6": ChromatographicPeakDeconvolutionParameters(
        1, 0.015, 0.02, 1.5, 4, 0.5, 0.005, ("gaussian", "bi_gaussian", "emg"), 400, 0.20
    ),
    "7": ChromatographicPeakDeconvolutionParameters(
        1, 0.01, 0.015, 1.2, 5, 0.0, 0.004, ("gaussian", "bi_gaussian", "emg"), 460, 0.12
    ),
}
STRINGENCY_ALIASES = {"low": "2", "medium": "4", "high": "6"}

# Noise-gate presets: each maps a user-facing preset name to the minimum
# "smoothness" (lag-1 autocorrelation of the trace's first differences) a window
# must reach to be worth deconvolving. A smooth peak - even if sparsely sampled
# or weak - produces consecutive same-sign slopes (a positive value), while
# white noise alternates sign (about -0.5). Windows below the chosen threshold
# are treated as "too messy": the (expensive and usually discarded) curve fit is
# skipped and the raw trace is used, both for export integration and the
# on-screen overlay. ``None`` ("off") disables the smoothness gate entirely.
#   - balanced (default): sits in the empty gap between noise (~-0.5) and real
#     peaks (>=+0.3), biased slightly toward keeping borderline peaks.
#   - lenient: only skips near-pure noise.
#   - aggressive: only fits clearly smooth peaks.
NOISE_GATE_PRESETS: dict[str, float | None] = {
    "off": None,
    "lenient": -0.3,
    "balanced": -0.1,
    "aggressive": 0.1,
}
NOISE_GATE_TYPES: tuple[str, ...] = tuple(NOISE_GATE_PRESETS)
DEFAULT_NOISE_GATE = "balanced"

# Maximum relative residual (sum of squares of recon-minus-raw over sum of
# squares of raw) for a joint fit to be trusted over the raw trace. Above this
# the model reproduces the data poorly and we fall back to raw integration.
FIT_QUALITY_MAX_REL_RESIDUAL = 0.15
EMPTY_ION_FRACTION_OF_TALLEST = 1e-4


def _trace_is_empty(row: np.ndarray, reference_max: float) -> bool:
    if row.size == 0:
        return True
    peak = float(np.max(np.asarray(row, dtype=np.float64)))
    if not np.isfinite(peak) or peak <= 0.0:
        return True
    return bool(
        reference_max > 0.0 and peak < reference_max * EMPTY_ION_FRACTION_OF_TALLEST
    )


def normalize_noise_gate(value: str | None) -> str:
    value = (value or DEFAULT_NOISE_GATE).lower().strip()
    return value if value in NOISE_GATE_PRESETS else DEFAULT_NOISE_GATE


def normalize_stringency(value: str | None) -> str:
    value = (value or "off").lower().strip()
    value = STRINGENCY_ALIASES.get(value, value)
    return value if value == "off" or value in STRINGENCY_PRESETS else "off"


def chromatographic_peak_deconvolution_enabled(value: str | None) -> bool:
    return normalize_stringency(value) != "off"


def normalize_fit_type(value: str | None) -> PeakShapeFitType:
    value = (value or "auto").lower().strip()
    return value if value in PEAK_SHAPE_FIT_TYPES else "auto"


def deconvolve_channel_matrix(
    time_data: np.ndarray,
    intensity_data: np.ndarray,
    *,
    retention_time: float | None,
    loffset: float | None = None,
    roffset: float | None = None,
    stringency: str | None = "off",
    fit_type: str | None = "auto",
    noise_gate: str | None = DEFAULT_NOISE_GATE,
) -> ChannelDeconvolutionBundle:
    time = np.asarray(time_data, dtype=np.float64)
    intensity = np.asarray(intensity_data, dtype=np.float64)
    matrix, _ = _as_trace_matrix(intensity)
    reference_max = float(np.max(matrix)) if matrix.size else 0.0
    channels = []
    for index in range(matrix.shape[0]):
        result = deconvolve_eic(
            time,
            matrix[index],
            retention_time=retention_time,
            loffset=loffset,
            roffset=roffset,
            stringency=stringency,
            fit_type=fit_type,
            noise_gate=noise_gate,
        )
        if result.model is None and _trace_is_empty(matrix[index], reference_max):
            result = dataclasses.replace(result, empty=True)
        channels.append(ChannelDeconvolution(index=index, result=result))
    return ChannelDeconvolutionBundle(time=time, channels=tuple(channels))


@dataclass(frozen=True)
class DisplayDeconvolution:
    bundle: ChannelDeconvolutionBundle
    intensity: np.ndarray


def deconvolve_for_display(
    time_data: np.ndarray,
    raw_intensity: np.ndarray,
    *,
    retention_time: float | None,
    loffset: float | None = None,
    roffset: float | None = None,
    stringency: str | None = "off",
    fit_type: str | None = "auto",
    noise_gate: str | None = DEFAULT_NOISE_GATE,
    apply_correction=None,
    independent_channels: bool = False,
) -> DisplayDeconvolution:
    raw = np.asarray(raw_intensity, dtype=np.float64)
    bundle = deconvolve_channel_matrix(
        time_data,
        raw,
        retention_time=retention_time,
        loffset=loffset,
        roffset=roffset,
        stringency=stringency,
        fit_type=fit_type,
        noise_gate=noise_gate,
    )
    if apply_correction is None:
        return DisplayDeconvolution(bundle=bundle, intensity=raw)

    matrix, was_1d = _as_trace_matrix(raw)
    if bundle.shows_model_overlays(independent_channels=independent_channels):
        source = np.vstack(
            [
                np.asarray(channel.result.selected, dtype=np.float64).reshape(-1)
                for channel in bundle.channels
            ]
        )
    else:
        source = matrix
    corrected = np.asarray(apply_correction(source), dtype=np.float64)
    return DisplayDeconvolution(
        bundle=bundle,
        intensity=_restore_shape(corrected, was_1d),
    )


def deconvolve_eic(
    time_data: np.ndarray,
    intensity_data: np.ndarray,
    *,
    retention_time: float | None,
    loffset: float | None = None,
    roffset: float | None = None,
    stringency: str | None = "off",
    fit_type: str | None = "auto",
    noise_gate: str | None = DEFAULT_NOISE_GATE,
) -> EICChromatographicPeakDeconvolutionResult:
    """Split one EIC into components and keep the one nearest RT.

    Clean peaks become a one-component model. Overlaps are split. Messy,
    empty, failed, or collapsed-overlap fits fall back to the raw trace.
    Multi-channel matrices go through ``deconvolve_channel_matrix``.
    """
    mode = normalize_stringency(stringency)
    shape_fit_type = normalize_fit_type(fit_type)
    min_smoothness = NOISE_GATE_PRESETS[normalize_noise_gate(noise_gate)]
    time = np.asarray(time_data, dtype=np.float64)
    intensity = np.asarray(intensity_data, dtype=np.float64)
    matrix, was_1d = _as_trace_matrix(intensity)
    if matrix.shape[0] > 1:
        raise ValueError(
            "deconvolve_eic fits one chromatographic channel. "
            "Use deconvolve_channel_matrix for multi-channel matrices."
        )

    if mode == "off" or time.size < 3 or intensity.size == 0:
        return _unchanged_result(time, intensity)

    params = STRINGENCY_PRESETS[mode]
    if shape_fit_type != "auto":
        params = dataclasses.replace(params, shape_models=(shape_fit_type,))

    if matrix.shape[1] != time.size:
        return _unchanged_result(time, intensity)

    integration_mask = _window_mask(time, retention_time, loffset, roffset)
    if np.count_nonzero(integration_mask) == 0:
        return _masked_result(time, intensity, integration_mask)

    fit_mask = _deconvolution_fit_mask(time, retention_time, loffset, roffset)
    fit_mask = fit_mask | integration_mask
    if np.count_nonzero(fit_mask) < 5:
        return _masked_result(time, intensity, integration_mask)

    selected, selected_mask, excluded, excluded_masks, centers, model = (
        _deconvolve_matrix(
            time,
            matrix,
            fit_mask,
            integration_mask,
            retention_time,
            params,
            min_smoothness,
        )
    )
    if model is not None and was_1d:
        model = dataclasses.replace(model, was_1d=True)

    target_rt = (
        retention_time
        if retention_time is not None
        else float(time[np.argmax(np.sum(matrix, axis=0))])
    )
    no_in_window_peak = model is None and bool(centers)
    if model is not None:
        selected_center = float(
            model.x0 + model.shape_params[model.selected_index, 0]
        )
    elif no_in_window_peak:
        selected_center = None
    else:
        selected_center = float(target_rt)
    return EICChromatographicPeakDeconvolutionResult(
        selected=_restore_shape(selected, was_1d),
        selected_mask=_restore_shape(selected_mask, was_1d),
        excluded=[_restore_shape(component, was_1d) for component in excluded],
        excluded_masks=[
            _restore_shape(component, was_1d) for component in excluded_masks
        ],
        selected_center=selected_center,
        component_centers=sorted(set(centers)) if centers else [selected_center],
        model=model,
        empty=no_in_window_peak,
    )


def _deconvolve_matrix(
    time: np.ndarray,
    matrix: np.ndarray,
    fit_mask: np.ndarray,
    integration_mask: np.ndarray,
    retention_time: float | None,
    params: ChromatographicPeakDeconvolutionParameters,
    min_smoothness: float | None,
) -> tuple[
    np.ndarray,
    np.ndarray,
    list[np.ndarray],
    list[np.ndarray],
    list[float],
    DeconvolutionModel | None,
]:
    fit_indices = np.flatnonzero(fit_mask)
    integration_indices = np.flatnonzero(integration_mask)
    window_time = time[fit_mask]
    window_matrix = np.maximum(np.asarray(matrix[:, fit_mask], dtype=np.float64), 0.0)

    summed_window = np.sum(window_matrix, axis=0)
    candidate_count = len(_candidate_peak_indices(window_matrix, params))
    if _too_messy_to_fit(summed_window, min_smoothness):
        fitted = None
    else:
        try:
            if candidate_count < 2:
                fitted = _fit_single_component_model_cached(
                    window_time.tobytes(),
                    window_matrix.tobytes(),
                    window_matrix.shape,
                    params,
                    retention_time,
                )
            else:
                fitted = _fit_joint_component_model_cached(
                    window_time.tobytes(),
                    window_matrix.tobytes(),
                    window_matrix.shape,
                    params,
                    retention_time,
                )
        except Exception:
            fitted = None

        if fitted is not None and not _fit_reproduces_window(
            window_matrix,
            fitted,
            integration_mask=integration_mask[fit_mask],
        ):
            fitted = None
    if fitted is None:
        selected_mask = np.zeros_like(matrix, dtype=bool)
        selected_mask[:, integration_indices] = True
        return matrix.copy(), selected_mask, [], [], [], None

    target_rt = (
        retention_time
        if retention_time is not None
        else float(window_time[np.argmax(np.sum(window_matrix, axis=0))])
    )
    integration_left = float(time[integration_indices[0]])
    integration_right = float(time[integration_indices[-1]])
    in_window = [
        index
        for index, center in enumerate(fitted.centers)
        if integration_left <= float(center) <= integration_right
    ]
    if not in_window:
        selected = np.zeros_like(matrix, dtype=np.float64)
        selected_mask = np.zeros_like(matrix, dtype=bool)
        selected_mask[:, integration_indices] = True
        excluded = []
        excluded_masks = []
        for component_index in range(fitted.components.shape[0]):
            component_matrix = np.zeros_like(matrix, dtype=np.float64)
            component_matrix[:, fit_indices] = (
                fitted.baseline + fitted.components[component_index]
            )
            component_mask = np.zeros_like(matrix, dtype=bool)
            component_mask[:, fit_indices] = True
            excluded.append(component_matrix)
            excluded_masks.append(component_mask)
        return (
            selected,
            selected_mask,
            excluded,
            excluded_masks,
            [float(center) for center in fitted.centers],
            None,
        )

    selected_index = in_window[
        int(
            np.argmin(
                [abs(float(fitted.centers[index]) - float(target_rt)) for index in in_window]
            )
        )
    ]

    selected = np.zeros_like(matrix, dtype=np.float64)
    selected_mask = np.zeros_like(matrix, dtype=bool)
    selected[:, fit_indices] = fitted.baseline + fitted.components[selected_index]
    selected_mask[:, integration_indices] = True

    excluded: list[np.ndarray] = []
    excluded_masks: list[np.ndarray] = []
    for component_index in range(fitted.components.shape[0]):
        if component_index == selected_index:
            continue
        component_matrix = np.zeros_like(matrix, dtype=np.float64)
        component_matrix[:, fit_indices] = (
            fitted.baseline + fitted.components[component_index]
        )
        component_mask = np.zeros_like(matrix, dtype=bool)
        component_mask[:, fit_indices] = True
        excluded.append(component_matrix)
        excluded_masks.append(component_mask)

    model: DeconvolutionModel | None = None
    if (
        fitted.shape_params is not None
        and fitted.norms is not None
        and fitted.weights is not None
        and fitted.intercept is not None
        and integration_indices.size > 0
    ):
        model = DeconvolutionModel(
            x0=float(fitted.x0),
            shape_model=fitted.shape_model,
            shape_params=np.asarray(fitted.shape_params, dtype=np.float64),
            norms=np.asarray(fitted.norms, dtype=np.float64),
            intercept=np.maximum(np.asarray(fitted.intercept, dtype=np.float64), 0.0),
            weights=np.maximum(np.asarray(fitted.weights, dtype=np.float64), 0.0),
            selected_index=selected_index,
            fit_left=float(time[fit_indices[0]]),
            fit_right=float(time[fit_indices[-1]]),
            integration_left=float(time[integration_indices[0]]),
            integration_right=float(time[integration_indices[-1]]),
        )

    return (
        selected,
        selected_mask,
        excluded,
        excluded_masks,
        [float(center) for center in fitted.centers],
        model,
    )


@functools.lru_cache(maxsize=8192)
def _fit_single_component_model_cached(
    time_bytes: bytes,
    matrix_bytes: bytes,
    matrix_shape: tuple[int, int],
    params: ChromatographicPeakDeconvolutionParameters,
    target_rt: float | None = None,
) -> FittedComponentModel | None:
    time = np.frombuffer(time_bytes, dtype=np.float64)
    matrix = np.frombuffer(matrix_bytes, dtype=np.float64).reshape(matrix_shape)
    cheap = dataclasses.replace(
        params,
        max_components=1,
        shape_models=(params.shape_models[0],),
        max_nfev=min(80, params.max_nfev),
    )
    return _fit_joint_component_model(time, matrix, cheap, target_rt=target_rt)


@functools.lru_cache(maxsize=8192)
def _fit_joint_component_model_cached(
    time_bytes: bytes,
    matrix_bytes: bytes,
    matrix_shape: tuple[int, int],
    params: ChromatographicPeakDeconvolutionParameters,
    target_rt: float | None = None,
) -> FittedComponentModel | None:
    """Cache fits keyed by the windowed data so repeated calls reuse the result.

    The same window/stringency is fit many times per render (baseline, overlays,
    detailed plot) and on every offset drag, so identical inputs are common.

    The cache is sized to hold a full session's worth of distinct fits so that
    expensive fits computed while browsing compounds survive until export and are
    reused there instead of being recomputed. Entries are keyed by the exact
    window data plus settings, so a changed setting or re-extracted trace yields a
    different key and never returns a stale result; the cost is only memory (each
    entry is one window's small fit result).
    """
    time = np.frombuffer(time_bytes, dtype=np.float64)
    matrix = np.frombuffer(matrix_bytes, dtype=np.float64).reshape(matrix_shape)
    return _fit_joint_component_model(time, matrix, params, target_rt=target_rt)


def get_deconvolution_fit_cache_info():
    """Return cache statistics for the expensive joint-fit cache."""
    return _fit_joint_component_model_cached.cache_info()


def _fit_joint_component_model(
    time: np.ndarray,
    matrix: np.ndarray,
    params: ChromatographicPeakDeconvolutionParameters,
    target_rt: float | None = None,
) -> FittedComponentModel | None:
    if time.size < 5 or matrix.size == 0:
        return None

    x = np.asarray(time, dtype=np.float64)
    y = np.maximum(np.asarray(matrix, dtype=np.float64), 0.0)
    channels, points = y.shape
    x0 = float(x[0])
    x_rel = x - x0
    x_span = float(x_rel[-1] - x_rel[0])
    if x_span <= 0 or channels == 0 or points == 0:
        return None

    dt = float(np.median(np.diff(x))) if x.size > 1 else x_span
    min_sigma = max(dt, x_span / 500.0)
    max_y = max(float(np.max(y)), np.finfo(float).eps)

    # Data-driven width estimate from the dominant peak, so the initial sigma and
    # the sigma upper bound track the actual peaks instead of half the window.
    typical_sigma = _estimate_peak_sigma(np.sum(y, axis=0), dt, params)
    init_sigma = float(np.clip(typical_sigma if typical_sigma > 0 else min_sigma * 2.0,
                               min_sigma, x_span))
    max_sigma = min(max(min_sigma * 4.0, init_sigma * 4.0), x_span)

    seed_indices = _prioritize_target_seed(
        _candidate_peak_indices(y, params),
        x,
        target_rt,
    )
    max_components = max(1, min(params.max_components, len(seed_indices), points // 3))

    best: FittedComponentModel | None = None
    for component_count in range(1, max_components + 1):
        initial_centers = sorted(
            float(x_rel[index]) for index in seed_indices[:component_count]
        )
        best_at_count: FittedComponentModel | None = None
        for shape_model in params.shape_models:
            fitted = _fit_shape_candidate(
                x_rel,
                y,
                initial_centers,
                shape_model,
                min_sigma,
                max_sigma,
                init_sigma,
                max_y,
                params,
            )
            if fitted is None or not _is_usable_fit(fitted, params, min_sigma):
                continue
            fitted = FittedComponentModel(
                baseline=fitted.baseline,
                components=fitted.components,
                centers=fitted.centers + x0,
                bic=fitted.bic,
                rss=fitted.rss,
                shape_model=fitted.shape_model,
                shape_params=fitted.shape_params,
                norms=fitted.norms,
                weights=fitted.weights,
                intercept=fitted.intercept,
                x0=x0,
            )
            if best_at_count is None or fitted.bic < best_at_count.bic - params.bic_improvement:
                best_at_count = fitted
            # Only escalate to a more flexible shape if the current fit still
            # leaves structured residuals; clean peaks stop at the simplest model.
            if not _has_structured_residuals(fitted, y):
                break

        if best_at_count is None:
            continue
        if best is None or best_at_count.bic < best.bic - params.bic_improvement:
            best = best_at_count
        else:
            # Adding a component no longer improves the fit; stop growing.
            break

    return best


def _fit_shape_candidate(
    x_rel: np.ndarray,
    y: np.ndarray,
    initial_centers: list[float],
    shape_model: PeakShapeModel,
    min_sigma: float,
    max_sigma: float,
    init_sigma: float,
    max_y: float,
    params: ChromatographicPeakDeconvolutionParameters,
) -> FittedComponentModel | None:
    channels, points = y.shape
    component_count = len(initial_centers)
    param_count = _shape_param_count(shape_model)
    channel_scale = np.maximum(
        np.percentile(y, 95, axis=1) - np.percentile(y, 10, axis=1),
        max(max_y * 1e-6, np.finfo(float).eps),
    )

    # Only the shape parameters are optimized nonlinearly; the per-channel
    # baseline and component weights are linear, so they are recovered with a
    # non-negative least-squares solve for any trial shape (variable projection).
    initial: list[float] = []
    lower: list[float] = []
    upper: list[float] = []
    for center in initial_centers:
        initial.extend(_initial_shape_params(shape_model, center, init_sigma))
        low, high = _shape_param_bounds(shape_model, x_rel, min_sigma, max_sigma)
        lower.extend(low)
        upper.extend(high)

    def shapes_from(
        values: np.ndarray, sort: bool = True
    ) -> tuple[np.ndarray, np.ndarray]:
        shapes: list[np.ndarray] = []
        centers: list[float] = []
        for index in range(component_count):
            shape_params = values[index * param_count : (index + 1) * param_count]
            centers.append(float(shape_params[0]))
            shapes.append(_component_shape(x_rel, shape_model, shape_params))
        center_array = np.asarray(centers, dtype=np.float64)
        shape_matrix = np.asarray(shapes, dtype=np.float64)
        # Component order does not affect the objective (the model is a sum over
        # components), so the sort is skipped on the optimizer's hot path and
        # applied only when the ordered result is needed.
        if sort:
            order = np.argsort(center_array)
            center_array = center_array[order]
            shape_matrix = shape_matrix[order]
        return center_array, shape_matrix

    def solve_linear(
        shape_matrix: np.ndarray, enforce_nonneg: bool = False
    ) -> tuple[np.ndarray, np.ndarray]:
        design = np.column_stack([np.ones(points), shape_matrix.T])
        # Cheap unconstrained solve via the tiny (1+K)x(1+K) normal equations.
        # During optimization this runs on every residual evaluation, so it must
        # be fast; non-negativity is only enforced once on the final fit, where a
        # per-channel NNLS cleans up any channel with a negative coefficient.
        gram = design.T @ design
        gram[np.diag_indices_from(gram)] += 1e-12
        coef = np.linalg.solve(gram, design.T @ y.T)
        if enforce_nonneg:
            for channel in np.flatnonzero(np.any(coef < 0.0, axis=0)):
                coef[:, channel], _ = nnls(design, y[channel])
        return coef[0], coef[1:].T

    def residual(values: np.ndarray) -> np.ndarray:
        _, shape_matrix = shapes_from(values, sort=False)
        intercept, weights = solve_linear(shape_matrix)
        total = intercept[:, None] + weights @ shape_matrix
        return ((total - y) / channel_scale[:, None]).ravel()

    try:
        result = least_squares(
            residual,
            x0=np.asarray(initial, dtype=np.float64),
            bounds=(np.asarray(lower, dtype=np.float64), np.asarray(upper, dtype=np.float64)),
            x_scale="jac",
            max_nfev=params.max_nfev,
        )
    except Exception:
        return None

    # status 0 is max_nfev. Keep that only on the cheap 1-component path.
    if not result.success and (params.max_components != 1 or result.status != 0):
        return None
    if not np.all(np.isfinite(result.x)):
        return None

    centers, shape_matrix = shapes_from(result.x)
    intercept, weights = solve_linear(shape_matrix, enforce_nonneg=True)
    baseline = np.repeat(intercept[:, None], points, axis=1)
    components = weights.T[:, :, None] * shape_matrix[:, None, :]
    scaled_residual = (baseline + np.sum(components, axis=0) - y) / channel_scale[:, None]
    rss = float(np.sum(scaled_residual**2))
    observation_count = int(y.size)
    parameter_count = channels * (1 + component_count) + int(result.x.size)
    bic = observation_count * np.log(max(rss / observation_count, np.finfo(float).eps))
    bic += parameter_count * np.log(max(observation_count, 2))

    # Capture the continuous-model parameters in the same (center-sorted) order as
    # ``centers``/``components`` so the fit can be re-evaluated on any time grid.
    ordered_params = np.asarray(result.x, dtype=np.float64).reshape(
        component_count, param_count
    )
    ordered_params = ordered_params[np.argsort(ordered_params[:, 0])]
    norms = np.array(
        [
            float(np.max(_component_shape_raw(x_rel, shape_model, ordered_params[k])))
            for k in range(component_count)
        ],
        dtype=np.float64,
    )
    return FittedComponentModel(
        baseline=np.maximum(baseline, 0.0),
        components=np.maximum(components, 0.0),
        centers=centers,
        bic=float(bic),
        rss=rss,
        shape_model=shape_model,
        shape_params=ordered_params,
        norms=norms,
        weights=np.maximum(weights, 0.0),
        intercept=np.maximum(intercept, 0.0),
        x0=0.0,
    )


def _prioritize_target_seed(
    indices: list[int],
    time: np.ndarray,
    target_rt: float | None,
) -> list[int]:
    if target_rt is None or not indices:
        return indices
    nearest = min(indices, key=lambda index: abs(float(time[index]) - float(target_rt)))
    return [nearest] + [index for index in indices if index != nearest]


def _candidate_peak_indices(
    matrix: np.ndarray, params: ChromatographicPeakDeconvolutionParameters
) -> list[int]:
    traces = [np.sum(matrix, axis=0), *[trace for trace in matrix]]
    candidates: list[tuple[int, float]] = []

    for trace in traces:
        for component in _detect_components(trace, params):
            candidates.append((component.apex, float(trace[component.apex])))
        for apex in _detect_shoulder_indices(trace, params):
            candidates.append((apex, float(trace[apex])))

    if not candidates:
        summed = np.sum(matrix, axis=0)
        candidates.append((int(np.argmax(summed)), float(np.max(summed))))

    min_distance = max(1, int(np.floor(params.min_width_points / 2.0)))
    candidates.sort(key=lambda item: item[1], reverse=True)
    merged: list[tuple[int, float]] = []
    for index, score in candidates:
        if all(abs(index - kept_index) > min_distance for kept_index, _ in merged):
            merged.append((index, score))

    # find_peaks misses a peak clipped at the EIC extract edge.
    if len(merged) < 2:
        leftover = _leftover_peak_index(
            np.sum(matrix, axis=0),
            exclude_indices=[index for index, _ in merged],
            min_height_fraction=params.min_height_fraction,
        )
        if leftover is not None:
            merged.append((leftover, float(np.sum(matrix, axis=0)[leftover])))

    merged.sort(key=lambda item: item[1], reverse=True)
    return [index for index, _ in merged]


def _leftover_peak_index(
    trace: np.ndarray,
    *,
    exclude_indices: list[int],
    min_height_fraction: float,
) -> int | None:
    """Return the strongest remaining maximum after known peaks are blanked."""
    y = np.maximum(np.asarray(trace, dtype=np.float64), 0.0)
    if y.size < 3:
        return None
    peak = float(np.max(y))
    if peak <= 0:
        return None
    suppressed = y.copy()
    for index in exclude_indices:
        apex = int(index)
        half = float(y[apex]) * 0.5
        left = apex
        while left > 0 and y[left] >= half:
            left -= 1
        right = apex
        while right < y.size - 1 and y[right] >= half:
            right += 1
        suppressed[left : right + 1] = 0.0
    leftover_index = int(np.argmax(suppressed))
    leftover_height = float(suppressed[leftover_index])
    if leftover_height < peak * min_height_fraction:
        return None
    # The cut face of a blanked peak is a slope, not a second apex.
    if leftover_index == 0:
        if y[0] < y[1]:
            return None
    elif leftover_index == y.size - 1:
        if y[-1] < y[-2]:
            return None
    elif y[leftover_index] < y[leftover_index - 1] or y[leftover_index] < y[leftover_index + 1]:
        return None
    return leftover_index


def _has_structured_residuals(fitted: FittedComponentModel, y: np.ndarray) -> bool:
    """True if fit residuals are autocorrelated, signalling a wrong peak shape.

    White residuals mean the simpler model already fits, so a clean peak does
    not need to escalate to bi-Gaussian or EMG.
    """
    residual = fitted.baseline + np.sum(fitted.components, axis=0) - y
    if residual.shape[1] < 3:
        return False
    residual = residual - residual.mean(axis=1, keepdims=True)
    denominator = float(np.sum(residual**2))
    if denominator <= np.finfo(float).eps:
        return False
    lag1 = float(np.sum(residual[:, :-1] * residual[:, 1:]))
    return lag1 / denominator > 0.4


def _is_usable_fit(
    fitted: FittedComponentModel,
    params: ChromatographicPeakDeconvolutionParameters,
    min_sigma: float,
) -> bool:
    if fitted.components.size == 0 or not np.isfinite(fitted.bic):
        return False

    centers = np.sort(fitted.centers)
    if centers.size > 1 and np.min(np.diff(centers)) < min_sigma:
        return False

    component_by_channel = np.sum(fitted.components, axis=2)
    channel_totals = np.sum(component_by_channel, axis=0)
    if float(np.sum(channel_totals)) <= 0:
        return False
    channel_totals = np.maximum(channel_totals, np.finfo(float).eps)
    component_channel_fraction = component_by_channel / channel_totals[None, :]
    if np.any(np.max(component_channel_fraction, axis=1) < params.min_component_fraction):
        return False

    return bool(np.all(np.isfinite(fitted.components)))


def _too_messy_to_fit(
    summed: np.ndarray, min_smoothness: float | None
) -> bool:
    """Return True when a window is too noisy/flat to be worth deconvolving.

    Fitting a multi-component model to a very messy or near-flat window is the
    most expensive case (it defeats every early-stop heuristic and the result is
    usually discarded anyway), and drawing such a fit is misleading.

    We score smoothness by the lag-1 autocorrelation of the first differences:
    a real elution peak rises then falls, so consecutive slopes share sign
    (positive score) regardless of how sparsely or weakly it is sampled, whereas
    noise alternates sign (score near -0.5). Because the score is weighted by
    slope magnitude, a clear peak on a noisy baseline still scores positive,
    while a window dominated by noise scores low and is skipped.

    ``min_smoothness`` is the threshold from the active noise-gate preset, or
    ``None`` to disable the gate (only flat/degenerate windows are skipped).
    """
    if min_smoothness is None:
        return False
    y = np.maximum(np.asarray(summed, dtype=np.float64), 0.0)
    if y.size < 5 or float(np.max(y)) <= 0.0:
        return True
    diffs = np.diff(y)
    denominator = float(np.sum(diffs[:-1] ** 2 + diffs[1:] ** 2)) / 2.0
    if denominator <= np.finfo(float).eps:
        return True  # flat window: nothing to fit
    smoothness = float(np.sum(diffs[:-1] * diffs[1:])) / denominator
    return smoothness < min_smoothness


def _fit_reproduces_window(
    window_matrix: np.ndarray,
    fitted: FittedComponentModel,
    integration_mask: np.ndarray,
) -> bool:
    recon = fitted.baseline + np.sum(fitted.components, axis=0)
    recon = recon[:, integration_mask]
    raw = np.asarray(window_matrix, dtype=np.float64)[:, integration_mask]
    denominator = float(np.sum(raw ** 2))
    if denominator <= np.finfo(float).eps:
        return False
    rel_residual = float(np.sum((recon - raw) ** 2)) / denominator
    return rel_residual <= FIT_QUALITY_MAX_REL_RESIDUAL


def _estimate_peak_sigma(
    summed: np.ndarray, dt: float, params: ChromatographicPeakDeconvolutionParameters
) -> float:
    """Estimate a characteristic peak sigma from the dominant peak's FWHM."""
    smoothed = _smooth(np.maximum(summed, 0.0), params.smooth_points)
    if smoothed.size < 3 or float(np.max(smoothed)) <= 0:
        return 0.0
    apex = int(np.argmax(smoothed))
    try:
        # Flat/degenerate windows make SciPy emit a PeakPropertyWarning about
        # zero width/prominence. We already treat a zero result as "no usable
        # peak", so silence it here; otherwise it floods the console once per
        # fit during a full export (the dedup registry gets reset by other
        # catch_warnings blocks elsewhere), which is noisy and slows the run.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fwhm_points = float(peak_widths(smoothed, [apex], rel_height=0.5)[0][0])
    except Exception:
        return 0.0
    return fwhm_points * dt / 2.3548 if fwhm_points > 0 else 0.0


def _initial_shape_params(
    shape_model: PeakShapeModel, center: float, init_sigma: float
) -> list[float]:
    if shape_model == "gaussian":
        return [center, init_sigma]
    if shape_model == "bi_gaussian":
        return [center, init_sigma, init_sigma]
    return [center, init_sigma, init_sigma]


def _shape_param_bounds(
    shape_model: PeakShapeModel,
    x_rel: np.ndarray,
    min_sigma: float,
    max_sigma: float,
) -> tuple[list[float], list[float]]:
    center_bounds = [float(x_rel[0]), float(x_rel[-1])]
    if shape_model == "gaussian":
        return [center_bounds[0], min_sigma], [center_bounds[1], max_sigma]
    if shape_model == "bi_gaussian":
        return (
            [center_bounds[0], min_sigma, min_sigma],
            [center_bounds[1], max_sigma, max_sigma],
        )
    return (
        [center_bounds[0], min_sigma, min_sigma],
        [center_bounds[1], max_sigma, max_sigma * 4.0],
    )


def _shape_param_count(shape_model: PeakShapeModel) -> int:
    return 2 if shape_model == "gaussian" else 3


def _component_shape_raw(
    x_rel: np.ndarray, shape_model: PeakShapeModel, values: np.ndarray
) -> np.ndarray:
    """Evaluate the (un-normalized) peak shape on an arbitrary time grid."""
    if shape_model == "gaussian":
        center, sigma = values
        shape = np.exp(-0.5 * ((x_rel - center) / sigma) ** 2)
    elif shape_model == "bi_gaussian":
        center, sigma_left, sigma_right = values
        sigma = np.where(x_rel < center, sigma_left, sigma_right)
        shape = np.exp(-0.5 * ((x_rel - center) / sigma) ** 2)
    else:
        center, sigma, tau = values
        sigma = max(float(sigma), np.finfo(float).eps)
        tau = max(float(tau), np.finfo(float).eps)
        offset = x_rel - center
        # Stable EMG via the scaled complementary error function; the leading
        # 1/(2*tau) constant is dropped because the shape is max-normalized later.
        # z is clipped to keep erfcx finite far out in the (negligible) tail.
        z = np.clip((sigma / tau - offset / sigma) / np.sqrt(2.0), -26.0, None)
        shape = np.exp(-0.5 * (offset / sigma) ** 2) * erfcx(z)
    return np.asarray(shape, dtype=np.float64)


def _component_shape(
    x_rel: np.ndarray, shape_model: PeakShapeModel, values: np.ndarray
) -> np.ndarray:
    shape = _component_shape_raw(x_rel, shape_model, values)
    max_shape = float(np.max(shape)) if shape.size else 0.0
    if max_shape <= 0 or not np.isfinite(max_shape):
        return np.zeros_like(x_rel, dtype=np.float64)
    return np.asarray(shape / max_shape, dtype=np.float64)


def _masked_result(
    time: np.ndarray, intensity: np.ndarray, mask: np.ndarray
) -> EICChromatographicPeakDeconvolutionResult:
    matrix, was_1d = _as_trace_matrix(np.asarray(intensity, dtype=np.float64))
    selected_mask = np.zeros_like(matrix, dtype=bool)
    if mask.size == matrix.shape[1]:
        selected_mask[:, mask] = True
    trace = np.sum(matrix, axis=0) if matrix.size else np.array([], dtype=np.float64)
    center = float(time[np.argmax(trace)]) if trace.size == time.size else None
    return EICChromatographicPeakDeconvolutionResult(
        selected=np.asarray(intensity, dtype=np.float64),
        selected_mask=_restore_shape(selected_mask, was_1d),
        excluded=[],
        excluded_masks=[],
        selected_center=center,
        component_centers=[center] if center is not None else [],
    )


def _unchanged_result(
    time: np.ndarray, intensity: np.ndarray
) -> EICChromatographicPeakDeconvolutionResult:
    if time.size and intensity.size:
        matrix, _ = _as_trace_matrix(np.asarray(intensity, dtype=np.float64))
        trace = np.sum(matrix, axis=0)
        center = float(time[np.argmax(trace)]) if trace.size == time.size else None
    else:
        center = None
    return EICChromatographicPeakDeconvolutionResult(
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


def _deconvolution_fit_mask(
    time: np.ndarray,
    retention_time: float | None,
    loffset: float | None,
    roffset: float | None,
) -> np.ndarray:
    if retention_time is None:
        return np.ones(time.shape, dtype=bool)

    context = max(
        MIN_DECONVOLUTION_CONTEXT_MINUTES,
        float(loffset or 0.0),
        float(roffset or 0.0),
    )
    return (time > retention_time - context) & (time < retention_time + context)


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
    detection_trace: np.ndarray, params: ChromatographicPeakDeconvolutionParameters
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


def _detect_shoulder_indices(
    trace: np.ndarray, params: ChromatographicPeakDeconvolutionParameters
) -> list[int]:
    """Detect shoulder apices: components on a flank with no own local maximum.

    A shoulder never forms a local maximum, so ``find_peaks`` misses it, but it
    does show up as a distinct region of strong downward curvature. We therefore
    look for prominent peaks in the *negative second derivative* of the smoothed
    trace: a clean single peak has one curvature maximum (its apex) and yields
    nothing extra, while a shoulder adds a second one on the flank. The second
    derivative amplifies noise, so we smooth a little more than the detection
    smoothing and keep only candidates sitting on a meaningful part of the peak.

    Returns an empty list unless the level enables shoulder detection
    (``shoulder_curvature_fraction > 0``). These are only *seed candidates*: the
    BIC component-count test and the post-fit quality net still decide whether a
    split is actually kept, and at the levels where this is enabled the EMG model
    is available to explain genuine tailing as a single component rather than
    being split.
    """
    if params.shoulder_curvature_fraction <= 0.0:
        return []
    y = np.maximum(np.asarray(trace, dtype=np.float64), 0.0)
    if y.size < 5 or float(np.max(y)) <= 0:
        return []
    smoothed = _smooth(y, max(params.smooth_points, 5))
    y_min = float(np.min(smoothed))
    y_range = float(np.max(smoothed) - y_min)
    if y_range <= 0:
        return []
    # Local maxima of the concavity (= -second derivative) mark the strongest
    # downward-curving points: the apex and any shoulders.
    concavity = -np.gradient(np.gradient(smoothed))
    concavity_range = float(np.max(concavity) - np.min(concavity))
    if concavity_range <= 0:
        return []
    peaks, _ = find_peaks(
        concavity,
        prominence=params.shoulder_curvature_fraction * concavity_range,
    )
    height_floor = y_min + params.min_height_fraction * y_range
    return [int(index) for index in peaks if smoothed[index] >= height_floor]
