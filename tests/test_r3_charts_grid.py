from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from manic.io.compound_reader import Compound
from manic.ui.channel_chips import ChannelChipRow
from manic.ui.colors import ChannelTraceStyle, label_colors
from manic.ui.graphs import GraphView, retention_time_text
from manic.ui.plot_tile import PEAK_BADGES, PlotTile
from manic.validation.peak_verdict import PeakVerdict


def test_retention_time_text_matches_the_sidebar_rounding():
    assert retention_time_text([7.09, 7.09]) == "tR 7.09"
    assert retention_time_text([7.2]) == "tR 7.2"
    assert retention_time_text([7.05, 7.1234]) == "tR 7.05–7.123"
    assert retention_time_text([]) == ""


def _compound(rt: float) -> Compound:
    return Compound(
        compound_name="Pyruvate",
        retention_time=rt,
        loffset=0.08,
        roffset=0.035,
        label_atoms=1,
        mass0=174.0,
        baseline_correction=0,
    )


def _eic(sample: str):
    time = np.linspace(6.9, 7.3, 81)
    peak = np.exp(-0.5 * ((time - 7.09) / 0.02) ** 2)
    return SimpleNamespace(
        sample_name=sample,
        compound_name="Pyruvate",
        time=time,
        intensity=np.vstack([1e6 * peak, 4e5 * peak]),
    )


@pytest.fixture
def plotted_grid(qapp, monkeypatch):
    rts = {"S1": 7.09, "S2": 7.09, "S3": 7.09}
    monkeypatch.setattr(
        "manic.ui.graphs.get_eics_for_compound",
        lambda _compound, samples, use_corrected=False: [_eic(s) for s in samples],
    )
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session",
        lambda _name, sample=None: _compound(rts.get(sample, 7.09)),
    )
    monkeypatch.setattr("manic.ui.graphs.get_sample_fit_types", lambda _name: {})
    view = GraphView()
    yield view, rts
    view.deleteLater()


def test_grid_header_names_the_compound_with_tr_and_count(plotted_grid):
    view, rts = plotted_grid
    view.plot_compound("Pyruvate", ["S1", "S2", "S3"])
    assert not view.compound_title.isHidden()
    assert view.compound_title.text() == "Pyruvate"
    assert view.selection_summary.text() == "tR 7.09 · 3 samples"

    view.select_samples(["S2"])
    assert view.selection_summary.text() == "tR 7.09 · 1 of 3 selected"

    rts["S3"] = 7.12
    view.plot_compound("Pyruvate", ["S1", "S2", "S3"])
    assert view.selection_summary.text() == "tR 7.09–7.12 · 1 of 3 selected"

    view.clear_all_plots()
    assert view.compound_title.isHidden()
    assert view.selection_summary.text() == ""


class _FakeChart:
    def __init__(self, sample: str, container: QWidget):
        self.sample_name = sample
        self.compound_name = "Cmp"
        self._container = container

    def parent(self) -> QWidget:
        return self._container


def _menu_texts(view: GraphView, chart) -> list[str]:
    view._show_context_menu(QPoint(0, 0), chart)
    menu = view._active_context_menu
    texts = [action.text() for action in menu.actions() if action.text()]
    menu.close()
    return texts


@pytest.fixture
def review_grid(qapp):
    view = GraphView()
    charts = {}
    for sample in ("A", "B", "C"):
        tile = PlotTile(QWidget())
        chart = _FakeChart(sample, tile)
        tile.chart_view = chart
        charts[sample] = chart
    view._current_plots = list(charts.values())
    view.apply_peak_verdicts(
        {"A": PeakVerdict.FAIL, "B": PeakVerdict.FAIL, "C": PeakVerdict.PASS}
    )
    yield view, charts
    view.deleteLater()


def test_review_commands_name_how_many_plots_they_change(review_grid):
    view, charts = review_grid
    view._selected_plots = set(charts.values())
    texts = _menu_texts(view, charts["A"])
    # Accept skips the passing tile C, so it targets two of the three.
    assert "Accept 2 Peaks (Below Threshold)" in texts
    assert "Mark 3 Peaks as Bad" in texts
    assert "Curve Fit for 3 Samples" in texts


def test_review_commands_stay_singular_for_one_plot(review_grid):
    view, charts = review_grid
    view._selected_plots = {charts["A"], charts["B"]}
    texts = _menu_texts(view, charts["C"])
    assert "Accept Peak (Below Threshold)" in texts
    assert "Mark Peak as Bad" in texts
    assert "Curve Fit" in texts


def test_chip_row_wraps_before_truncating_a_chip(qapp):
    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    row = ChannelChipRow()
    layout.addWidget(row)
    layout.addStretch()
    labels = [f"M+{i} m/z {174 + i}" for i in range(4)]
    row.set_channels(labels, [ChannelTraceStyle(c, Qt.SolidLine) for c in label_colors[:4]])
    try:
        host.resize(260, 200)
        host.show()
        qapp.processEvents()
        chips = row.chips()
        assert [chip.width() for chip in chips] == [chip.sizeHint().width() for chip in chips]
        assert len({chip.y() for chip in chips}) == 2
        assert row.height() >= 2 * chips[0].height()
    finally:
        host.deleteLater()


def test_badges_move_below_a_caption_they_would_cut_off(qapp):
    tile = PlotTile(QWidget())
    tile.set_caption("Sample_05_rt_shift")
    tile.set_badges([PEAK_BADGES[PeakVerdict.FAIL]])
    try:
        tile.resize(200, 150)
        tile.show()
        qapp.processEvents()
        assert not tile.badges_inline()
        assert tile.caption.text() == "Sample_05_rt_shift"

        tile.resize(600, 300)
        qapp.processEvents()
        assert tile.badges_inline()
    finally:
        tile.deleteLater()
