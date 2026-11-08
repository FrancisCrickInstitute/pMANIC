"""Shared look for every QtCharts chart: system font, theme colours, tidy ticks."""

from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCharts import (
    QAbstractAxis,
    QAbstractBarSeries,
    QAreaSeries,
    QBarCategoryAxis,
    QChart,
    QChartView,
    QValueAxis,
    QXYSeries,
)
from PySide6.QtCore import QEvent, QMargins, QObject, QPoint, QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QBrush, QCursor, QFont, QFontMetrics, QFontMetricsF, QPen
from PySide6.QtWidgets import QApplication, QGraphicsSimpleTextItem, QToolTip

from manic.ui.theme import color, remap_color

AXIS_LABEL_PX = 10
# A large plot tile's sample caption.
CAPTION_PX = 13

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


def fit_name_font(chart: QChart, axis: QAbstractAxis) -> None:
    """Sample names grow with roomy summary rows, from the axis size up to the caption size."""
    rows = axis.count()
    if not rows:
        return
    px = min(max(int(chart.plotArea().height() / rows * 0.6), AXIS_LABEL_PX), CAPTION_PX)
    if axis.labelsFont().pixelSize() != px:
        axis.setLabelsFont(ui_font(px))


def fit_category_names(axis, names: list[str], view_width: int) -> None:
    """Shorten names in the middle to fit a summary chart's name column.

    QtCharts gives the name axis at most 40% of the chart and lets a longer name
    run off its edge (or, truncating, leaves only "…"). Hover gives the full name.
    """
    metrics = QFontMetrics(axis.labelsFont())
    width = int(view_width * 0.4) - 8
    fitted, seen = [], {}
    for name in names:
        short = metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, width)
        # A category axis needs unique names; alike shortenings differ by invisible marks.
        fitted.append(short + "\u200b" * seen.get(short, 0))
        seen[short] = seen.get(short, 0) + 1
    if fitted != axis.categories():
        axis.setCategories(fitted)


def place_row_notes(
    chart: QChart, notes: list[QGraphicsSimpleTextItem], texts: dict[int, str]
) -> None:
    """Replace ``notes`` with ``texts`` at the start of their bar rows (0 is the bottom bar).

    A row with no visible bar says why ("—", "0", "<0.01") in the sample names' font.
    """
    for note in notes:
        if note.scene() is not None:
            note.scene().removeItem(note)
    notes.clear()
    names = chart.axes(Qt.Vertical)
    if not chart.series() or not names:
        return
    series = chart.series()[0]
    for row, text in texts.items():
        note = QGraphicsSimpleTextItem(text, chart)
        note.setFont(names[0].labelsFont())
        note.setBrush(color("text_secondary"))
        note.setZValue(10)
        start = chart.mapToPosition(QPointF(0, row), series)
        note.setPos(start.x() + 4, start.y() - note.boundingRect().height() / 2)
        notes.append(note)


def bar_row_at(chart: QChart, view: QChartView, pos: QPoint) -> int | None:
    """The bar row (0 is the bottom bar) under a chart-view viewport position.

    A row spans its name and the plot's width, so a bar too short to hit still has one.
    """
    names = next((a for a in chart.axes(Qt.Vertical) if isinstance(a, QBarCategoryAxis)), None)
    if not chart.series() or names is None:
        return None
    point = chart.mapFromScene(view.mapToScene(pos))
    area = chart.plotArea()
    if not area.top() <= point.y() <= area.bottom() or point.x() > area.right():
        return None
    row = round(chart.mapToValue(point, chart.series()[0]).y())
    return row if 0 <= row < names.count() else None


# A chart's tip stays up while the pointer rests on what it describes.
_TIP_HOLD_MS = 86_400_000


class BarRows(QObject):
    """A bar chart answers by row: a click calls ``activated(row)``, and the place under the
    pointer alone decides the tip, ``tip(row, value)`` or none, the same for a row whose bar
    is empty or too short to hit.

    ``value`` is the pointer in the chart's value space, for a tip that differs along a row.
    With ``waits_for_double_click``, a click activates only once no second click follows, so a
    double-click that enlarges the chart leaves the selection as it was.
    """

    def __init__(
        self,
        chart: QChart,
        view: QChartView,
        activated: Callable[[int], None],
        tip: Callable[[int, QPointF], str | None],
        *,
        waits_for_double_click: bool = False,
    ):
        # The viewport's child, so its filter goes before the viewport's own teardown events.
        super().__init__(view.viewport())
        self._chart, self._view = chart, view
        self._activated, self._tip = activated, tip
        self._showing: str | None = None
        self._settled = QTimer(self, singleShot=True, interval=0)
        self._settled.timeout.connect(lambda: self._show_under(QCursor.pos()))
        self._click: QTimer | None = None
        if waits_for_double_click:
            self._click = QTimer(self, singleShot=True, interval=QApplication.doubleClickInterval())
            self._click.timeout.connect(self._activate_click)
        self._clicked: int | None = None
        self._doubled = False
        view.viewport().setMouseTracking(True)
        view.viewport().installEventFilter(self)

    def refresh(self, pointer: QPoint | None = None) -> None:
        """Show the tip for the place at ``pointer`` (a viewport point; the keys give a row's
        name), or with none given, under the pointer once the layout has settled; hide it
        where there is none."""
        if pointer is None:
            if self._click is not None:
                # A waiting click names a row of the old data; new rows may hold other samples.
                self._click.stop()
                self._clicked = None
            self._settled.start()
        else:
            self._show_at(pointer)

    def _show_under(self, at: QPoint) -> None:
        # Qt sends no event when the chart moves under a still pointer, so a point kept in the
        # viewport goes stale; the screen point stays true while the pointer rests.
        viewport = self._view.viewport()
        self._show_at(viewport.mapFromGlobal(at) if QApplication.widgetAt(at) is viewport else None)

    def _show_at(self, pointer: QPoint | None) -> None:
        text = None
        row = None if pointer is None else bar_row_at(self._chart, self._view, pointer)
        if row is not None:
            scene = self._view.mapToScene(pointer)
            value = self._chart.mapToValue(self._chart.mapFromScene(scene), self._chart.series()[0])
            text = self._tip(row, value)
        if text is None:
            # Another chart may have raised the tip since; Qt has one tip for the whole app.
            if self._showing is not None and QToolTip.isVisible() and QToolTip.text() == self._showing:
                QToolTip.hideText()
        else:
            screen = self._view.viewport().mapToGlobal(pointer)
            if text != self._showing and QToolTip.isVisible() and QToolTip.text() == text:
                # Qt ignores the same text while the hide just asked for is pending; new text cancels it.
                QToolTip.showText(screen, text + " ", self._view)
            QToolTip.showText(screen, text, self._view, QRect(), _TIP_HOLD_MS)
        self._showing = text

    def eventFilter(self, obj, event) -> bool:
        kind = event.type()
        if kind == QEvent.ToolTip:
            self._show_under(event.globalPos())
            # Unanswered, the scene would hide any tip none of its items own.
            return True
        if kind == QEvent.MouseMove:
            self._show_at(event.position().toPoint())
        elif kind in (QEvent.Leave, QEvent.Hide):
            self._show_at(None)
        elif kind == QEvent.Resize:
            self.refresh()
        elif kind == QEvent.MouseButtonPress:
            # The release that ends a double-click can be lost to the popup it opened.
            self._doubled = False
        elif (
            kind == QEvent.MouseButtonDblClick
            and event.button() == Qt.LeftButton
            and self._click is not None
        ):
            self._click.stop()
            self._clicked = None
            self._doubled = True
        elif kind == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            row = bar_row_at(self._chart, self._view, event.position().toPoint())
            if self._doubled:
                self._doubled = False  # the release that ends a double-click
            elif row is not None and self._click is None:
                self._activated(row)
            elif row is not None:
                self._activate_click()  # an earlier click still waiting is a click of its own
                self._clicked = row
                self._click.start()
        return False

    def _activate_click(self) -> None:
        self._click.stop()
        row, self._clicked = self._clicked, None
        if row is not None:
            self._activated(row)


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
