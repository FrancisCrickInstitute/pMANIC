"""Small building blocks for the sidebar: headings, filters, status rows, sections."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSettings, QSize, Qt, Signal
from PySide6.QtGui import (
    QFont,
    QFontMetrics,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from manic.ui import theme
from manic.ui.theme import FONT_SIZE_SMALL, color, set_style_property


def shortcut_text(sequence: str) -> str:
    """'Ctrl+O' as this platform writes it (⌘O on macOS)."""
    return QKeySequence(sequence).toString(QKeySequence.SequenceFormat.NativeText)


def section_heading(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setProperty("role", "section")
    font = QFont(label.font())
    font.setPixelSize(FONT_SIZE_SMALL)
    font.setWeight(QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
    label.setFont(font)
    return label


# A bar row needs this many pixels before the sample axis can name it without
# QtCharts dropping labels that would touch.
NAME_ROW_PX = 16
SUMMARY_CHART_MAX_HEIGHT = 330
# Rows a summary keeps when the sidebar is short; the rest scroll under the pinned axis.
SUMMARY_SHORT_ROWS = 2


def fit_category_names(axis, names: list[str], view_width: int) -> None:
    """Shorten names in the middle to fit a sidebar chart's name column.

    QtCharts gives the name axis at most 40% of the chart and lets a longer name
    run off its edge (or, truncating, leaves only "…"). Hover gives the full name.
    """
    metrics = QFontMetrics(axis.labelsFont())
    width = int(view_width * 0.4) - 8
    fitted = [metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, width) for name in names]
    # A category axis needs unique names.
    if len(set(fitted)) == len(fitted) and fitted != axis.categories():
        axis.setCategories(fitted)


class SummaryChartArea(QScrollArea):
    """A summary chart tall enough to name every bar; rows past the widget's height scroll.

    It asks for only a few rows, so a short sidebar fits every summary without
    scrolling around them; the sidebar's stretch gives it more when there is room.
    """

    def __init__(self, chart_view: QWidget, axis_px: int, parent=None):
        super().__init__(parent)
        self._view = chart_view
        self._axis_px = axis_px
        self._short = axis_px + NAME_ROW_PX
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(chart_view)
        self.viewport().setAutoFillBackground(False)

    def set_rows(self, count: int) -> None:
        self._view.setMinimumHeight(self._axis_px + count * NAME_ROW_PX)
        self._short = self._axis_px + min(max(count, 1), SUMMARY_SHORT_ROWS) * NAME_ROW_PX
        self.updateGeometry()

    def minimumSizeHint(self) -> QSize:
        return QSize(super().minimumSizeHint().width(), self._short)

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), self._short)

    def show_rows(self, chart, rows: list[int]) -> None:
        """Scroll the topmost of these bar rows into view; row 0 is the bottom bar."""
        if rows and chart.series():
            y = chart.mapToPosition(QPointF(0, max(rows)), chart.series()[0]).y()
            self.ensureVisible(0, int(y), 0, NAME_ROW_PX)


class WholeRowsArea(QScrollArea):
    """Rows that are never cut through: all of them when they fit, else one whole row
    at a time, scrolled a row at a time."""

    def __init__(self, parent=None):
        super().__init__(parent)
        body = QWidget()
        self.rows = QVBoxLayout(body)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(8)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(body)
        self.viewport().setAutoFillBackground(False)
        body.setAutoFillBackground(False)
        self._step = 0
        self._at = 0
        self.verticalScrollBar().valueChanged.connect(self._snap)

    def _heights(self) -> list[int]:
        rows = (self.rows.itemAt(i).widget() for i in range(self.rows.count()))
        return [row.sizeHint().height() for row in rows if row is not None and not row.isHidden()]

    def full_height(self) -> int:
        heights = self._heights()
        return sum(heights) + self.rows.spacing() * max(len(heights) - 1, 0)

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), self.full_height())

    def minimumSizeHint(self) -> QSize:
        return QSize(super().minimumSizeHint().width(), max(self._heights(), default=0))

    def fit(self, room: int) -> None:
        """Show every row if ``room`` holds them, else one at a time, each as tall as the tallest."""
        tallest = max(self._heights(), default=0)
        paged = room < self.full_height()
        for index in range(self.rows.count()):
            row = self.rows.itemAt(index).widget()
            if row is not None:
                row.setMinimumHeight(tallest if paged else 0)
        self._step = tallest + self.rows.spacing() if paged else 0
        self.setMaximumHeight(tallest if paged else self.full_height())
        self._snap(self.verticalScrollBar().value())

    def _snap(self, value: int) -> None:
        bar = self.verticalScrollBar()
        if not self._step or value % self._step == 0 or value == bar.maximum():
            self._at = value
            return
        # Any scroll moves a whole row in its direction.
        step = self._step if value > self._at else -self._step
        bar.setValue(max(bar.minimum(), min(self._at + step, bar.maximum())))


def divider() -> QFrame:
    line = QFrame()
    line.setProperty("role", "divider")
    line.setFixedHeight(1)
    return line


def status_pixmap(state: str) -> QPixmap:
    """Done: filled check. Optional/blocked: an empty ring."""
    size = 14
    ratio = 2.0
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    box = QRectF(1, 1, size - 2, size - 2)
    if state == "done":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color("success"))
        painter.drawEllipse(box)
        tick = QPainterPath(QPointF(size * 0.30, size * 0.52))
        tick.lineTo(QPointF(size * 0.45, size * 0.66))
        tick.lineTo(QPointF(size * 0.71, size * 0.37))
        pen = QPen(color("surface"), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(tick)
    else:
        pen = QPen(color("border_strong"), 1.4)
        if state == "optional":
            pen.setDashPattern([2, 2])
        painter.setPen(pen)
        painter.drawEllipse(box.adjusted(0.5, 0.5, -0.5, -0.5))
    painter.end()
    return pixmap


class ElidedLabel(QLabel):
    """A one-line label that elides instead of widening its parent.

    ``hover`` is shown as the tooltip only while the text is cut; True shows the full text."""

    def __init__(
        self,
        text: str = "",
        parent=None,
        *,
        mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
        hover: str | bool = False,
    ):
        super().__init__(parent)
        self._full = text
        self._mode = mode
        self._hover = hover
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt override)
        self._full = text
        self._elide()

    def full_text(self) -> str:
        return self._full

    def resizeEvent(self, event):
        self._elide()
        super().resizeEvent(event)

    def _elide(self) -> None:
        metrics = QFontMetrics(self.font())
        width = max(self.width(), 0)
        shown = metrics.elidedText(self._full, self._mode, width) if width else self._full
        super().setText(shown)
        if self._hover:
            hover = self._full if self._hover is True else self._hover
            self.setToolTip(hover if shown != self._full else "")


class StatusRow(QPushButton):
    """A clickable header row: state icon, title, and a right-aligned value."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setProperty("role", "statusRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(8)
        self._icon = QLabel()
        self._icon.setFixedSize(14, 14)
        self._title = QLabel(title)
        self._value = ElidedLabel()
        self._value.setObjectName("statusValue")
        self._value.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        for child in (self._icon, self._title, self._value):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._icon)
        layout.addWidget(self._title)
        layout.addWidget(self._value, 1)
        self.setFixedHeight(26)
        self.set_state("blocked", "")
        theme.notifier.changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, _remap: dict) -> None:
        self._icon.setPixmap(status_pixmap(self._state))

    def set_state(self, state: str, value: str) -> None:
        self._state = state
        self._icon.setPixmap(status_pixmap(state))
        self._value.setText(value)
        set_style_property(self._value, "state", state)


class FilterField(QLineEdit):
    """Filters a list as you type. Arrow keys move through the list; Enter picks."""

    filtered = Signal()

    def __init__(self, target: QListWidget, placeholder: str, parent=None):
        super().__init__(parent)
        self._target = target
        self.setProperty("role", "search")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.textChanged.connect(self.reapply)

    def reapply(self) -> None:
        needle = self.text().strip().casefold()
        for row in range(self._target.count()):
            item = self._target.item(row)
            hidden = bool(needle) and needle not in item.text().casefold()
            self._target.setRowHidden(row, hidden)
        self.filtered.emit()

    def visible_count(self) -> int:
        return sum(
            1 for row in range(self._target.count()) if not self._target.isRowHidden(row)
        )

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            QApplication.sendEvent(self._target, event)
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current = self._target.currentRow()
            if current < 0 or self._target.isRowHidden(current):
                first = next(
                    (
                        row
                        for row in range(self._target.count())
                        if not self._target.isRowHidden(row)
                    ),
                    None,
                )
                if first is not None:
                    self._target.setCurrentRow(first)
            self._target.setFocus()
            return
        if key == Qt.Key.Key_Escape and self.text():
            self.clear()
            return
        super().keyPressEvent(event)


class CollapsibleSection(QWidget):
    """A section whose heading row toggles its body; the heading shows a summary.

    With ``settings_key`` the open/closed state a user picks is remembered."""

    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        body: QWidget,
        expanded: bool = False,
        parent=None,
        settings_key: str | None = None,
    ):
        super().__init__(parent)
        self.body = body
        self._settings_key = settings_key
        if settings_key:
            expanded = QSettings().value(settings_key, expanded, type=bool)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.header = QPushButton()
        self.header.setProperty("role", "sectionToggle")
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(self.header)
        row.setContentsMargins(0, 0, 2, 0)
        row.setSpacing(6)
        self._chevron = QLabel()
        self._chevron.setProperty("role", "section")
        self._chevron.setFixedWidth(10)
        self._title = section_heading(title)
        self.summary = ElidedLabel()
        self.summary.setProperty("role", "hint")
        self.summary.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        for child in (self._chevron, self._title, self.summary):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(self._chevron)
        row.addWidget(self._title)
        row.addWidget(self.summary, 1)
        self.header.setFixedHeight(24)
        self.header.clicked.connect(self._on_header_clicked)

        layout.addWidget(self.header)
        layout.addWidget(body)
        self._headless = False
        self._expanded = not expanded
        self.set_expanded(expanded)

    def _on_header_clicked(self) -> None:
        self.set_expanded(not self.is_expanded())
        if self._settings_key:
            QSettings().setValue(self._settings_key, self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self._chevron.setText("▾" if expanded else "▸")
        self.body.setVisible(expanded or self._headless)
        self.header.setToolTip("Collapse" if expanded else "Expand")
        self.toggled.emit(expanded)

    def set_headless(self, headless: bool) -> None:
        """Hide the heading and always show the body, while a switcher stands in for it."""
        self._headless = headless
        self.header.setVisible(not headless)
        self.body.setVisible(headless or self._expanded)
