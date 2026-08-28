from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

from PySide6.QtCharts import QCategoryAxis, QChart, QScatterSeries
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QCursor, QFont
from PySide6.QtWidgets import QToolTip, QWidget

from manic.ui.colors import QUALIFIER_GREEN, QUALIFIER_GREY, QUALIFIER_RED
from manic.validation.unlabelled_identity import (
    IdentitySampleAssessment,
    QualifierAssessment,
    QualifierStatus,
)

_TOOLTIP_HOLD_MS = 86_400_000
_MARKER_MIN = 8.0
_MARKER_MAX = 28.0

_STATUS_LABELS = {
    QualifierStatus.VALIDATED: "Validated",
    QualifierStatus.FAILED: "Failed",
    QualifierStatus.ABSENT: "Absent",
    QualifierStatus.NOT_ASSESSED: "Not assessed",
    QualifierStatus.UNAVAILABLE: "Unavailable",
}

_SERIES_BUCKETS: tuple[tuple[str, QColor, frozenset[QualifierStatus]], ...] = (
    ("Validated", QUALIFIER_GREEN, frozenset({QualifierStatus.VALIDATED})),
    ("Failed", QUALIFIER_RED, frozenset({QualifierStatus.FAILED})),
    (
        "No verdict",
        QUALIFIER_GREY,
        frozenset(
            {
                QualifierStatus.ABSENT,
                QualifierStatus.NOT_ASSESSED,
                QualifierStatus.UNAVAILABLE,
            }
        ),
    ),
)


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


def identity_marker_size(plot_height: float, sample_count: int) -> float:
    if sample_count <= 0:
        return _MARKER_MIN
    return min(_MARKER_MAX, max(_MARKER_MIN, plot_height / sample_count))


@dataclass(frozen=True, slots=True)
class IdentityCell:
    sample_name: str
    qualifier: QualifierAssessment


@dataclass(slots=True)
class IdentityChartBinding:
    series: tuple[QScatterSeries, ...]
    cells_by_point: Mapping[tuple[int, int], IdentityCell]

    def cell_at(self, point: QPointF) -> IdentityCell | None:
        key = (int(round(point.x())), int(round(point.y())))
        return self.cells_by_point.get(key)


def add_identity_series(
    chart: QChart,
    samples: Sequence[IdentitySampleAssessment],
    *,
    show_names: bool,
) -> IdentityChartBinding:
    chart.removeAllSeries()
    for axis in list(chart.axes()):
        chart.removeAxis(axis)
    if not samples:
        return IdentityChartBinding((), MappingProxyType({}))

    count = len(samples)
    cells: dict[tuple[int, int], IdentityCell] = {}
    points_by_label: dict[str, list[QPointF]] = {
        label: [] for label, _color, _statuses in _SERIES_BUCKETS
    }

    for index, sample in enumerate(samples):
        y = count - index
        for qualifier in sample.qualifiers:
            x = int(qualifier.ordinal)
            point = QPointF(float(x), float(y))
            cells[(x, y)] = IdentityCell(sample.sample_name, qualifier)
            for label, _color, statuses in _SERIES_BUCKETS:
                if qualifier.status in statuses:
                    points_by_label[label].append(point)
                    break

    series_list: list[QScatterSeries] = []
    for label, color, _statuses in _SERIES_BUCKETS:
        series = QScatterSeries()
        series.setName(label)
        series.setColor(color)
        series.setBorderColor(color)
        series.setMarkerShape(QScatterSeries.MarkerShapeRectangle)
        for point in points_by_label[label]:
            series.append(point)
        chart.addSeries(series)
        series_list.append(series)

    x_axis = QCategoryAxis()
    x_axis.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
    x_axis.append("V1", 1.0)
    x_axis.append("V2", 2.0)
    x_axis.setRange(0.5, 2.5)
    x_axis.setLabelsFont(QFont("Arial", 10 if show_names else 8))
    x_axis.setGridLineVisible(False)
    x_axis.setLineVisible(False)
    x_axis.setLabelsVisible(True)

    y_axis = QCategoryAxis()
    y_axis.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
    for index in range(count - 1, -1, -1):
        y_axis.append(samples[index].sample_name, float(count - index))
    y_axis.setRange(0.5, float(count) + 0.5)
    y_axis.setLabelsFont(QFont("Arial", 10 if show_names else 8))
    y_axis.setGridLineVisible(False)
    y_axis.setLineVisible(False)
    y_axis.setLabelsVisible(show_names)

    chart.addAxis(x_axis, Qt.AlignBottom)
    chart.addAxis(y_axis, Qt.AlignLeft)
    for series in series_list:
        series.attachAxis(x_axis)
        series.attachAxis(y_axis)

    def _resize_markers(_rect=None) -> None:
        size = identity_marker_size(chart.plotArea().height(), count)
        for series in series_list:
            series.setMarkerSize(size)

    previous = getattr(chart, "_identity_marker_resize", None)
    if previous is not None:
        try:
            chart.plotAreaChanged.disconnect(previous)
        except RuntimeError:
            pass
    chart._identity_marker_resize = _resize_markers
    chart.plotAreaChanged.connect(_resize_markers)
    _resize_markers()

    return IdentityChartBinding(tuple(series_list), MappingProxyType(cells))
