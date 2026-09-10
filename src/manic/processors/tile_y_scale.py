from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

import numpy as np

from manic.models.analysis import AnalysisMode
from manic.processors.display_deconvolution import PlotDisplay, display_y_max

MODEL_OVERLAY_GRID_POINTS = 256


class YScalePolicy(StrEnum):
    PER_TILE_EXTRACT = "per_tile_extract"
    SHARED_EXTRACT = "shared_extract"
    PER_TILE_SELECTED_PEAK = "per_tile_selected_peak"

    @classmethod
    def coerce(cls, value: YScalePolicy | str) -> YScalePolicy:
        if isinstance(value, cls):
            return value
        return cls(str(value).strip().lower())


@dataclass(frozen=True, slots=True)
class TileScaleInput:
    prepared: PlotDisplay
    raw_intensity: np.ndarray
    independent_channels: bool


@dataclass(frozen=True, slots=True)
class YAxisScale:
    scale_factor: float
    scale_exp: int
    scaled_max: float
    unscaled_max: float


def available_y_scale_policies(mode: AnalysisMode) -> frozenset[YScalePolicy]:
    if mode is AnalysisMode.UNLABELLED:
        return frozenset(
            {YScalePolicy.PER_TILE_EXTRACT, YScalePolicy.SHARED_EXTRACT}
        )
    return frozenset(YScalePolicy)


def extract_scale_intensity(
    prepared: PlotDisplay,
    raw_intensity: np.ndarray,
    *,
    independent_channels: bool,
) -> np.ndarray:
    display = prepared.display
    if (
        display is not None
        and not prepared.includes_raw_underlay
        and display.bundle.shows_model_overlays(
            independent_channels=independent_channels
        )
    ):
        return np.concatenate(
            (
                np.asarray(prepared.intensity, dtype=np.float64).ravel(),
                np.asarray(raw_intensity, dtype=np.float64).ravel(),
            )
        )
    return prepared.intensity


def selected_peak_scale_intensity(
    prepared: PlotDisplay,
    *,
    independent_channels: bool,
) -> np.ndarray | None:
    display = prepared.display
    if display is None:
        return None
    bundle = display.bundle
    models = tuple(
        channel.result.model
        for channel in bundle.channels
        if channel.result.model is not None
    )
    if not models:
        return None
    if (
        not prepared.includes_raw_underlay
        and bundle.shows_model_overlays(independent_channels=independent_channels)
    ):
        return np.asarray(prepared.intensity, dtype=np.float64)
    rows: list[np.ndarray] = []
    for model in models:
        t_left, t_right = model.integration_left, model.integration_right
        if not (t_right > t_left):
            t_left, t_right = model.fit_left, model.fit_right
        if not (t_right > t_left):
            continue
        grid = np.linspace(t_left, t_right, MODEL_OVERLAY_GRID_POINTS)
        rows.append(
            np.ravel(np.asarray(model.evaluate_selected(grid), dtype=np.float64))
        )
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]
    return np.vstack(rows)


def tile_y_max(policy: YScalePolicy, tile: TileScaleInput) -> float:
    match policy:
        case YScalePolicy.PER_TILE_SELECTED_PEAK:
            selected = selected_peak_scale_intensity(
                tile.prepared,
                independent_channels=tile.independent_channels,
            )
            if selected is not None:
                return display_y_max(selected)
            return display_y_max(
                extract_scale_intensity(
                    tile.prepared,
                    tile.raw_intensity,
                    independent_channels=tile.independent_channels,
                )
            )
        case YScalePolicy.PER_TILE_EXTRACT | YScalePolicy.SHARED_EXTRACT:
            return display_y_max(
                extract_scale_intensity(
                    tile.prepared,
                    tile.raw_intensity,
                    independent_channels=tile.independent_channels,
                )
            )
        case unexpected:
            assert_never(unexpected)


def y_axis_from_max(unscaled_max: float) -> YAxisScale:
    scale_exp = int(np.floor(np.log10(unscaled_max))) if unscaled_max > 0 else 0
    scale_factor = 10**scale_exp
    scaled_max = unscaled_max / scale_factor if scale_factor != 0 else 0.0
    return YAxisScale(scale_factor, scale_exp, scaled_max, unscaled_max)


def axes_for_tiles(
    policy: YScalePolicy,
    tiles: Sequence[TileScaleInput],
) -> tuple[YAxisScale, ...]:
    policy = YScalePolicy.coerce(policy)
    if not tiles:
        return ()
    maxima = tuple(tile_y_max(policy, tile) for tile in tiles)
    match policy:
        case YScalePolicy.SHARED_EXTRACT:
            shared = y_axis_from_max(max(maxima, default=0.0))
            return tuple(shared for _ in maxima)
        case YScalePolicy.PER_TILE_EXTRACT | YScalePolicy.PER_TILE_SELECTED_PEAK:
            return tuple(y_axis_from_max(value) for value in maxima)
        case unexpected:
            assert_never(unexpected)
