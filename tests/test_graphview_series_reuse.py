from __future__ import annotations

import zlib

import numpy as np
import pytest

from manic.models import database
from manic.ui.graphs import GraphView


def _seed_two_compounds() -> list[str]:
    time = np.linspace(4.5, 5.5, 81, dtype=np.float64)
    samples = ["S1", "S2"]
    with database.get_connection() as conn:
        for s in samples:
            conn.execute("INSERT INTO samples (sample_name) VALUES (?)", (s,))
        # Multi-channel labelled compound (4 isotopologues -> more series)
        conn.execute(
            """
            INSERT INTO compounds (
                compound_name, retention_time, loffset, roffset, mass0,
                label_atoms, formula, deconvolution_level, baseline_correction
            ) VALUES ('Multi', 5.0, 0.15, 0.15, 200.0, 3, 'C3H7NO2', 'off', 1)
            """
        )
        # Single-channel compound (fewer series)
        conn.execute(
            """
            INSERT INTO compounds (
                compound_name, retention_time, loffset, roffset, mass0,
                label_atoms, formula, deconvolution_level, baseline_correction
            ) VALUES ('Single', 5.0, 0.15, 0.15, 150.0, 0, NULL, 'off', 1)
            """
        )
        peak = 1000.0 * np.exp(-0.5 * ((time - 5.0) / 0.04) ** 2)
        multi_y = np.vstack([peak, 0.4 * peak, 0.2 * peak, 0.05 * peak]).astype(np.float64)
        single_y = peak.astype(np.float64)
        for s in samples:
            conn.execute(
                "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
                "VALUES (?, 'Multi', ?, ?, 0.5)",
                (s, zlib.compress(time.tobytes()), zlib.compress(multi_y.tobytes())),
            )
            conn.execute(
                "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
                "VALUES (?, 'Single', ?, ?, 0.5)",
                (s, zlib.compress(time.tobytes()), zlib.compress(single_y.tobytes())),
            )
    return samples


def _visible_series_signature(chart):
    return [
        (
            series.name(),
            series.property("guide_role"),
            series.pen().color().getRgb(),
            series.pen().style(),
            round(series.pen().widthF(), 2),
            [(round(p.x(), 6), round(p.y(), 6)) for p in series.points()],
        )
        for series in chart.series()
        if series.isVisible()
    ]


def test_graphview_reuses_qline_series_and_hides_spares_matching_cold_plot(qapp, empty_db):
    samples = _seed_two_compounds()

    # Cold reference for Single on a brand-new GraphView
    cold = GraphView()
    cold.plot_compound("Single", samples)
    expected_by_sample = {
        plot.sample_name: _visible_series_signature(plot.chart())
        for plot in cold._current_plots
    }

    # Reused GraphView: Multi (more series) -> Single (fewer series) -> Multi
    view = GraphView()
    view.plot_compound("Multi", samples)
    multi_series_ids = {
        plot.sample_name: [id(s) for s in plot.chart().series()]
        for plot in view._current_plots
    }
    first_pool_len = len(multi_series_ids["S1"])
    assert first_pool_len > len(expected_by_sample["S1"])

    view.plot_compound("Single", samples)
    for plot in view._current_plots:
        chart = plot.chart()
        # No new QLineSeries created when switching to a smaller-series compound
        assert len(chart.series()) == first_pool_len
        visible = [s for s in chart.series() if s.isVisible()]
        hidden = [s for s in chart.series() if not s.isVisible()]
        assert len(hidden) == first_pool_len - len(visible)
        for spare in hidden:
            assert spare.count() == 0
            assert spare.name() == ""
            assert spare.property("guide_role") is None
        assert _visible_series_signature(chart) == expected_by_sample[plot.sample_name]

    # Switching back to Multi reuses the exact same pooled series objects
    all_before = {id(s) for plot in view._current_plots for s in plot.chart().series()}
    view.plot_compound("Multi", samples)
    all_after = {id(s) for plot in view._current_plots for s in plot.chart().series()}
    assert all_after == all_before


def test_graphview_restores_updates_enabled_after_error(qapp, empty_db, monkeypatch):
    samples = _seed_two_compounds()
    view = GraphView()
    grid_host = view._scroll.widget()
    assert grid_host.updatesEnabled()

    monkeypatch.setattr(
        "manic.ui.graphs.get_eics_for_compound",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(RuntimeError, match="boom"):
        view.plot_compound("Single", samples)
    assert grid_host.updatesEnabled()
