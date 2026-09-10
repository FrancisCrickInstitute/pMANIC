from types import SimpleNamespace

import numpy as np

from manic.processors.display_deconvolution import DisplayDeconvolution, PlotDisplay
from manic.processors.tile_y_scale import (
    TileScaleInput,
    TileYMaxOrigin,
    YScalePolicy,
    axes_for_tiles,
    tile_y_max,
)


class _SelectedModel:
    selected_index = 0
    integration_left = 0.0
    integration_right = 1.0
    fit_left = 0.0
    fit_right = 1.0

    def __init__(self, peak=12.0):
        self.peak = peak

    def evaluate_selected(self, time_grid):
        return np.full(np.asarray(time_grid).shape, self.peak)


class _Bundle:
    def __init__(self, channels, overlays=True):
        self.channels = channels
        self._overlays = overlays

    def shows_model_overlays(self, *, independent_channels: bool) -> bool:
        return self._overlays


def _channel(model):
    return SimpleNamespace(result=SimpleNamespace(model=model))


def _tile(
    prepared_intensity,
    raw_intensity,
    *,
    model=None,
    overlays=True,
    includes_raw_underlay=False,
    independent_channels=False,
) -> TileScaleInput:
    if model is None:
        model = _SelectedModel()
    display = None
    if overlays or model is not None:
        channels = (_channel(model),)
        display = DisplayDeconvolution(
            bundle=_Bundle(channels, overlays=overlays),
            intensity=np.asarray(prepared_intensity, dtype=np.float64),
        )
    return TileScaleInput(
        prepared=PlotDisplay(
            display=display,
            intensity=np.asarray(prepared_intensity, dtype=np.float64),
            includes_raw_underlay=includes_raw_underlay,
        ),
        raw_intensity=np.asarray(raw_intensity, dtype=np.float64),
        independent_channels=independent_channels,
    )


def test_extract_keeps_taller_neighbour_selected_peak_does_not():
    tile = _tile([1.0, 12.0, 3.0], [1.0, 12.0, 100.0])

    extract = tile_y_max(YScalePolicy.PER_TILE_EXTRACT, tile)
    selected = tile_y_max(YScalePolicy.PER_TILE_SELECTED_PEAK, tile)

    assert extract.origin is TileYMaxOrigin.EXTRACT
    assert extract.value == 100.0
    assert selected.origin is TileYMaxOrigin.SELECTED_PEAK
    assert selected.value == 12.0

    extract_axis, = axes_for_tiles(YScalePolicy.PER_TILE_EXTRACT, (tile,))
    selected_axis, = axes_for_tiles(YScalePolicy.PER_TILE_SELECTED_PEAK, (tile,))
    assert extract_axis.unscaled_max == 100.0
    assert extract_axis.scale_factor == 100.0
    assert extract_axis.scale_exp == 2
    assert extract_axis.scaled_max == 1.0
    assert selected_axis.unscaled_max == 12.0
    assert selected_axis.scale_factor == 10.0
    assert selected_axis.scale_exp == 1
    assert selected_axis.scaled_max == 1.2


def test_selected_peak_uses_model_series_not_raw_underlay():
    tile = _tile(
        [100.0, 80.0, 90.0],
        [100.0, 80.0, 90.0],
        includes_raw_underlay=True,
    )

    extract = tile_y_max(YScalePolicy.PER_TILE_EXTRACT, tile)
    selected = tile_y_max(YScalePolicy.PER_TILE_SELECTED_PEAK, tile)

    assert extract.value == 100.0
    assert selected.origin is TileYMaxOrigin.SELECTED_PEAK
    assert selected.value == 12.0


def test_selected_peak_skips_channels_without_a_model():
    display = DisplayDeconvolution(
        bundle=_Bundle(
            (_channel(_SelectedModel(12.0)), _channel(None)),
            overlays=True,
        ),
        intensity=np.array([[100.0], [200.0]]),
    )
    tile = TileScaleInput(
        prepared=PlotDisplay(
            display=display,
            intensity=np.array([[100.0], [200.0]]),
            includes_raw_underlay=True,
        ),
        raw_intensity=np.array([[100.0], [200.0]]),
        independent_channels=False,
    )

    selected = tile_y_max(YScalePolicy.PER_TILE_SELECTED_PEAK, tile)
    assert selected.origin is TileYMaxOrigin.SELECTED_PEAK
    assert selected.value == 12.0


def test_no_model_is_extract_fallback():
    tile = TileScaleInput(
        prepared=PlotDisplay(
            display=None,
            intensity=np.array([1.0, 5.0, 3.0]),
            includes_raw_underlay=False,
        ),
        raw_intensity=np.array([1.0, 5.0, 3.0]),
        independent_channels=False,
    )

    result = tile_y_max(YScalePolicy.PER_TILE_SELECTED_PEAK, tile)
    assert result.origin is TileYMaxOrigin.EXTRACT_FALLBACK
    assert result.value == 5.0
    axis, = axes_for_tiles(YScalePolicy.PER_TILE_SELECTED_PEAK, (tile,))
    assert axis.unscaled_max == 5.0


def test_shared_extract_copies_one_number_selected_peak_does_not():
    short = _tile(
        [4.0, 10.0],
        [4.0, 10.0],
        model=_SelectedModel(7.0),
        includes_raw_underlay=True,
    )
    tall = _tile(
        [8.0, 40.0],
        [8.0, 40.0],
        model=_SelectedModel(12.0),
        includes_raw_underlay=True,
    )

    shared = axes_for_tiles(YScalePolicy.SHARED_EXTRACT, (short, tall))
    assert shared[0].unscaled_max == 40.0
    assert shared[1].unscaled_max == 40.0
    assert shared[0].scaled_max == shared[1].scaled_max == 4.0
    assert shared[0] is shared[1]

    per_peak = axes_for_tiles(YScalePolicy.PER_TILE_SELECTED_PEAK, (short, tall))
    assert per_peak[0].unscaled_max == 7.0
    assert per_peak[1].unscaled_max == 12.0
    assert per_peak[0] is not per_peak[1]
