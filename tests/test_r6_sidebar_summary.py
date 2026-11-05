from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from manic.ui.isotopologue_ratio_widget import IsotopologueRatioWidget
from manic.ui.sidebar_widgets import NAME_ROW_PX, SUMMARY_CHART_MAX_HEIGHT
from manic.ui.total_abundance_widget import TotalAbundanceWidget

NAMES = [f"Bio_{i:03d}" for i in range(30)]


def _eics(names):
    return [SimpleNamespace(sample_name=name) for name in names]


def _abundance(names):
    widget = TotalAbundanceWidget()
    widget.update_abundance_from_data(
        "Alanine", _eics(names), np.arange(1, len(names) + 1, dtype=float) * 1e6
    )
    return widget


def _ratios(names):
    widget = IsotopologueRatioWidget()
    ratios = np.tile([0.6, 0.3, 0.1], (len(names), 1))
    # The widget orders bars like the grid by reversing; mirror what update_ratios stores.
    widget._current_sample_names = names[::-1]
    widget._current_ratios = ratios
    widget._update_chart(ratios, names[::-1])
    return widget


def _row_in_view(widget, name) -> bool:
    index = widget._current_sample_names.index(name)
    y = widget.chart.mapToPosition(QPointF(0, index), widget.chart.series()[0]).y()
    top = widget.chart_area.verticalScrollBar().value()
    return top <= y <= top + widget.chart_area.viewport().height()


def _shown(widget):
    widget.resize(264, SUMMARY_CHART_MAX_HEIGHT)
    widget.show()
    for _ in range(10):
        QApplication.processEvents()
    return widget


@pytest.mark.parametrize("make", [_abundance, _ratios])
def test_thirty_samples_are_named_on_readable_rows_that_scroll(qapp, make):
    widget = _shown(make(NAMES))
    try:
        axis = widget.chart.axes(Qt.Vertical)[0]
        assert axis.labelsVisible()
        assert list(axis.categories())[::-1][0] == "Bio_000"
        assert widget.chart.plotArea().height() >= len(NAMES) * NAME_ROW_PX
        assert widget.height() <= SUMMARY_CHART_MAX_HEIGHT
        assert widget.chart_area.verticalScrollBar().maximum() > 0
    finally:
        widget.deleteLater()


@pytest.mark.parametrize("make", [_abundance, _ratios])
def test_a_few_samples_fit_without_scrolling(qapp, make):
    widget = _shown(make(NAMES[:3]))
    try:
        assert widget.chart.axes(Qt.Vertical)[0].labelsVisible()
        assert widget.chart_area.verticalScrollBar().maximum() == 0
    finally:
        widget.deleteLater()


@pytest.mark.parametrize("make", [_abundance, _ratios])
def test_selecting_a_sample_scrolls_its_row_into_view(qapp, make):
    widget = _shown(make(NAMES))
    try:
        bar = widget.chart_area.verticalScrollBar()
        bar.setValue(0)
        assert not _row_in_view(widget, "Bio_029")
        widget.set_highlighted(["Bio_029"])
        assert widget.highlighted_bars() == ["Bio_029"]
        assert _row_in_view(widget, "Bio_029")
        widget.set_highlighted(["Bio_000"])
        assert _row_in_view(widget, "Bio_000")
        assert not _row_in_view(widget, "Bio_029")
    finally:
        widget.deleteLater()
