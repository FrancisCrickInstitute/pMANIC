from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSet,
    QCategoryAxis,
    QChart,
    QHorizontalStackedBarSeries,
    QValueAxis,
)
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QCursor, QFont
from PySide6.QtWidgets import QToolTip, QWidget

from manic.ui.colors import QUALIFIER_STATUS_COLORS
from manic.validation.unlabelled_identity import (
    IdentitySampleAssessment,
    QualifierAssessment,
    QualifierStatus,
)

_TOOLTIP_HOLD_MS = 86_400_000

_STATUS_LABELS = {
    QualifierStatus.VALIDATED: "Validated",
    QualifierStatus.FAILED: "Failed",
    QualifierStatus.ABSENT: "Absent",
    QualifierStatus.NOT_ASSESSED: "Not assessed",
    QualifierStatus.UNAVAILABLE: "Unavailable",
}


def show_identity_tooltip(widget: QWidget, text: str) -> None:
    QToolTip.showText(
        QCursor.pos(),
        text,
        widget,
        widget.rect(),
        _TOOLTIP_HOLD_MS,
    )


def identity_cell_tooltip(cell: "IdentityCell") -> str:
    qualifier = cell.qualifier
    return (
        f"{cell.sample_name}\n"
        f"V{qualifier.ordinal}  {_STATUS_LABELS[qualifier.status]}\n"
        f"{qualifier.detail}"
    )


@dataclass(frozen=True, slots=True)
class IdentityCell:
    sample_name: str
    qualifier: QualifierAssessment


@dataclass(slots=True)
class IdentityGridBinding:
    bar_sets: tuple[QBarSet, ...]
    cells_by_set: Mapping[QBarSet, IdentityCell]

    def cell_for(self, bar_set: QBarSet) -> IdentityCell | None:
        return self.cells_by_set.get(bar_set)


def add_identity_grid(
    chart: QChart,
    samples: Sequence[IdentitySampleAssessment],
    *,
    label_font_size: int = 8,
) -> IdentityGridBinding:
    chart.removeAllSeries()
    for axis in list(chart.axes()):
        chart.removeAxis(axis)
    chart.setTitle("")
    chart.legend().setVisible(False)
    chart.setMargins(QMargins(0, 0, 0, 0))
    chart.layout().setContentsMargins(0, 0, 0, 0)
    chart.setBackgroundRoundness(0)
    if not samples:
        return IdentityGridBinding((), MappingProxyType({}))

    display = tuple(reversed(samples))
    count = len(display)
    series = QHorizontalStackedBarSeries()
    series.setBarWidth(0.92)
    bar_sets: list[QBarSet] = []
    cells: dict[QBarSet, IdentityCell] = {}
    for row, sample in enumerate(display):
        for qualifier in sample.qualifiers:
            bar_set = QBarSet("")
            bar_set.setColor(QUALIFIER_STATUS_COLORS[qualifier.status])
            # White borders keep adjacent same-status cells from fusing.
            bar_set.setBorderColor(QColor("white"))
            for other_row in range(count):
                bar_set.append(1.0 if other_row == row else 0.0)
            series.append(bar_set)
            bar_sets.append(bar_set)
            cells[bar_set] = IdentityCell(sample.sample_name, qualifier)
    chart.addSeries(series)

    x_axis = QValueAxis()
    x_axis.setRange(0, 2)
    x_axis.setLabelsVisible(False)
    x_axis.setGridLineVisible(False)
    x_axis.setLineVisible(False)

    y_axis = QBarCategoryAxis()
    y_axis.append([sample.sample_name for sample in display])
    y_axis.setLabelsFont(QFont("Arial", label_font_size))
    y_axis.setGridLineVisible(False)
    y_axis.setLineVisible(False)
    y_axis.setLabelsVisible(True)

    top_axis = QCategoryAxis()
    top_axis.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
    top_axis.append("V1", 0.5)
    top_axis.append("V2", 1.5)
    top_axis.setRange(0, 2)
    top_axis.setLabelsFont(QFont("Arial", label_font_size))
    top_axis.setGridLineVisible(False)
    top_axis.setLineVisible(False)
    top_axis.setLabelsVisible(True)

    chart.addAxis(x_axis, Qt.AlignBottom)
    chart.addAxis(y_axis, Qt.AlignLeft)
    chart.addAxis(top_axis, Qt.AlignTop)
    series.attachAxis(x_axis)
    series.attachAxis(y_axis)
    return IdentityGridBinding(tuple(bar_sets), MappingProxyType(cells))
