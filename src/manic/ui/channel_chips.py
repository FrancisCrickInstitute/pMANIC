"""Chip row naming each plotted channel, with a swatch of its trace pen."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QWidget

from manic.constants import create_font
from manic.ui.colors import ChannelTraceStyle

SWATCH_WIDTH = 18
CHIP_HEIGHT = 20
PAD_X = 8
GAP = 6


class ChannelChip(QWidget):
    def __init__(self, label: str, style: ChannelTraceStyle, parent=None):
        super().__init__(parent)
        self.label = label
        self.style = style
        self.setFont(create_font(9))
        text_width = QFontMetrics(self.font()).horizontalAdvance(label)
        self.setFixedSize(PAD_X + SWATCH_WIDTH + GAP + text_width + PAD_X, CHIP_HEIGHT)
        self.setToolTip(label)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        fill = QColor(self.style.color)
        fill.setAlpha(60)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, CHIP_HEIGHT / 2, CHIP_HEIGHT / 2)

        y = rect.center().y()
        painter.setPen(QPen(self.style.color, 2, self.style.line_style, Qt.FlatCap))
        painter.drawLine(PAD_X, y, PAD_X + SWATCH_WIDTH, y)

        painter.setPen(QColor("#222"))
        painter.drawText(
            QRectF(PAD_X + SWATCH_WIDTH + GAP, 0, rect.width(), rect.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.label,
        )


class ChannelChipRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 3, 4, 3)
        self._layout.setSpacing(GAP)
        self._layout.addStretch()
        self.hide()

    def set_channels(
        self, labels: Sequence[str], styles: Sequence[ChannelTraceStyle]
    ) -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            item.widget().deleteLater()
        for label, style in zip(labels, styles):
            self._layout.insertWidget(self._layout.count() - 1, ChannelChip(label, style))
        self.setVisible(bool(labels))

    def chips(self) -> list[ChannelChip]:
        return [
            self._layout.itemAt(i).widget() for i in range(self._layout.count() - 1)
        ]

    def labels(self) -> list[str]:
        return [chip.label for chip in self.chips()]
