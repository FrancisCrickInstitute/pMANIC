import threading
import time
import zlib

import numpy as np
import pytest
from PySide6.QtCore import QTimer

from manic.io.compound_reader import read_compound_with_session
from manic.models import database
from manic.processors import chromatographic_peak_deconvolution as deconvolution
from manic.processors.display_deconvolution import plot_display
from manic.processors.eic_processing import get_eics_for_compound
from manic.processors.tile_y_scale import TileScaleInput, axes_for_tiles
from manic.ui.graphs import GraphView
from manic.ui.isotopologue_ratio_widget import IsotopologueRatioWidget

from conftest import _gaussian, _make_window

SAMPLES = ["S1", "S2", "S3"]


def _insert(compound: str, rt: float, heights: list[float]) -> None:
    time_axis = np.linspace(0.0, 10.0, 201)
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms, int_std_amount) VALUES (?, ?, 1.0, 1.0, 217.0, 1, 1.0)",
            (compound, rt),
        )
        for sample, height in zip(SAMPLES, heights):
            m0 = _gaussian(time_axis, rt - 0.4, 0.2, height) + _gaussian(
                time_axis, rt, 0.25, 2 * height
            )
            m1 = 0.3 * m0
            conn.execute(
                "INSERT OR IGNORE INTO samples (sample_name, file_name) VALUES (?, ?)",
                (sample, f"/fake/{sample}.cdf"),
            )
            conn.execute(
                "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
                "VALUES (?, ?, ?, ?, 2.0)",
                (
                    sample,
                    compound,
                    zlib.compress(time_axis.tobytes()),
                    zlib.compress(np.vstack([m0, m1]).ravel().tobytes()),
                ),
            )


@pytest.fixture
def gated_fits(monkeypatch):
    """Count optimizer runs per thread; hold worker-thread fits until the gate opens."""
    deconvolution._fit_single_component_model_cached.cache_clear()
    deconvolution._fit_joint_component_model_cached.cache_clear()
    gate = threading.Event()
    calls = {"gui": 0, "worker": 0}
    real = deconvolution.least_squares

    def counted(*args, **kwargs):
        if threading.current_thread() is threading.main_thread():
            calls["gui"] += 1
        else:
            calls["worker"] += 1
            assert gate.wait(30), "test never opened the fit gate"
        return real(*args, **kwargs)

    monkeypatch.setattr(deconvolution, "least_squares", counted)
    yield gate, calls
    gate.set()


@pytest.fixture
def window(qapp, monkeypatch):
    _insert("Alpha", 5.0, [100.0, 140.0, 80.0])
    _insert("Beta", 6.0, [60.0, 90.0, 120.0])
    window = _make_window(monkeypatch)
    window.resize(1200, 800)
    window.show()
    yield window
    window.graph_view.cancel_fits()
    window.close()
    qapp.processEvents()


def _wait_for_fits(qapp, window, timeout=30.0):
    deadline = time.monotonic() + timeout
    while window.graph_view.fits_pending:
        assert time.monotonic() < deadline, "fits did not finish"
        qapp.processEvents()
        time.sleep(0.005)
    qapp.processEvents()


def _navigate(window, compound):
    window.toolbar.update_compound_list(["Alpha", "Beta"])
    window.toolbar.update_sample_list(SAMPLES)
    window.toolbar.compound_list.setCurrentRow(["Alpha", "Beta"].index(compound))


def _chart_snapshot(chart_view):
    chart = chart_view.chart()
    series = [
        (type(s).__name__, s.name(), [(p.x(), p.y()) for p in s.points()])
        for s in chart.series()
        if hasattr(s, "points")
    ]
    y_axis = chart.axes()[1]
    return chart_view.sample_name, series, (y_axis.min(), y_axis.max())


def _synchronous_tiles(window, compound):
    """Tiles as the synchronous plot path drew them: fit, scale, then build."""
    graph = window.graph_view
    eics = get_eics_for_compound(compound, SAMPLES, use_corrected=False)
    compounds = [read_compound_with_session(compound, eic.sample_name) for eic in eics]
    inputs = [
        TileScaleInput(
            prepared=plot_display(eic.time, eic.intensity, c, use_corrected=graph.use_corrected),
            raw_intensity=eic.intensity,
            independent_channels=c.is_unlabelled_target,
        )
        for eic, c in zip(eics, compounds)
    ]
    reference = GraphView()
    reference._sample_fit_types = graph._sample_fit_types
    axes = axes_for_tiles(graph._y_scale_policy, inputs)
    try:
        return [
            _chart_snapshot(reference._build_plot(eic, axis_scale=axis))
            for eic, axis in zip(eics, axes)
        ]
    finally:
        reference.deleteLater()


def _synchronous_ratios(compound):
    widget = IsotopologueRatioWidget()
    try:
        widget.update_ratios(compound, get_eics_for_compound(compound, SAMPLES))
        return widget._current_ratios
    finally:
        widget.deleteLater()


def test_compound_navigation_returns_to_event_loop_before_fits_finish(
    qapp, window, gated_fits
):
    gate, calls = gated_fits

    _navigate(window, "Beta")

    assert calls["gui"] == 0
    graph = window.graph_view
    assert graph.get_current_compound() == "Beta"
    assert len(graph._current_plots) == len(SAMPLES)
    assert all(plot.chart().series() for plot in graph._current_plots)

    beats = []
    QTimer.singleShot(0, lambda: beats.append(graph.fits_pending))
    deadline = time.monotonic() + 5
    while not beats and time.monotonic() < deadline:
        qapp.processEvents()
    assert beats == [True]
    raw_tiles = [_chart_snapshot(p) for p in graph._current_plots]

    gate.set()
    _wait_for_fits(qapp, window)
    assert calls["gui"] == 0
    assert calls["worker"] >= len(SAMPLES)
    fitted_tiles = [_chart_snapshot(p) for p in graph._current_plots]
    assert all(raw != fitted for raw, fitted in zip(raw_tiles, fitted_tiles))


def test_results_for_a_compound_left_mid_fit_are_dropped(qapp, window, gated_fits):
    gate, _calls = gated_fits

    _navigate(window, "Alpha")
    window.toolbar.compound_list.setCurrentRow(1)
    gate.set()
    _wait_for_fits(qapp, window)

    graph = window.graph_view
    assert graph.get_current_compound() == "Beta"
    assert {p.compound_name for p in graph._current_plots} == {"Beta"}
    assert [_chart_snapshot(p) for p in graph._current_plots] == _synchronous_tiles(
        window, "Beta"
    )
    np.testing.assert_array_equal(
        window.toolbar.isotopologue_ratios._current_ratios, _synchronous_ratios("Beta")
    )
