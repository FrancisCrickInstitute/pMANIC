from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QFontMetrics, QMouseEvent, QTextDocumentFragment
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from manic.ui import theme
from manic.ui.isotopologue_ratio_widget import IsotopologueRatioWidget
from manic.ui.total_abundance_widget import TotalAbundanceWidget

NAMES = [f"Bio_{i:03d}" for i in range(30)]


@pytest.fixture(autouse=True)
def integration(monkeypatch):
    """Integrating an EIC gives the sums of its intensity rows, one per isotopologue."""
    module = "manic.ui.isotopologue_ratio_widget"
    monkeypatch.setattr(f"{module}.read_compound_with_session", lambda _compound, _sample: None)
    monkeypatch.setattr(
        f"{module}.integrated_display_areas",
        lambda _time, intensity, _compound, use_corrected: list(intensity.sum(axis=1)),
    )


def _eics(names, areas=None):
    if areas is None:
        areas = [[0.6, 0.3, 0.1]] * len(names)
    return [
        SimpleNamespace(
            sample_name=name, time=np.zeros(1), intensity=np.asarray(area, dtype=float)[:, None]
        )
        for name, area in zip(names, areas)
    ]


def _ratios(names, areas=None):
    widget = IsotopologueRatioWidget()
    widget.update_ratios("Alanine", _eics(names, areas))
    return widget


def _abundance(names, values=None):
    widget = TotalAbundanceWidget()
    if values is None:
        values = np.arange(1, len(names) + 1, dtype=float) * 1e6
    widget.update_abundance_from_data("Alanine", _eics(names), np.asarray(values, dtype=float))
    return widget


def _shown(widget, height=330):
    widget.resize(264, height)
    widget.show()
    for _ in range(10):
        QApplication.processEvents()
    return widget


def _category(widget, point) -> str:
    value = widget.chart.mapToValue(point, widget.chart.series()[0])
    return widget.chart.axes(Qt.Vertical)[0].categories()[round(value.y())]


def _selected(widget) -> list[str]:
    """Samples whose bars carry the selection mark, top to bottom."""
    if isinstance(widget, TotalAbundanceWidget):
        bars = widget.chart.series()[0].barSets()[0]
        names = widget.chart.axes(Qt.Vertical)[0].categories()
        return [names[i] for i in sorted(bars.selectedBars(), reverse=True)]
    ticks = [
        item for item in widget.chart.childItems()
        if isinstance(item, QGraphicsRectItem) and item.brush().color() == theme.color("accent")
    ]
    ticks.sort(key=lambda item: item.rect().top())
    return [_category(widget, item.rect().center()) for item in ticks]


def _rows_in_view(widget) -> list[str]:
    series = widget.chart.series()[0]
    top = widget.chart_area.verticalScrollBar().value()
    bottom = top + widget.chart_area.viewport().height()
    return [
        name
        for i, name in enumerate(widget.chart.axes(Qt.Vertical)[0].categories())
        if top <= widget.chart.mapToPosition(QPointF(0, i), series).y() <= bottom
    ]


def _hover(widget, name, monkeypatch) -> list[str]:
    """Move the mouse onto a sample's bar; the tooltips that shows."""
    shown = []
    monkeypatch.setattr(QToolTip, "showText", lambda _pos, text, *_args: shown.append(text))
    series = widget.chart.series()[0]
    index = list(widget.chart.axes(Qt.Vertical)[0].categories()).index(name)
    # Halfway along the first bar segment.
    point = widget.chart.mapToPosition(QPointF(series.barSets()[0].at(index) / 2, index), series)
    pos = QPointF(widget.chart_view.mapFromScene(widget.chart.mapToScene(point)))
    viewport = widget.chart_view.viewport()
    QApplication.sendEvent(
        viewport,
        QMouseEvent(QEvent.MouseMove, pos, viewport.mapToGlobal(pos), Qt.NoButton, Qt.NoButton, Qt.NoModifier),
    )
    return shown


def test_mini_charts_pair_each_sample_with_its_own_values(qapp, monkeypatch):
    names = ["S1", "S2", "S3"]
    areas = [[90.0, 10.0, 0.0], [1000.0, 600.0, 400.0], [6000.0, 6000.0, 18000.0]]
    ratio_chart = IsotopologueRatioWidget()
    abundance_chart = TotalAbundanceWidget()
    try:
        eics = _eics(names, areas)
        ratio_chart.update_ratios("Cmp", eics)
        abundances, shared = ratio_chart.get_last_total_abundances()
        abundance_chart.update_abundance_from_data("Cmp", shared, abundances)
        _shown(ratio_chart, 300)
        _shown(abundance_chart, 300)

        assert _hover(ratio_chart, "S1", monkeypatch)[-1] == "S1\nM+0  90.0%\nM+1  10.0%\nM+2  0.0%"
        assert _hover(abundance_chart, "S1", monkeypatch)[-1] == "S1\nTotal abundance  100"
        assert _hover(abundance_chart, "S3", monkeypatch)[-1] == "S3\nTotal abundance  3e+04"
        assert [e.sample_name for e in eics] == names

        assert ratio_chart.key.isVisible()
        key = QTextDocumentFragment.fromHtml(ratio_chart.key.text()).toPlainText()
        assert key.replace("\xa0", " ") == "■ M+0   ■ M+1   ■ M+2"
    finally:
        ratio_chart.deleteLater()
        abundance_chart.deleteLater()


@pytest.mark.parametrize(
    "values, multiplier, ticks",
    [
        ([1.2e6, 3.9e6, 2.5e6], "×10⁶", ["0", "2", "4"]),
        ([1.2e-3, 0.4e-3, 0.9e-3], "×10⁻³", ["0.0", "0.5", "1.0"]),
        ([2.5, 1.0, 2.0], "", ["0", "1", "2"]),
    ],
)
def test_abundance_marks_the_selected_samples_and_ticks_on_round_numbers(qapp, values, multiplier, ticks):
    widget = _shown(_abundance(["S1", "S2", "S3"], values))
    try:
        assert widget.header.detail.text() == multiplier
        assert [text for text, _x in widget.value_axis.tick_positions()] == ticks
        widget.set_highlighted(["S3", "elsewhere"])
        assert _selected(widget) == ["S3"]
        widget.set_highlighted([])
        assert _selected(widget) == []
    finally:
        widget.deleteLater()


@pytest.mark.parametrize("count, scrolls", [(30, True), (3, False)])
@pytest.mark.parametrize("make", [_abundance, _ratios])
def test_thirty_samples_are_named_on_readable_rows_that_scroll(qapp, make, count, scrolls):
    names = NAMES[:count]
    widget = _shown(make(names))
    try:
        axis = widget.chart.axes(Qt.Vertical)[0]
        assert axis.labelsVisible()
        assert list(axis.categories())[::-1] == names
        # Each row is at least as tall as the name it carries.
        row = widget.chart.plotArea().height() / count
        assert row >= QFontMetrics(axis.labelsFont()).height()
        assert (widget.chart_area.verticalScrollBar().maximum() > 0) is scrolls
    finally:
        widget.deleteLater()


@pytest.mark.parametrize("make", [_abundance, _ratios])
def test_selecting_a_sample_scrolls_its_row_into_view(qapp, make):
    widget = _shown(make(NAMES))
    try:
        widget.chart_area.verticalScrollBar().setValue(0)
        assert "Bio_029" not in _rows_in_view(widget)
        widget.set_highlighted(["Bio_029"])
        assert _selected(widget) == ["Bio_029"]
        assert "Bio_029" in _rows_in_view(widget)
        widget.set_highlighted(["Bio_000"])
        assert "Bio_000" in _rows_in_view(widget)
        assert "Bio_029" not in _rows_in_view(widget)
        widget.set_highlighted([])
        assert _selected(widget) == []
    finally:
        widget.deleteLater()


@pytest.mark.parametrize(
    "make, ticks",
    [(_abundance, ["0", "1", "2", "3"]), (_ratios, ["0.0", "0.5", "1.0"])],
)
def test_value_axis_stays_in_view_while_rows_scroll(qapp, make, ticks):
    widget = _shown(make(NAMES), 300)
    try:
        bar = widget.chart_area.verticalScrollBar()
        assert bar.maximum() > 0
        before = widget.value_axis.tick_positions()
        assert [text for text, _x in before] == ticks and widget.value_axis.isVisible()
        bar.setValue(bar.maximum())
        for _ in range(10):
            QApplication.processEvents()
        # Pinned outside the scroll area, so still on screen and at the same x.
        assert widget.value_axis.isVisible()
        assert widget.value_axis.geometry().bottom() < widget.chart_area.geometry().top()
        assert widget.value_axis.tick_positions() == before
    finally:
        widget.deleteLater()


def test_two_summaries_share_a_short_sidebar_without_an_outer_scroll(qapp):
    host = QWidget()
    layout = QVBoxLayout(host)
    charts = [_ratios(NAMES), _abundance(NAMES)]
    for chart in charts:
        layout.addWidget(chart, 1)
    try:
        _shown(host, 360)
        for chart in charts:
            assert chart.geometry().bottom() < 360
            assert len(_rows_in_view(chart)) >= 2
    finally:
        host.deleteLater()


def test_selection_leaves_other_bars_their_cohort_colours(qapp):
    widget = _shown(_ratios(NAMES[:5]), 300)
    try:
        bar_sets = widget.chart.series()[0].barSets()
        colours = [bar_set.color().name() for bar_set in bar_sets]
        widget.set_highlighted(["Bio_002"])
        assert _selected(widget) == ["Bio_002"]
        assert [bar_set.color().name() for bar_set in bar_sets] == colours
        assert all(bar_set.count() == 5 for bar_set in bar_sets)
        widget.set_highlighted([])
        assert _selected(widget) == []
    finally:
        widget.deleteLater()


def test_a_sample_with_no_ratio_shows_a_dash_and_explains_on_hover(qapp, monkeypatch):
    names = ["Bio_001", "Bio_018", "Bio_020"]
    widget = _shown(_ratios(names, [[6.0, 3.0, 1.0], [0.0, 0.0, 0.0], [5.0, 5.0, 0.0]]), 300)
    try:
        dashes = [
            item for item in widget.chart.childItems()
            if isinstance(item, QGraphicsSimpleTextItem) and item.isVisible()
        ]
        assert [dash.text() for dash in dashes] == ["—"]
        dash = dashes[0]
        assert _category(widget, dash.pos() + dash.boundingRect().center()) == "Bio_018"
        assert _hover(widget, "Bio_018", monkeypatch)[-1] == (
            "Bio_018\nNo ratio: this sample has no integrated peak area for this compound."
        )
    finally:
        widget.deleteLater()
