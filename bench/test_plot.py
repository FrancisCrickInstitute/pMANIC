from __future__ import annotations

from manic.io.list_compound_names import list_compound_names
from manic.io.sample_reader import list_active_samples
from manic.models.analysis import AnalysisContext
from manic.ui.main_window import MainWindow


def _make_window(case, qapp):
    MainWindow._check_for_updates = lambda self: None
    window = MainWindow(AnalysisContext(case.mode))
    names = list_compound_names()
    samples = list_active_samples()
    window.toolbar.update_compound_list(names)
    window.toolbar.update_sample_list(samples)
    window.resize(1600, 1000)
    window.show()
    qapp.processEvents()
    return window, names, samples


def _assert_grid(window, case, compound: str) -> None:
    assert window.graph_view.get_current_compound() == compound
    plots = window.graph_view._current_plots
    assert len(plots) == case.n_samples
    assert all(plot.chart().series() for plot in plots)
    if case.labelled:
        ratios = window.toolbar.isotopologue_ratios._current_ratios
        assert ratios is not None and ratios.shape[0] == case.n_samples
    else:
        abundances = window.toolbar.total_abundance._current_abundances
        assert abundances is not None and len(abundances) == case.n_samples


def test_plot_first(case, db, qapp, benchmark, repeat):
    """Cold first plot: a fresh window per round, so the tile pool and fit cache are empty."""
    windows = []

    def setup():
        window, names, samples = _make_window(case, qapp)
        windows.append((window, names))
        return (window, names[0], samples), {}

    def plot(window, name, samples):
        window.on_plot_button(name, samples)
        qapp.processEvents()

    try:
        benchmark.pedantic(plot, setup=setup, rounds=repeat)
        for window, names in windows:
            _assert_grid(window, case, names[0])
    finally:
        for window, _names in windows:
            window.close()
        qapp.processEvents()


def test_plot_next(case, db, qapp, navigation, benchmark):
    """Move to the next compound in the list. One round per move; the grid is checked between moves."""
    window, names, samples = _make_window(case, qapp)
    window.on_plot_button(names[0], samples)
    qapp.processEvents()
    pending = iter(navigation)
    shown = [0]

    def setup():
        _assert_grid(window, case, names[shown[-1]])
        index = next(pending)
        shown.append(index)
        return (index,), {}

    def navigate(index):
        window.toolbar.compound_list.setCurrentRow(index)
        qapp.processEvents()

    try:
        benchmark.pedantic(navigate, setup=setup, rounds=len(navigation))
        _assert_grid(window, case, names[shown[-1]])
    finally:
        window.close()
        qapp.processEvents()
