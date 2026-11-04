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
from PySide6.QtCore import QMargins, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QCursor, QFontMetrics
from PySide6.QtWidgets import QGraphicsSimpleTextItem, QToolTip, QWidget

from manic.ui.chart_style import style_axis, ui_font
from manic.ui.colors import QUALIFIER_STATUS_COLORS
from manic.ui.theme import color, contrast
from manic.validation.unlabelled_identity import (
    IdentitySampleAssessment,
    QualifierAssessment,
    QualifierStatus,
)

_TOOLTIP_HOLD_MS = 86_400_000
# Rows are capped at this height, so one sample is a strip, not a slab.
IDENTITY_ROW_MAX = 24
# Room for the "Qualifier 1  Qualifier 2" header above the cells.
IDENTITY_HEADER = 22

_STATUS_LABELS = {
    QualifierStatus.VALIDATED: "Validated",
    QualifierStatus.FAILED: "Failed",
    QualifierStatus.ABSENT: "Absent",
    QualifierStatus.NOT_ASSESSED: "Not assessed",
    QualifierStatus.UNAVAILABLE: "Unavailable",
}


# A mark in every cell, so no state is told by colour alone; the three
# grey states especially.
STATUS_MARKS = {
    QualifierStatus.VALIDATED: "✓",
    QualifierStatus.FAILED: "✕",
    QualifierStatus.ABSENT: "–",
    QualifierStatus.NOT_ASSESSED: "?",
    QualifierStatus.UNAVAILABLE: "n/a",
}


def identity_chart_height(rows: int) -> int:
    return rows * IDENTITY_ROW_MAX + IDENTITY_HEADER


class _CellMark(QGraphicsSimpleTextItem):
    """A cell's state mark, in whichever text colour reads on the cell fill.

    With no fill and no row it is a column header above the cells.
    """

    def __init__(self, text: str, fill: QColor | None, x: float, row: int | None, parent):
        super().__init__(text, parent)
        # The shared QColor is retuned in place on a scheme switch.
        self._fill = fill
        self.cell = (x, row)

    def paint(self, painter, _option, _widget=None):
        ink = (
            color("text_secondary") if self._fill is None
            else max((color("text"), color("surface")), key=lambda c: contrast(c, self._fill))
        )
        painter.setPen(ink)
        painter.setFont(self.font())
        painter.drawText(self.boundingRect(), Qt.AlignCenter, self.text())


def _place_cell_marks(chart: QChart) -> None:
    series = chart.series()
    marks = [item for item in chart.childItems() if isinstance(item, _CellMark)]
    if not series or not marks:
        return
    top = chart.mapToPosition(QPointF(0, 0.5), series[0]).y()
    bottom = chart.mapToPosition(QPointF(0, -0.5), series[0]).y()
    fits = abs(bottom - top) >= QFontMetrics(marks[0].font()).height()
    header_y = chart.plotArea().top() - IDENTITY_HEADER / 2
    for mark in marks:
        x, row = mark.cell
        mark.setVisible(fits or row is None)
        if mark.isVisible():
            centre = chart.mapToPosition(QPointF(x, 0 if row is None else row), series[0])
            if row is None:
                centre.setY(header_y)
            mark.setPos(centre - QRectF(mark.boundingRect()).center())


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
        f"Qualifier {qualifier.ordinal}  {_STATUS_LABELS[qualifier.status]}\n"
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
    label_font_size: int = 10,
    show_sample_names: bool = True,
) -> IdentityGridBinding:
    chart.removeAllSeries()
    for axis in list(chart.axes()):
        chart.removeAxis(axis)
    chart.setTitle("")
    chart.legend().setVisible(False)
    chart.setMargins(QMargins(0, 0, 0, 0))
    chart.layout().setContentsMargins(0, 0, 0, 0)
    chart.setBackgroundRoundness(0)
    for item in chart.childItems():
        if isinstance(item, _CellMark):
            item.setParentItem(None)
            if item.scene() is not None:
                item.scene().removeItem(item)
    if not samples:
        return IdentityGridBinding((), MappingProxyType({}))

    display = tuple(reversed(samples))
    count = len(display)
    series = QHorizontalStackedBarSeries()
    series.setBarWidth(0.92)
    bar_sets: list[QBarSet] = []
    cells: dict[QBarSet, IdentityCell] = {}
    for row, sample in enumerate(display):
        for column, qualifier in enumerate(sample.qualifiers):
            fill = QUALIFIER_STATUS_COLORS[qualifier.status]
            mark = _CellMark(STATUS_MARKS[qualifier.status], fill, column + 0.5, row, chart)
            mark.setFont(ui_font(label_font_size))
            mark.setZValue(10)
            bar_set = QBarSet("")
            bar_set.setColor(fill)
            bar_set.setBorderColor(color("surface"))
            for other_row in range(count):
                bar_set.append(1.0 if other_row == row else 0.0)
            series.append(bar_set)
            bar_sets.append(bar_set)
            cells[bar_set] = IdentityCell(sample.sample_name, qualifier)
    chart.addSeries(series)
    # QtCharts shrinks an axis with the chart, clipping its labels on a
    # short grid, so the column headers sit in a fixed margin instead.
    chart.setMargins(QMargins(0, IDENTITY_HEADER, 0, 0))
    for column in range(2):
        header = _CellMark(f"Qualifier {column + 1}", None, column + 0.5, None, chart)
        header.setFont(ui_font(label_font_size))

    x_axis = QValueAxis()
    x_axis.setRange(0, 2)
    x_axis.setLabelsVisible(False)
    x_axis.setGridLineVisible(False)
    x_axis.setLineVisible(False)

    y_axis = QBarCategoryAxis()
    y_axis.append([sample.sample_name for sample in display])
    style_axis(y_axis)
    y_axis.setLabelsFont(ui_font(label_font_size))
    y_axis.setLabelsColor(color("text"))
    y_axis.setLineVisible(False)
    y_axis.setLabelsVisible(show_sample_names)

    top_axis = QCategoryAxis()
    top_axis.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
    top_axis.append("Qualifier 1", 0.5)
    top_axis.append("Qualifier 2", 1.5)
    top_axis.setRange(0, 2)
    style_axis(top_axis)
    top_axis.setLabelsFont(ui_font(label_font_size))
    top_axis.setLineVisible(False)
    top_axis.setVisible(False)

    chart.addAxis(x_axis, Qt.AlignBottom)
    chart.addAxis(y_axis, Qt.AlignLeft)
    chart.addAxis(top_axis, Qt.AlignTop)
    series.attachAxis(x_axis)
    series.attachAxis(y_axis)
    if not chart.property("identityMarksPlaced"):
        chart.setProperty("identityMarksPlaced", True)
        chart.plotAreaChanged.connect(lambda _area: _place_cell_marks(chart))
    _place_cell_marks(chart)
    return IdentityGridBinding(tuple(bar_sets), MappingProxyType(cells))
