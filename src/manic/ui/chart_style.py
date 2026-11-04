"""Shared look for every QtCharts chart: system font, theme colours, tidy ticks."""

from __future__ import annotations

import math

from PySide6.QtCharts import QAbstractAxis, QChart, QValueAxis
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import QApplication

from manic.ui.theme import COLORS, color

AXIS_LABEL_PX = 10

_SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def ui_font(pixel_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """The application's system UI font at a pixel size."""
    font = QFont(QApplication.font())
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def text_style(token: str, pixel_size: int, weight: int = 400) -> str:
    """Label stylesheet that wins over app-wide QLabel rules (padding, font size)."""
    return (
        f"color: {COLORS[token]}; font-size: {pixel_size}px; font-weight: {weight};"
        " padding: 0px; border: none; background: transparent;"
    )


def scale_text(exponent: int) -> str:
    """'×10⁶' for an axis multiplier; empty when there is none."""
    return f"×10{str(exponent).translate(_SUPERSCRIPT)}" if exponent else ""


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


def set_nice_ticks(
    axis: QValueAxis, low: float, high: float, *, max_ticks: float, decimals: int | None = None
) -> None:
    """Ticks on round numbers inside [low, high] without changing the range."""
    step = nice_step(high - low, max_ticks)
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
    """Transparent chart on a white plot area, no title or built-in legend."""
    chart.setBackgroundVisible(False)
    chart.setBackgroundRoundness(0)
    chart.setPlotAreaBackgroundVisible(True)
    chart.setPlotAreaBackgroundBrush(QColor(color("surface")))
    chart.setPlotAreaBackgroundPen(QPen(Qt.NoPen))
    chart.legend().setVisible(False)
    chart.setTitle("")
    chart.setMargins(margins)
    chart.layout().setContentsMargins(0, 0, 0, 0)
