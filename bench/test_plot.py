from __future__ import annotations

import re

import pytest
from PySide6.QtCore import QEventLoop

from manic.io.list_compound_names import list_compound_names
from manic.io.sample_reader import list_active_samples
from manic.models.analysis import AnalysisContext
from manic.processors.chromatographic_peak_deconvolution import (
    _fit_joint_component_model_cached,
    _fit_single_component_model_cached,
)
from manic.ui.main_window import MainWindow
from manic.utils.utils import apply_app_stylesheet


def _clear_fit_caches() -> None:
    _fit_single_component_model_cached.cache_clear()
    _fit_joint_component_model_cached.cache_clear()


def _wait_for_fits(window, qapp) -> None:
    """Block until the tile fit worker finishes, so timings cover the fitted grid."""
    graph = window.graph_view
    if graph.fits_pending:
        loop = QEventLoop()
        graph.fits_finished.connect(loop.quit)
        loop.exec()
        graph.fits_finished.disconnect(loop.quit)
    qapp.processEvents()


def _make_window(case, qapp):
    MainWindow._check_for_updates = lambda self: None
    apply_app_stylesheet(qapp)
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


@pytest.fixture(scope="module")
def navigation_window(case, db, qapp):
    _clear_fit_caches()
    window, names, samples = _make_window(case, qapp)
    window.on_plot_button(names[0], samples)
    _wait_for_fits(window, qapp)
    try:
        yield window, names
    finally:
        window.close()
        qapp.processEvents()


def test_plot_first(case, db, qapp, benchmark, repeat):
    """Cold first plot: a fresh window per round, so the tile pool and fit cache are empty."""
    windows = []

    def setup():
        _clear_fit_caches()
        window, names, samples = _make_window(case, qapp)
        windows.append((window, names))
        return (window, names[0], samples), {}

    def plot(window, name, samples):
        window.on_plot_button(name, samples)
        _wait_for_fits(window, qapp)

    try:
        benchmark.pedantic(plot, setup=setup, rounds=repeat)
        for window, names in windows:
            _assert_grid(window, case, names[0])
    finally:
        for window, _names in windows:
            window.close()
        qapp.processEvents()


def test_plot_next(
    case,
    qapp,
    navigation_window,
    navigation_index,
    benchmark,
    repeat,
):
    """Time one identified compound so isolated navigation regressions fail."""
    window, names = navigation_window
    target_name = names[navigation_index]
    # Compound names come from the DB, which may not exist at collection time,
    # so the row label is set here rather than via a parametrize id.
    target_id = re.sub(r"[^a-z0-9]+", "-", target_name.lower()).strip("-")
    benchmark.name = f"{benchmark.name}-{target_id}"
    benchmark.fullname = f"{benchmark.fullname}-{target_id}"
    benchmark.extra_info["compound"] = target_name
    benchmark.extra_info["compound_index"] = navigation_index

    def setup():
        source_name = window.graph_view.get_current_compound()
        if source_name == target_name:
            window.toolbar.compound_list.setCurrentRow(0)
            _wait_for_fits(window, qapp)
            source_name = names[0]
        _assert_grid(window, case, source_name)
        if repeat > 1:
            _clear_fit_caches()
        return (navigation_index,), {}

    def navigate(index):
        window.toolbar.compound_list.setCurrentRow(index)
        _wait_for_fits(window, qapp)

    benchmark.pedantic(navigate, setup=setup, rounds=repeat)
    _assert_grid(window, case, target_name)
