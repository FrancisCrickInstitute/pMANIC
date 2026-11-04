from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QPoint

from manic.io.compound_reader import Compound
from manic.processors.tile_y_scale import YScalePolicy
from manic.ui.graphs import GraphView


def _compound():
    return Compound(
        compound_name="Valine",
        retention_time=7.09,
        loffset=0.08,
        roffset=0.035,
        label_atoms=1,
        mass0=174.0,
        baseline_correction=0,
    )


def _eic(sample: str, compound: str):
    time = np.linspace(6.9, 7.3, 81)
    peak = np.exp(-0.5 * ((time - 7.09) / 0.02) ** 2)
    return SimpleNamespace(
        sample_name=sample,
        compound_name=compound,
        time=time,
        intensity=np.vstack([1e6 * peak, 4e5 * peak]),
    )


@pytest.fixture
def grid(qapp, monkeypatch):
    monkeypatch.setattr(
        "manic.ui.graphs.get_eics_for_compound",
        lambda compound, samples, use_corrected=False: [_eic(s, compound) for s in samples],
    )
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session", lambda _name, sample=None: _compound()
    )
    monkeypatch.setattr("manic.ui.graphs.get_sample_fit_types", lambda _name: {})
    view = GraphView()
    view.resize(900, 700)
    yield view
    view.deleteLater()


def test_replotting_the_same_compound_keeps_selection_and_focus(grid):
    grid.plot_compound("Valine", ["S1", "S2", "S3", "S4"])
    grid.select_samples(["S2", "S4"])
    grid._focus_on(3)
    emitted = []
    grid.selection_changed.connect(emitted.append)

    grid.set_y_scale_policy(YScalePolicy.SHARED_EXTRACT)
    assert grid.get_selected_samples() == ["S2", "S4"]
    assert grid._focused_plot().sample_name == "S4"
    assert [p.is_selected for p in grid._current_plots] == [False, True, False, True]
    assert grid.selection_summary.text().endswith("2 of 4 selected")
    assert emitted == []

    # A curve-fit change re-plots through plot_compound with the same arguments.
    grid.plot_compound("Valine", ["S1", "S2", "S3", "S4"])
    assert grid.get_selected_samples() == ["S2", "S4"]


def test_replotting_drops_only_the_samples_no_longer_shown(grid):
    grid.plot_compound("Valine", ["S1", "S2", "S3", "S4"])
    grid.select_samples(["S2", "S4"])
    grid._focus_on(3)
    emitted = []
    grid.selection_changed.connect(emitted.append)

    grid.plot_compound("Valine", ["S1", "S2", "S3"])
    assert grid.get_selected_samples() == ["S2"]
    assert grid._focused_plot() is None
    assert emitted == [["S2"]]


def test_switching_compound_starts_with_no_selection(grid):
    grid.plot_compound("Valine", ["S1", "S2", "S3"])
    grid.select_samples(["S2"])
    grid.plot_compound("Leucine", ["S1", "S2", "S3"])
    assert grid.get_selected_samples() == []
    assert not any(p.is_selected for p in grid._current_plots)


def test_context_menu_matches_the_review_menu_order(grid):
    grid.plot_compound("Valine", ["S1", "S2"])
    plot = grid._current_plots[0]
    grid._show_context_menu(QPoint(0, 0), plot)
    menu = grid._active_context_menu
    texts = [a.text() or "|" for a in menu.actions()]
    menu.close()
    assert texts == [
        "Inspect S1...",
        "|",
        "Select All Plots",
        "Deselect All",
        "Select Only This Sample",
        "Show Only Selected Samples",
        "Show All Samples",
        "|",
        "Accept Peak (Below Threshold)",
        "Mark Peak as Bad",
        "Curve Fit",
    ]


def test_density_sets_chart_text_size(grid):
    grid.set_density("compact")
    grid.plot_compound("Valine", ["S1", "S2"])
    tile = grid._current_plots[0].parent()

    def sizes():
        axes = tile.chart_view.chart().axes()
        return (
            {axis.labelsFont().pixelSize() for axis in axes},
            tile.caption.styleSheet().count("font-size: 12px"),
        )

    assert sizes() == ({10}, 1)
    grid.set_density("comfortable")
    assert {a.labelsFont().pixelSize() for a in tile.chart_view.chart().axes()} == {11}
    assert "font-size: 13px" in tile.caption.styleSheet()
    assert "font-size: 11px" in tile.scale_label.styleSheet()
