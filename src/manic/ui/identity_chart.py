from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSet,
    QChart,
    QHorizontalStackedBarSeries,
    QValueAxis,
)
from PySide6.QtCore import QMargins, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QCursor, QFontMetrics
from PySide6.QtWidgets import QGraphicsSimpleTextItem, QToolTip, QWidget

from manic.models.analysis import IonRole
from manic.ui.channel_chips import expectation_text
from manic.ui.chart_style import style_axis, ui_font
from manic.ui.colors import QUALIFIER_GREEN, QUALIFIER_PASS_TINT, QUALIFIER_STATUS_COLORS
from manic.ui.theme import color, contrast
from manic.validation.unlabelled_identity import (
    IdentityAssessmentSet,
    IdentitySampleAssessment,
    QualifierAssessment,
    QualifierStatus,
)

_TOOLTIP_HOLD_MS = 86_400_000
# Rows are capped at this height, so one sample is a strip, not a slab.
IDENTITY_ROW_MAX = 24


def identity_column_headers(channels, *, detail: bool = True) -> list[tuple[float, str]]:
    """A header at each column's centre, one column per qualifier the method has.

    With ``detail``, a second line names the ion and its expectation.
    """
    qualifiers = sorted((c for c in channels if c.role is IonRole.QUALIFIER), key=lambda c: c.ordinal)
    return [
        (
            column + 0.5,
            f"Qualifier {c.ordinal}" + (f"\nm/z {c.mz:g}   {expectation_text(c)}" if detail else ""),
        )
        for column, c in enumerate(qualifiers)
    ]


def identity_cells(sample: IdentitySampleAssessment) -> list[QualifierAssessment]:
    """One cell per qualifier the method has; a slot for an absent ion is no cell."""
    return [q for q in sample.qualifiers if q.status is not QualifierStatus.ABSENT]


STATUS_LABELS = {
    QualifierStatus.VALIDATED: "Validated",
    QualifierStatus.FAILED: "Failed",
    QualifierStatus.NOT_ASSESSED: "Not assessed",
    QualifierStatus.UNAVAILABLE: "Unavailable",
}


# A mark in every cell, so no state is told by colour alone; the three
# grey states especially.
STATUS_MARKS = {
    QualifierStatus.VALIDATED: "✓",
    QualifierStatus.FAILED: "✕",
    QualifierStatus.NOT_ASSESSED: "?",
    QualifierStatus.UNAVAILABLE: "n/a",
}


def identity_chart_height(rows: int, row_height: int = IDENTITY_ROW_MAX) -> int:
    return rows * row_height


# The User Guide section on filling a qualifier's expected ratio, as a documentation link.
MISSING_RATIO_GUIDE = "01_user_guide.md#fix-a-missing-qualifier-ratio"
_GUIDE_LINK = (
    f'<a href="{MISSING_RATIO_GUIDE}" style="text-decoration: none;">'
    "Fix\u00a0a\u00a0missing\u00a0qualifier\u00a0ratio</a>"
)
MISSING_RATIO_STEP = (
    "Expected ratios come from the compound list's Qualifier Ratio columns. "
    f"See {_GUIDE_LINK}."
)
MISSING_TOLERANCE_STEP = "Set the missing tolerances in Settings\u00a0›\u00a0Qualifier\u00a0ratios."


def _checkable(channel) -> bool:
    return channel.expected_ratio is not None and channel.ratio_tolerance is not None


def identity_unassessed_note(identity: IdentityAssessmentSet) -> str | None:
    """The next step for a compound none of whose qualifiers can be checked, else None.

    The key chips already name what is missing, so this says only how to fix it:
    Settings edits tolerances, never expected ratios.
    """
    qualifiers = [c for c in identity.channels if c.role is IonRole.QUALIFIER]
    if not qualifiers:
        return f"{identity.compound_name} has no qualifier ions, so there is no identity to check."
    if any(_checkable(c) for c in qualifiers):
        return None
    steps = []
    if any(c.expected_ratio is None for c in qualifiers):
        steps.append(MISSING_RATIO_STEP)
    if any(c.expected_ratio is not None for c in qualifiers):
        steps.append(MISSING_TOLERANCE_STEP)
    return " ".join(steps)


def qualifier_gap_note(identity: IdentityAssessmentSet) -> str | None:
    """One note naming each qualifier no sample can be checked on, else None.

    The gap is the compound's, not any sample's, so the grid states it once
    instead of marking every tile partial.
    """
    qualifiers = [c for c in identity.channels if c.role is IonRole.QUALIFIER]
    notes = [
        f"Qualifier {c.ordinal} is not assessed: the compound list gives it no expected ratio. "
        f"See {_GUIDE_LINK}."
        if c.expected_ratio is None
        else f"Qualifier {c.ordinal} is not assessed: it has no tolerance. "
        "Set one in Settings\u00a0›\u00a0Qualifier\u00a0ratios."
        for c in qualifiers
        if not _checkable(c)
    ]
    return " ".join(notes) or None


class _CellMark(QGraphicsSimpleTextItem):
    """A cell's state mark, in ``ink`` or else whichever text colour reads on the cell fill."""

    def __init__(self, text: str, fill: QColor, ink: QColor | None, x: float, row: int, parent):
        super().__init__(text, parent)
        # The shared QColors are retuned in place on a scheme switch.
        self._fill = fill
        self._ink = ink
        self.cell = (x, row)

    def paint(self, painter, _option, _widget=None):
        painter.setPen(
            self._ink
            or max((color("text"), color("surface")), key=lambda c: contrast(c, self._fill))
        )
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
    for mark in marks:
        x, row = mark.cell
        mark.setVisible(fits)
        if fits:
            centre = chart.mapToPosition(QPointF(x, row), series[0])
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
        f"Qualifier {qualifier.ordinal}  {STATUS_LABELS[qualifier.status]}\n"
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
        for column, qualifier in enumerate(identity_cells(sample)):
            passed = qualifier.status is QualifierStatus.VALIDATED
            fill = QUALIFIER_PASS_TINT if passed else QUALIFIER_STATUS_COLORS[qualifier.status]
            ink = QUALIFIER_GREEN if passed else None
            mark = _CellMark(STATUS_MARKS[qualifier.status], fill, ink, column + 0.5, row, chart)
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

    x_axis = QValueAxis()
    x_axis.setRange(0, max(len(identity_cells(samples[0])), 1))
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

    chart.addAxis(x_axis, Qt.AlignBottom)
    chart.addAxis(y_axis, Qt.AlignLeft)
    series.attachAxis(x_axis)
    series.attachAxis(y_axis)
    if not chart.property("identityMarksPlaced"):
        chart.setProperty("identityMarksPlaced", True)
        chart.plotAreaChanged.connect(lambda _area: _place_cell_marks(chart))
    _place_cell_marks(chart)
    return IdentityGridBinding(tuple(bar_sets), MappingProxyType(cells))
