"""Legend row naming each plotted channel, with a swatch of its trace pen."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QWidget, QWidgetItem

from manic.models.analysis import IonChannel, IonRole
from manic.ui.chart_style import ui_font
from manic.ui.colors import ChannelTraceStyle, legend_trace_styles
from manic.ui.theme import color
from manic.validation.unlabelled_identity import qualifier_expectation

SWATCH_WIDTH = 16
CHIP_HEIGHT = 18
GAP = 6
# After each label, so neighbouring entries read as separate.
TRAIL = 10


def identity_key_chips(
    channels: Sequence[IonChannel],
) -> tuple[list[str], list[ChannelTraceStyle]]:
    """Chips for the Identity view: every channel, each qualifier with its expectation."""
    labels = [
        f"{channel.label}   {expectation_text(channel)}"
        if channel.role is IonRole.QUALIFIER
        else channel.label
        for channel in channels
    ]
    return labels, list(legend_trace_styles(channels, unlabelled=True, multi_trace=True))


def expectation_text(channel: IonChannel) -> str:
    """'expected 0.400  ±25%', naming whichever of ratio or tolerance is missing."""
    if channel.expected_ratio is None:
        return "no expected ratio"
    if channel.ratio_tolerance is None:
        return qualifier_expectation(channel).replace("—", "no tolerance")
    return qualifier_expectation(channel)


class ChannelChip(QWidget):
    """A legend entry: a swatch of the trace pen, then the channel name."""

    def __init__(self, label: str, style: ChannelTraceStyle, parent=None):
        super().__init__(parent)
        self.label = label
        self.style = style
        self.setFont(ui_font(11))
        metrics = QFontMetrics(self.font())
        chrome = SWATCH_WIDTH + GAP + TRAIL
        self._full = QSize(chrome + metrics.horizontalAdvance(label), CHIP_HEIGHT)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setFixedHeight(CHIP_HEIGHT)

    def resizeEvent(self, event) -> None:
        self.setToolTip(self.label if self.width() < self._full.width() else "")
        super().resizeEvent(event)

    def sizeHint(self) -> QSize:
        return self._full

    def minimumSizeHint(self) -> QSize:
        return QSize(SWATCH_WIDTH + TRAIL, CHIP_HEIGHT)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        y = self.height() / 2
        painter.setPen(QPen(self.style.color, 2.5, self.style.line_style, Qt.RoundCap))
        painter.drawLine(QPointF(1.5, y), QPointF(SWATCH_WIDTH - 1.5, y))

        painter.setPen(color("text"))
        text_left = SWATCH_WIDTH + GAP
        text_width = self.width() - text_left - TRAIL
        painter.drawText(
            QRectF(text_left, 0, text_width, self.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            QFontMetrics(self.font()).elidedText(self.label, Qt.ElideMiddle, text_width),
        )


class FlowLayout(QLayout):
    """Left-to-right rows that wrap; an item wider than a row is narrowed to fit."""

    def __init__(self, parent=None, spacing: int = GAP):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def insertWidget(self, index: int, widget: QWidget) -> None:
        self.addChildWidget(widget)
        self._items.insert(index, QWidgetItem(widget))
        self.invalidate()

    def remove(self, widget: QWidget) -> None:
        self._items = [item for item in self._items if item.widget() is not widget]
        self.invalidate()

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._arrange(QRect(0, 0, width, 0), move=False)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._arrange(rect, move=True)

    def sizeHint(self) -> QSize:
        visible = [item for item in self._items if not item.isEmpty()]
        width = sum(item.sizeHint().width() for item in visible)
        width += self.spacing() * max(len(visible) - 1, 0)
        height = max((item.sizeHint().height() for item in visible), default=0)
        return QSize(width, height)

    def minimumSize(self) -> QSize:
        heights = [item.minimumSize().height() for item in self._items if not item.isEmpty()]
        return QSize(1, max(heights, default=0))

    def _arrange(self, rect: QRect, *, move: bool) -> int:
        x, y, row_height = rect.x(), rect.y(), 0
        right = rect.right() + 1
        for item in self._items:
            if item.isEmpty():
                continue
            hint = item.sizeHint()
            width = min(hint.width(), rect.width())
            if x > rect.x() and x + width > right:
                x, y, row_height = rect.x(), y + row_height + self.spacing(), 0
            if move:
                item.setGeometry(QRect(QPoint(x, y), QSize(width, hint.height())))
            x += width + self.spacing()
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y()


class ChannelChipRow(QWidget):
    """Channel entries that wrap onto more rows rather than truncating, then an
    optional trailing widget (a colour key) that wraps with them."""

    def __init__(self, parent=None, trailing: QWidget | None = None):
        super().__init__(parent)
        self._layout = FlowLayout(self)
        self._chips: list[ChannelChip] = []
        if trailing is not None:
            self._layout.addWidget(trailing)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.hide()

    def set_channels(
        self, labels: Sequence[str], styles: Sequence[ChannelTraceStyle]
    ) -> None:
        for chip in self._chips:
            self._layout.remove(chip)
            # Hidden at once: deleteLater waits for the event loop.
            chip.hide()
            chip.deleteLater()
        self._chips = [ChannelChip(label, style, self) for label, style in zip(labels, styles)]
        for index, chip in enumerate(self._chips):
            self._layout.insertWidget(index, chip)
            chip.show()
        self.setVisible(bool(labels))
        self.updateGeometry()

    def chips(self) -> list[ChannelChip]:
        return list(self._chips)

    def labels(self) -> list[str]:
        return [chip.label for chip in self.chips()]
