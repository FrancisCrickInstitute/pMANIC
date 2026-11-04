"""Chip row naming each plotted channel, with a swatch of its trace pen."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QWidget, QWidgetItem

from manic.models.analysis import IonChannel, IonRole
from manic.ui.chart_style import ui_font
from manic.ui.colors import QUALIFIER_GREY, ChannelTraceStyle, legend_trace_styles
from manic.ui.theme import color
from manic.validation.unlabelled_identity import qualifier_expectation

SWATCH_WIDTH = 16
CHIP_HEIGHT = 22
PAD_X = 9
GAP = 6


def identity_key_chips(
    channels: Sequence[IonChannel],
) -> tuple[list[str], list[ChannelTraceStyle]]:
    """Chips for the Identity view: every channel with its expectation, plus a
    dotted placeholder for each of the two qualifier slots the method left empty."""
    labels = [
        f"{channel.label}   {_expectation(channel)}"
        if channel.role is IonRole.QUALIFIER
        else channel.label
        for channel in channels
    ]
    styles = list(legend_trace_styles(channels, unlabelled=True, multi_trace=True))
    present = {channel.ordinal for channel in channels if channel.role is IonRole.QUALIFIER}
    for ordinal in (1, 2):
        if ordinal not in present:
            labels.append(f"Qualifier ion {ordinal}   not in the method")
            styles.append(ChannelTraceStyle(QUALIFIER_GREY, Qt.DotLine))
    return labels, styles


def _expectation(channel: IonChannel) -> str:
    if channel.expected_ratio is None:
        return "no expected ratio"
    return qualifier_expectation(channel)


class ChannelChip(QWidget):
    def __init__(self, label: str, style: ChannelTraceStyle, parent=None):
        super().__init__(parent)
        self.label = label
        self.style = style
        self.setFont(ui_font(11))
        metrics = QFontMetrics(self.font())
        chrome = PAD_X + SWATCH_WIDTH + GAP + PAD_X
        self._full = QSize(chrome + metrics.horizontalAdvance(label), CHIP_HEIGHT)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setFixedHeight(CHIP_HEIGHT)
        self.setToolTip(label)

    def sizeHint(self) -> QSize:
        return self._full

    def minimumSizeHint(self) -> QSize:
        return QSize(PAD_X * 2 + SWATCH_WIDTH, CHIP_HEIGHT)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        painter.setPen(QPen(color("border"), 1))
        painter.setBrush(color("surface"))
        painter.drawRoundedRect(rect, CHIP_HEIGHT / 2, CHIP_HEIGHT / 2)

        y = rect.center().y()
        painter.setPen(QPen(self.style.color, 2.5, self.style.line_style, Qt.RoundCap))
        painter.drawLine(PAD_X, y, PAD_X + SWATCH_WIDTH, y)

        painter.setPen(color("text"))
        text_left = PAD_X + SWATCH_WIDTH + GAP
        text_width = int(rect.width()) - text_left - PAD_X + 2
        painter.drawText(
            QRectF(text_left, 0, text_width, rect.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            QFontMetrics(self.font()).elidedText(self.label, Qt.ElideRight, text_width),
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
    """Channel chips that wrap onto more rows rather than truncating, then an
    optional trailing widget (a colour key) that wraps with them."""

    def __init__(self, parent=None, trailing: QWidget | None = None):
        super().__init__(parent)
        self._layout = FlowLayout(self)
        self._chips: list[ChannelChip] = []
        self.trailing = trailing
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
