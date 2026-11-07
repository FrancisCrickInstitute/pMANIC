from __future__ import annotations

from PySide6.QtCharts import QChart, QChartView
from PySide6.QtCore import QMargins, QPointF, QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsRectItem,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from manic.ui.chart_header import ChartHeader
from manic.ui.chart_popup_dialog import (
    ChartPopupDialog,
    PinnedAxis,
    category_rect,
    identity_key_html,
    IDENTITY_KEY_TOOLTIP,
)
from manic.ui.chart_style import (
    BarRows,
    fit_category_names,
    fit_name_font,
    style_chart,
    text_style,
)
from manic.ui.identity_chart import (
    STATUS_LABELS,
    IdentityGridBinding,
    add_identity_grid,
    identity_cell_tooltip,
    identity_cells,
    identity_chart_height,
    identity_column_headers,
    identity_unassessed_note,
    qualifier_gap_note,
)
from manic.ui import theme
from manic.ui.sidebar_widgets import ROOMY_ROW_PX, SUMMARY_SHORT_ROWS
from manic.ui.theme import color
from manic.validation.unlabelled_identity import IdentityAssessmentSet

# Tall enough for each row's state mark and sample name.
IDENTITY_ROW = 18


class _RowsScroll(QScrollArea):
    """Asks for its minimum height; the panel's stretch grows it up to its maximum.

    Never for the chart's width: a chart view's hint is its last scene width, so
    asking for it would hold the summary wider than the panel.
    """

    def sizeHint(self) -> QSize:
        return QSize(super().minimumSizeHint().width(), self.minimumHeight())

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()


class TargetedQcWidget(QWidget):
    sample_activated = Signal(str)
    # A documentation link from the note, "file.md#section".
    guide_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("targetedQc")

        self.chart = QChart()
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_view.setFrameShape(QFrame.NoFrame)
        self.chart_view.setStyleSheet("QChartView { background: transparent; border: none; }")
        self.chart_view.mouseDoubleClickEvent = self._chart_view_double_click
        # Rows count up from the bottom; samples read top down.
        self._rows = BarRows(
            self.chart,
            self.chart_view,
            lambda row: self.sample_activated.emit(self._identity.samples[-1 - row].sample_name),
            self._row_tip,
        )

        style_chart(self.chart, QMargins(0, 0, 0, 0))

        self.header = ChartHeader("Identity")
        self.header.expand_button.clicked.connect(self._show_popup_chart)

        self._scroll = _RowsScroll()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll.setWidget(self.chart_view)
        self._scroll.hide()
        self.columns = PinnedAxis(self.chart_view)

        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setTextFormat(Qt.RichText)
        self.note.linkActivated.connect(self.guide_requested)
        # In line with the header's title.
        self.note.setContentsMargins(8, 0, 4, 0)
        theme.style(self.note, text_style("text_secondary", 11))
        self.note.hide()

        self.key = QLabel()
        self.key.setTextFormat(Qt.RichText)
        self.key.setWordWrap(True)
        self.key.setAlignment(Qt.AlignHCenter)
        theme.style(self.key, text_style("text_secondary", 11))
        self.key.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 4)
        layout.setSpacing(2)
        layout.addWidget(self.header)
        layout.addWidget(self.columns)
        layout.addWidget(self._scroll)
        layout.addWidget(self.note)
        layout.addWidget(self.key)
        # Grows with the panel, but never past its rows (see _cap_height).
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._identity: IdentityAssessmentSet | None = None
        self._binding: IdentityGridBinding | None = None
        self._highlighted: set[str] = set()
        self._marks: list[QGraphicsRectItem] = []
        self.chart.plotAreaChanged.connect(self._paint_highlight)
        self.chart.plotAreaChanged.connect(self._fit_names)
        theme.notifier.changed.connect(self._paint_highlight)

    def update_results(self, identity: IdentityAssessmentSet) -> None:
        if not identity.samples:
            self.clear()
            return

        self._identity = identity
        self._binding = add_identity_grid(self.chart, identity.samples)
        height = identity_chart_height(len(identity.samples), IDENTITY_ROW)
        self.chart_view.setMinimumHeight(height)
        short = identity_chart_height(SUMMARY_SHORT_ROWS, IDENTITY_ROW)
        self._scroll.setMinimumHeight(min(height, short))
        # With room to spare the rows grow, like the Peak area bars beside them.
        self._scroll.setMaximumHeight(identity_chart_height(len(identity.samples), ROOMY_ROW_PX))
        self.columns.set_axis("", identity_column_headers(identity.channels, detail=False))
        assessed = identity_unassessed_note(identity) is None
        # The grid hides its own note on the gap while this panel is open.
        note = qualifier_gap_note(identity) or identity_unassessed_note(identity)
        self.note.setText(note or "")
        self.note.setVisible(note is not None)
        self._scroll.setVisible(assessed)
        self.columns.setVisible(assessed)
        self._fit_names()
        self._paint_highlight()
        # The footer tallies the failures; a sample count here would be a second number for them.
        self.header.set_has_data(True)
        self.key.setText(identity_key_html(identity, swatches=False))
        self.key.setToolTip(IDENTITY_KEY_TOOLTIP)
        self.key.setVisible(assessed)
        self._cap_height()
        self._rows.refresh()

    def _cap_height(self) -> None:
        """As tall as its rows and no taller, so no band opens below one sample."""
        grow = 0 if self._scroll.isHidden() else (
            self._scroll.maximumHeight() - self._scroll.minimumHeight()
        )
        preferred = self.heightForWidth(self.width()) if self.hasHeightForWidth() else -1
        if preferred < 0:
            preferred = self.sizeHint().height()
        if self.maximumHeight() != preferred + grow:
            self.setMaximumHeight(preferred + grow)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._cap_height()

    def clear(self) -> None:
        self._identity = None
        self._binding = None
        self.header.set_has_data(False)
        for widget in (self.key, self.note, self._scroll, self.columns):
            widget.hide()
        add_identity_grid(self.chart, ())
        self._paint_highlight()
        self._cap_height()
        self._rows.refresh()

    def _fit_names(self, *_args) -> None:
        axes = self.chart.axes(Qt.Vertical)
        if self._identity is not None and axes:
            fit_name_font(self.chart, axes[0])
            fit_category_names(
                axes[0],
                [sample.sample_name for sample in reversed(self._identity.samples)],
                self.chart_view.width(),
            )

    def set_highlighted(self, sample_names) -> None:
        """Outline the rows of the samples selected in the grid and scroll to the first; every row stays."""
        self._highlighted = set(sample_names)
        self._paint_highlight()
        if self._marks:
            first = min(self._marks, key=lambda mark: mark.rect().top())
            centre = self.chart_view.mapFromScene(first.sceneBoundingRect().center())
            self._scroll.ensureVisible(centre.x(), centre.y(), 0, int(first.rect().height()))

    def _paint_highlight(self, *_args) -> None:
        for mark in self._marks:
            if mark.scene() is not None:
                mark.scene().removeItem(mark)
        self._marks = []
        if self._identity is None or not self.chart.series():
            return
        names = [sample.sample_name for sample in self._identity.samples]
        for row, name in enumerate(names):
            if name not in self._highlighted:
                continue
            mark = QGraphicsRectItem(category_rect(self.chart, len(names) - 1 - row), self.chart)
            mark.setPen(QPen(color("accent"), 1.5))
            mark.setBrush(Qt.NoBrush)
            mark.setZValue(20)
            self._marks.append(mark)

    def _row_tip(self, row: int, value: QPointF) -> str:
        """Over a cell its own detail; over the name, the sample and each qualifier's state."""
        cell = self._binding.cell_at(value)
        if cell is not None:
            return identity_cell_tooltip(cell)
        sample = self._identity.samples[-1 - row]
        states = (f"Qualifier {q.ordinal}  {STATUS_LABELS[q.status]}" for q in identity_cells(sample))
        return "\n".join((sample.sample_name, *states))

    def _has_data(self) -> bool:
        return self._identity is not None and bool(self._identity.samples)

    def _chart_view_double_click(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._has_data():
            self._show_popup_chart()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._has_data():
            self._show_popup_chart()
        super().mouseDoubleClickEvent(event)

    def _show_popup_chart(self) -> None:
        if self._identity is None:
            return
        dialog = ChartPopupDialog.for_identity(self._identity, parent=self)
        dialog.sample_activated.connect(self.sample_activated)
        dialog.guide_requested.connect(self.guide_requested)
        dialog.exec()
