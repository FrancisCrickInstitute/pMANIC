from __future__ import annotations

from enum import StrEnum

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSet,
    QChart,
    QHorizontalStackedBarSeries,
    QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCursor, QFont
from PySide6.QtWidgets import QToolTip, QWidget


class RatioVerdict(StrEnum):
    VALIDATED = "validated"
    PARTIAL = "partial"
    MISMATCH = "mismatch"
    NOT_GIVEN = "not_given"


VERDICT_LABELS = {
    RatioVerdict.VALIDATED: "Validated",
    RatioVerdict.PARTIAL: "Partial",
    RatioVerdict.MISMATCH: "Fail",
    RatioVerdict.NOT_GIVEN: "No ratio",
}

VERDICT_COLORS = {
    RatioVerdict.VALIDATED: QColor("#2F9E44"),
    RatioVerdict.PARTIAL: QColor("#E8590C"),
    RatioVerdict.MISMATCH: QColor("#C92A2A"),
    RatioVerdict.NOT_GIVEN: QColor("#868E96"),
}

_TOOLTIP_HOLD_MS = 86_400_000


def show_identity_tooltip(widget: QWidget, text: str) -> None:
    QToolTip.showText(
        QCursor.pos(),
        text,
        widget,
        widget.rect(),
        _TOOLTIP_HOLD_MS,
    )


def add_identity_series(
    chart: QChart,
    samples: list[tuple[str, RatioVerdict]],
    *,
    show_names: bool,
) -> list[str]:
    chart.removeAllSeries()
    for axis in list(chart.axes()):
        chart.removeAxis(axis)
    if not samples:
        return []

    series = QHorizontalStackedBarSeries()
    series.setBarWidth(0.8)
    display = list(reversed(samples))
    names = [name for name, _verdict in display]

    for verdict in RatioVerdict:
        bar_set = QBarSet(VERDICT_LABELS[verdict])
        bar_set.setColor(VERDICT_COLORS[verdict])
        for _name, sample_verdict in display:
            bar_set.append(1.0 if sample_verdict is verdict else 0.0)
        series.append(bar_set)

    chart.addSeries(series)

    x_axis = QValueAxis()
    x_axis.setRange(0, 1)
    x_axis.setLabelsVisible(False)
    x_axis.setGridLineVisible(False)
    x_axis.setLineVisible(False)
    x_axis.setTickCount(2)

    y_axis = QBarCategoryAxis()
    y_axis.append(names)
    y_axis.setLabelsFont(QFont("Arial", 10 if show_names else 8))
    y_axis.setGridLineVisible(False)
    y_axis.setLineVisible(False)
    y_axis.setLabelsVisible(show_names)

    chart.addAxis(x_axis, Qt.AlignBottom)
    chart.addAxis(y_axis, Qt.AlignLeft)
    series.attachAxis(x_axis)
    series.attachAxis(y_axis)
    return names
