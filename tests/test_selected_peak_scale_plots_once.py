import zlib

import numpy as np
import pytest

from conftest import _gaussian, _make_window
from manic.models import database
from manic.processors.tile_y_scale import YScalePolicy


@pytest.fixture
def window(qapp, monkeypatch):
    """A (deconvolution on) is shown scaled to its selected peak; B has deconvolution off."""
    time = np.linspace(4.0, 6.0, 201)
    intensity = _gaussian(time, 5.0, 0.03, 1e5)
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO samples (sample_name, file_name) VALUES ('S1', '/fake/S1.cdf')"
        )
        for name, level in (("A", "4"), ("B", "off")):
            conn.execute(
                "INSERT INTO compounds (compound_name, retention_time, loffset, "
                "roffset, mass0, label_atoms, deconvolution_level) "
                "VALUES (?, 5.0, 0.1, 0.1, 100.0, 0, ?)",
                (name, level),
            )
            conn.execute(
                "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis) "
                "VALUES ('S1', ?, ?, ?)",
                (name, zlib.compress(time.tobytes()), zlib.compress(intensity.tobytes())),
            )
    window = _make_window(monkeypatch)
    window.cdf_data_loaded = window.compound_data_loaded = True
    window.toolbar.update_sample_list(["S1"])
    window.toolbar.update_compound_list(["A", "B"], "A")
    window.toolbar.selected_peak_yscale_action.trigger()
    yield window
    window.close()


def _record_plots(window, monkeypatch):
    view = window.graph_view
    plotted = []
    real_plot = view.plot_compound

    def record(compound_name, *args, **kwargs):
        plotted.append((compound_name, view._y_scale_policy))
        return real_plot(compound_name, *args, **kwargs)

    monkeypatch.setattr(view, "plot_compound", record)
    return plotted


def test_switching_to_compound_without_deconvolution_plots_it_once(window, monkeypatch):
    plotted = _record_plots(window, monkeypatch)

    window.toolbar.compound_list.setCurrentRow(1)

    assert plotted == [("B", YScalePolicy.PER_TILE_EXTRACT)]
    assert not window.toolbar.selected_peak_yscale_action.isChecked()


def test_turning_deconvolution_off_plots_the_compound_once(window, monkeypatch):
    plotted = _record_plots(window, monkeypatch)

    window.apply_deconvolution("A", "off", "auto", "balanced", False)

    assert plotted == [("A", YScalePolicy.PER_TILE_EXTRACT)]
    assert not window.toolbar.selected_peak_yscale_action.isChecked()
