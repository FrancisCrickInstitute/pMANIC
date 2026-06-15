from __future__ import annotations

import dataclasses
import functools
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


STRINGENCY_PRESETS: dict[str, ChromatographicPeakDeconvolutionParameters] = {
    "1": ChromatographicPeakDeconvolutionParameters(
        13, 0.25, 0.12, 7.0, 2, 14.0, 0.04, ("gaussian",), 160
    ),
    "2": ChromatographicPeakDeconvolutionParameters(
        11, 0.18, 0.10, 6.0, 2, 12.0, 0.03, ("gaussian",), 180
    ),
    "3": ChromatographicPeakDeconvolutionParameters(
        9, 0.12, 0.08, 5.0, 3, 9.0, 0.02, ("gaussian", "bi_gaussian"), 220
    ),
    "4": ChromatographicPeakDeconvolutionParameters(
        7, 0.08, 0.05, 4.0, 3, 6.0, 0.015, ("gaussian", "bi_gaussian"), 260
    ),
    "5": ChromatographicPeakDeconvolutionParameters(
        5, 0.05, 0.04, 3.0, 4, 4.0, 0.01, ("gaussian", "bi_gaussian"), 320
    ),
    "6": ChromatographicPeakDeconvolutionParameters(
        3, 0.03, 0.03, 2.0, 4, 2.0, 0.0075, ("gaussian", "bi_gaussian", "emg"), 380
    ),
    "7": ChromatographicPeakDeconvolutionParameters(
        1, 0.02, 0.02, 1.5, 5, 0.0, 0.005, ("gaussian", "bi_gaussian", "emg"), 450
    ),
}
STRINGENCY_ALIASES = {"low": "2", "medium": "4", "high": "6"}


def normalize_stringency(value: str | None) -> str:
    value = (value or "off").lower().strip()
    value = STRINGENCY_ALIASES.get(value, value)
    return value if value == "off" or value in STRINGENCY_PRESETS else "off"


def chromatographic_peak_deconvolution_enabled(value: str | None) -> bool:
    return normalize_stringency(value) != "off"


def normalize_fit_type(value: str | None) -> PeakShapeFitType:
    value = (value or "auto").lower().strip()
    return value if value in PEAK_SHAPE_FIT_TYPES else "auto"


def deconvolve_eic(
    time_data: np.ndarray,
    intensity_data: np.ndarray,
    *,
    retention_time: float | None,
    loffset: float | None = None,
    roffset: float | None = None,
    stringency: str | None = "off",
    fit_type: str | None = "auto",
) -> EICChromatographicPeakDeconvolutionResult:
    """
    Split an EIC into chromatographic components and select the one nearest RT.

    Deconvolution-on mode always fits and reconstructs the selected window,
    including single-component windows. Multi-isotopologue inputs are fit as a
    matrix: each component has one shared elution shape and non-negative channel
    weights.
    """
    mode = normalize_stringency(stringency)
    shape_fit_type = normalize_fit_type(fit_type)
    time = np.asarray(time_data, dtype=np.float64)
    intensity = np.asarray(intensity_data, dtype=np.float64)

    if mode == "off" or time.size < 3 or intensity.size == 0:
        return _unchanged_result(time, intensity)

    params = STRINGENCY_PRESETS[mode]
    if shape_fit_type != "auto":
        params = dataclasses.replace(params, shape_models=(shape_fit_type,))

    matrix, was_1d = _as_trace_matrix(intensity)
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
        )
    )
    if model is not None and was_1d:
        model = dataclasses.replace(model, was_1d=True)

    target_rt = (
        retention_time
        if retention_time is not None
        else float(time[np.argmax(np.sum(matrix, axis=0))])
    )
    selected_center = (
        min(centers, key=lambda center: abs(center - target_rt))
        if centers
        else float(target_rt)
    )
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
    )


def _deconvolve_matrix(
    time: np.ndarray,
    matrix: np.ndarray,
    fit_mask: np.ndarray,
    integration_mask: np.ndarray,
    retention_time: float | None,
    params: ChromatographicPeakDeconvolutionParameters,
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

    try:
        fitted = _fit_joint_component_model_cached(
            window_time.tobytes(),
            window_matrix.tobytes(),
            window_matrix.shape,
            params,
        )
    except Exception:
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
    selected_index = int(
        np.argmin([abs(float(center) - float(target_rt)) for center in fitted.centers])
    )

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


@functools.lru_cache(maxsize=256)
def _fit_joint_component_model_cached(
    time_bytes: bytes,
    matrix_bytes: bytes,
    matrix_shape: tuple[int, int],
    params: ChromatographicPeakDeconvolutionParameters,
) -> FittedComponentModel | None:
    """Cache fits keyed by the windowed data so repeated calls reuse the result.

    The same window/stringency is fit many times per render (baseline, overlays,
    detailed plot) and on every offset drag, so identical inputs are common.
    """
    time = np.frombuffer(time_bytes, dtype=np.float64)
    matrix = np.frombuffer(matrix_bytes, dtype=np.float64).reshape(matrix_shape)
    return _fit_joint_component_model(time, matrix, params)


def _fit_joint_component_model(
    time: np.ndarray,
    matrix: np.ndarray,
    params: ChromatographicPeakDeconvolutionParameters,
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

    seed_indices = _candidate_peak_indices(y, params)
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

    def shapes_from(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        shapes: list[np.ndarray] = []
        centers: list[float] = []
        for index in range(component_count):
            shape_params = values[index * param_count : (index + 1) * param_count]
            centers.append(float(shape_params[0]))
            shapes.append(_component_shape(x_rel, shape_model, shape_params))
        order = np.argsort(centers)
        sorted_centers = np.asarray(centers, dtype=np.float64)[order]
        shape_matrix = np.asarray(shapes, dtype=np.float64)[order]
        return sorted_centers, shape_matrix

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
        _, shape_matrix = shapes_from(values)
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

    if not result.success:
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


def _candidate_peak_indices(
    matrix: np.ndarray, params: ChromatographicPeakDeconvolutionParameters
) -> list[int]:
    traces = [np.sum(matrix, axis=0), *[trace for trace in matrix]]
    candidates: list[tuple[int, float]] = []

    for trace in traces:
        for component in _detect_components(trace, params):
            candidates.append((component.apex, float(trace[component.apex])))

    if not candidates:
        summed = np.sum(matrix, axis=0)
        candidates.append((int(np.argmax(summed)), float(np.max(summed))))

    min_distance = max(1, int(np.floor(params.min_width_points / 2.0)))
    candidates.sort(key=lambda item: item[1], reverse=True)
    merged: list[tuple[int, float]] = []
    for index, score in candidates:
        if all(abs(index - kept_index) > min_distance for kept_index, _ in merged):
            merged.append((index, score))

    merged.sort(key=lambda item: item[1], reverse=True)
    return [index for index, _ in merged]


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


def _estimate_peak_sigma(
    summed: np.ndarray, dt: float, params: ChromatographicPeakDeconvolutionParameters
) -> float:
    """Estimate a characteristic peak sigma from the dominant peak's FWHM."""
    smoothed = _smooth(np.maximum(summed, 0.0), params.smooth_points)
    if smoothed.size < 3 or float(np.max(smoothed)) <= 0:
        return 0.0
    apex = int(np.argmax(smoothed))
    try:
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
