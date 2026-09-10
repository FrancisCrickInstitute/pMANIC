from types import SimpleNamespace

import numpy as np

from manic.processors.display_deconvolution import DisplayDeconvolution, PlotDisplay
from manic.processors.tile_y_scale import (
    TileScaleInput,
    YScalePolicy,
    axes_for_tiles,
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


def _tile(prepared_intensity, raw_intensity, *, model=None) -> TileScaleInput:
    if model is None:
        model = _SelectedModel()
    display = DisplayDeconvolution(
        bundle=SimpleNamespace(
            channels=(SimpleNamespace(result=SimpleNamespace(model=model)),),
            shows_model_overlays=lambda *, independent_channels: True,
        ),
        intensity=np.asarray(prepared_intensity, dtype=np.float64),
    )
    return TileScaleInput(
        prepared=PlotDisplay(
            display=display,
            intensity=np.asarray(prepared_intensity, dtype=np.float64),
            includes_raw_underlay=True,
        ),
        raw_intensity=np.asarray(raw_intensity, dtype=np.float64),
        independent_channels=False,
    )


def test_selected_peak_ignores_a_taller_neighbour():
    tile = _tile([1.0, 12.0, 100.0], [1.0, 12.0, 100.0])

    extract, = axes_for_tiles(YScalePolicy.PER_TILE_EXTRACT, (tile,))
    selected, = axes_for_tiles(YScalePolicy.PER_TILE_SELECTED_PEAK, (tile,))

    assert extract.unscaled_max == 100.0
    assert selected.unscaled_max == 12.0


def test_shared_extract_copies_one_number_selected_peak_does_not():
    short = _tile([4.0, 10.0], [4.0, 10.0], model=_SelectedModel(7.0))
    tall = _tile([8.0, 40.0], [8.0, 40.0], model=_SelectedModel(12.0))

    shared = axes_for_tiles(YScalePolicy.SHARED_EXTRACT, (short, tall))
    assert shared[0].unscaled_max == 40.0
    assert shared[1].unscaled_max == 40.0

    per_peak = axes_for_tiles(YScalePolicy.PER_TILE_SELECTED_PEAK, (short, tall))
    assert per_peak[0].unscaled_max == 7.0
    assert per_peak[1].unscaled_max == 12.0
