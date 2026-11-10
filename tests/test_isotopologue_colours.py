from types import SimpleNamespace

import numpy as np

from manic.models.analysis import labelled_channels
from manic.ui.colors import channel_trace_styles
from manic.ui.isotopologue_ratio_widget import IsotopologueRatioWidget

# The Add compound dialog allows up to 100 label atoms.
MAX_LABEL_ATOMS = 100


def test_every_isotopologue_has_its_own_colour(qapp, monkeypatch):
    module = "manic.ui.isotopologue_ratio_widget"
    monkeypatch.setattr(f"{module}.read_compound_with_session", lambda _compound, _sample: None)
    monkeypatch.setattr(
        f"{module}.integrated_display_areas",
        lambda _time, intensity, _compound, use_corrected: list(intensity.sum(axis=1)),
    )
    count = MAX_LABEL_ATOMS + 1
    eic = SimpleNamespace(sample_name="Bio_001", time=np.zeros(1), intensity=np.ones((count, 1)))

    chart = IsotopologueRatioWidget()
    chart.update_ratios("Melatonin", [eic])
    bars = chart.chart.series()[0].barSets()
    tiles = channel_trace_styles(labelled_channels(100.0, MAX_LABEL_ATOMS), None)

    assert len({bar.color().name() for bar in bars}) == count
    assert len({style.color.name() for style in tiles}) == count
