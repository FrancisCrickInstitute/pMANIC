import time
import zlib
from unittest.mock import Mock

import numpy as np
import pytest

from manic.models import database
from manic.processors.display_deconvolution import integrated_display_areas

from conftest import _gaussian, _make_window

SAMPLES = ["S1", "S2", "S3"]


def _seed(compound: str, label_atoms: int) -> None:
    time = np.linspace(0.0, 2.0, 81)
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES (?, 1.0, 0.4, 0.4, 100.0, ?)",
            (compound, label_atoms),
        )
        for i, sample in enumerate(SAMPLES):
            peak = _gaussian(time, 1.0, 0.08, 1000.0 * (i + 1))
            matrix = np.vstack([peak * (0.5**k) for k in range(label_atoms + 1)])
            conn.execute(
                "INSERT OR IGNORE INTO samples (sample_name, file_name) VALUES (?, ?)",
                (sample, f"/fake/{sample}.cdf"),
            )
            conn.execute(
                "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
                "VALUES (?, ?, ?, ?, 0.6)",
                (
                    sample,
                    compound,
                    zlib.compress(time.tobytes()),
                    zlib.compress(matrix.ravel().tobytes()),
                ),
            )


@pytest.mark.parametrize(("compound", "label_atoms"), [("Lactate", 2), ("Urea", 0)])
def test_tile_selection_keeps_summary_charts(qapp, monkeypatch, compound, label_atoms):
    _seed(compound, label_atoms)
    window = _make_window(monkeypatch)
    calls = Mock(wraps=integrated_display_areas)
    monkeypatch.setattr(
        "manic.ui.isotopologue_ratio_widget.integrated_display_areas", calls
    )
    try:
        window.on_plot_button(compound, SAMPLES)
        # Tile fits run off the GUI thread; the summary charts fill when they land.
        deadline = time.monotonic() + 30
        while window.graph_view.fits_pending and time.monotonic() < deadline:
            qapp.processEvents()
        qapp.processEvents()
        assert calls.call_count == len(SAMPLES)
        ratios = window.toolbar.isotopologue_ratios._current_ratios
        totals = window.toolbar.total_abundance._current_abundances.copy()
        assert totals.shape == (len(SAMPLES),)
        assert np.all(totals > 0)

        calls.reset_mock()
        assert window.graph_view.select_sample("S2")
        window.graph_view.select_all_plots()
        window.graph_view.clear_selection()

        assert calls.call_count == 0
        assert window.toolbar.isotopologue_ratios._current_ratios is ratios
        np.testing.assert_array_equal(
            window.toolbar.total_abundance._current_abundances, totals
        )
    finally:
        window.close()
        window.deleteLater()
