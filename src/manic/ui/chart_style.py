"""Shared look for every QtCharts chart: system font, theme colours, tidy ticks."""

from __future__ import annotations

import math

from PySide6.QtCharts import (
    QAbstractAxis,
    QAbstractBarSeries,
    QAreaSeries,
    QChart,
    QValueAxis,
    QXYSeries,
)
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QBrush, QFont, QFontMetricsF, QPen
from PySide6.QtWidgets import QApplication

from manic.ui.theme import color, remap_color

AXIS_LABEL_PX = 10

_SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def ui_font(pixel_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """The application's system UI font at a pixel size."""
    font = QFont(QApplication.font())
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def text_style(token: str, pixel_size: int, weight: int = 400) -> str:
    """Label stylesheet template (for ``theme.style``) that wins over app-wide QLabel rules."""
    return (
        f"color: @{token}; font-size: {pixel_size}px; font-weight: {weight};"
        " padding: 0px; border: none; background: transparent;"
    )


def scale_text(exponent: int) -> str:
    """'×10⁶' for an axis multiplier; empty when there is none."""
    return f"×10{str(exponent).translate(_SUPERSCRIPT)}" if exponent else ""


def abundance_scale(values) -> tuple[float, int]:
    """(largest finite value, power of ten the axis shows it in); (1, 0) when none is positive.

    A sample with no abundance (NaN) has no bar, so it never sets the axis.
    """
    finite = [float(v) for v in values if math.isfinite(v)]
    top = max(finite, default=0.0)
    if not top > 0:
        return 1.0, 0
    return top, math.floor(math.log10(top))


def nice_step(span: float, max_ticks: float) -> float:
    """Largest 1-2-5 step that gives at least ``max_ticks`` intervals over ``span``."""
    if not math.isfinite(span) or span <= 0:
        return 1.0
    raw = span / max_ticks
    magnitude = 10 ** math.floor(math.log10(raw))
    for multiple in (5, 2, 1):
        if multiple * magnitude <= raw:
            return multiple * magnitude
    return magnitude


def step_decimals(step: float) -> int:
    return max(0, -math.floor(math.log10(step) + 1e-9))


def _next_step(step: float) -> float:
    """The 1-2-5 step after ``step``."""
    magnitude = 10 ** math.floor(math.log10(step) + 1e-9)
    return next(m * magnitude for m in (2, 5, 10) if m * magnitude > step * (1 + 1e-9))


def set_nice_ticks(
    axis: QValueAxis,
    low: float,
    high: float,
    *,
    max_ticks: float,
    decimals: int | None = None,
    plot_px: float = 0,
) -> None:
    """Ticks on round numbers inside [low, high] without changing the range.

    For a horizontal axis ``plot_px`` wide, the step widens until neighbouring
    labels in the axis font stay two digits apart.
    """
    step = nice_step(high - low, max_ticks)
    if plot_px > 0 and high > low:
        metrics = QFontMetricsF(axis.labelsFont())
        places = step_decimals(step) if decimals is None else decimals
        label = max(metrics.horizontalAdvance(f"{v:.{places}f}") for v in (low, high))
        spacing = (label + metrics.horizontalAdvance("00")) * (high - low)
        while step < spacing / plot_px:
            step = _next_step(step)
        # Denser labels move the plot edge by up to a label's width, which can make the
        # wider step fit again; going denser only with that much to spare stops the flip.
        shown = axis.tickInterval() if axis.tickType() == QValueAxis.TicksDynamic else 0
        while step < shown and step < spacing / max(plot_px - label, 1):
            step = _next_step(step)
    axis.setTickType(QValueAxis.TicksDynamic)
    axis.setTickAnchor(math.ceil(low / step) * step)
    axis.setTickInterval(step)
    axis.setLabelFormat(f"%.{step_decimals(step) if decimals is None else decimals}f")


def style_axis(axis: QAbstractAxis, *, grid: bool = False) -> None:
    axis.setLabelsFont(ui_font(AXIS_LABEL_PX))
    axis.setLabelsColor(color("text_secondary"))
    axis.setLinePen(QPen(color("border_strong"), 1))
    axis.setGridLineVisible(grid)
    axis.setGridLinePen(QPen(color("grid_line"), 1))
    axis.setMinorGridLineVisible(False)
    axis.setShadesVisible(False)
    axis.setTitleFont(ui_font(11))
    axis.setTitleBrush(color("text_secondary"))
    # Tick labels are short; QtCharts otherwise shows "…" when a reused chart
    # changes label width before its layout catches up.
    axis.setTruncateLabels(False)


def style_chart(chart: QChart, margins: QMargins = QMargins(0, 0, 0, 0)) -> None:
    """Transparent chart on a surface-coloured plot area, no title or built-in legend."""
    chart.setBackgroundVisible(False)
    chart.setBackgroundRoundness(0)
    chart.setPlotAreaBackgroundVisible(True)
    chart.setPlotAreaBackgroundBrush(color("surface"))
    chart.setPlotAreaBackgroundPen(QPen(Qt.NoPen))
    chart.legend().setVisible(False)
    chart.setTitle("")
    chart.setMargins(margins)
    chart.layout().setContentsMargins(0, 0, 0, 0)


def remap_chart_colors(chart: QChart, remap: dict[str, str]) -> None:
    """Move a built chart to a new scheme in place, keeping its data and selection."""

    def pen(p: QPen) -> QPen:
        p = QPen(p)
        p.setColor(remap_color(p.color(), remap))
        return p

    def brush(b: QBrush) -> QBrush:
        b = QBrush(b)
        b.setColor(remap_color(b.color(), remap))
        return b

    chart.setPlotAreaBackgroundBrush(brush(chart.plotAreaBackgroundBrush()))
    for axis in chart.axes():
        axis.setLabelsColor(remap_color(axis.labelsColor(), remap))
        axis.setLinePen(pen(axis.linePen()))
        axis.setGridLinePen(pen(axis.gridLinePen()))
        axis.setTitleBrush(brush(axis.titleBrush()))
    for series in chart.series():
        if isinstance(series, QAbstractBarSeries):
            for bar_set in series.barSets():
                bar_set.setPen(pen(bar_set.pen()))
                bar_set.setBrush(brush(bar_set.brush()))
                bar_set.setLabelColor(remap_color(bar_set.labelColor(), remap))
        elif isinstance(series, (QXYSeries, QAreaSeries)):
            series.setPen(pen(series.pen()))
            series.setBrush(brush(series.brush()))
