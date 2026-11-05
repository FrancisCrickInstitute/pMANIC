from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QToolTip, QVBoxLayout, QWidget

from manic.ui import theme
from manic.ui.isotopologue_ratio_widget import IsotopologueRatioWidget
from manic.ui.sidebar_widgets import SUMMARY_SHORT_ROWS, NAME_ROW_PX
from manic.ui.total_abundance_widget import TotalAbundanceWidget

NAMES = [f"Bio_{i:03d}" for i in range(30)]


def _abundance(names):
    widget = TotalAbundanceWidget()
    widget.update_abundance_from_data(
        "Alanine",
        [SimpleNamespace(sample_name=n) for n in names],
        np.arange(1, len(names) + 1, dtype=float) * 1e6,
    )
    return widget


def _ratios(names, ratios=None):
    widget = IsotopologueRatioWidget()
    if ratios is None:
        ratios = np.tile([0.6, 0.3, 0.1], (len(names), 1))
    widget._current_sample_names = names[::-1]
    widget._current_ratios = ratios
    widget._update_chart(ratios, names[::-1])
    return widget


def _pump():
    for _ in range(10):
        QApplication.processEvents()


@pytest.mark.parametrize("make", [_abundance, _ratios])
def test_value_axis_stays_in_view_while_rows_scroll(qapp, make):
    widget = make(NAMES)
    try:
        widget.resize(264, 300)
        widget.show()
        _pump()
        bar = widget.chart_area.verticalScrollBar()
        assert bar.maximum() > 0
        ticks = widget.value_axis.tick_positions()
        assert ticks and widget.value_axis.isVisible()
        bar.setValue(bar.maximum())
        _pump()
        # Pinned outside the scroll area, so still on screen and at the same x.
        assert widget.value_axis.isVisible()
        assert widget.value_axis.geometry().bottom() < widget.chart_area.geometry().top()
        assert widget.value_axis.tick_positions() == ticks
    finally:
        widget.deleteLater()


def test_two_summaries_share_a_short_sidebar_without_an_outer_scroll(qapp):
    host = QWidget()
    layout = QVBoxLayout(host)
    charts = [_ratios(NAMES), _abundance(NAMES)]
    for chart in charts:
        layout.addWidget(chart, 1)
    try:
        host.resize(264, 360)
        host.show()
        _pump()
        assert sum(c.minimumHeight() for c in charts) < 360
        for chart in charts:
            assert chart.chart_area.viewport().height() >= SUMMARY_SHORT_ROWS * NAME_ROW_PX - 4
        assert layout.geometry().height() <= 360
    finally:
        host.deleteLater()


def test_selection_leaves_other_bars_their_cohort_colours(qapp):
    widget = _ratios(NAMES[:5])
    try:
        widget.resize(264, 300)
        widget.show()
        _pump()
        widget.set_highlighted(["Bio_002"])
        assert widget.highlighted_bars() == ["Bio_002"]
        fills = {mark.brush().color().name() for mark in widget._marks}
        assert fills == {theme.color("accent_soft").name(), theme.color("accent").name()}
    finally:
        widget.deleteLater()


def test_a_sample_with_no_ratio_shows_a_dash_and_explains_on_hover(qapp, monkeypatch):
    names = ["Bio_001", "Bio_018", "Bio_020"]
    ratios = np.array([[0.6, 0.3, 0.1], [0.0, 0.0, 0.0], [0.5, 0.5, 0.0]])
    widget = _ratios(names, ratios)
    shown = []
    monkeypatch.setattr(QToolTip, "showText", lambda _pos, text, *_a: shown.append(text))
    try:
        widget.resize(264, 300)
        widget.show()
        _pump()
        # Rows are stored bottom-up: Bio_018 sits in the middle either way.
        assert widget.dash_rows() == ["Bio_018"]
        series = widget.chart.series()[0]
        point = widget.chart.mapToPosition(QPointF(0.5, 1), series)
        viewport = widget.chart_view.mapFromScene(widget.chart.mapToScene(point))
        assert widget.row_at(viewport) == 1
        event = QMouseEvent(
            QEvent.MouseMove, QPointF(viewport), QPointF(widget.chart_view.viewport().mapToGlobal(viewport)),
            Qt.NoButton, Qt.NoButton, Qt.NoModifier,
        )
        QApplication.sendEvent(widget.chart_view.viewport(), event)
        assert shown and shown[-1].startswith("Bio_018\nNo ratio")
    finally:
        widget.deleteLater()
