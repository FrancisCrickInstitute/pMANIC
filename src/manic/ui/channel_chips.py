"""Chip row naming each plotted channel, with a swatch of its trace pen."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QWidget

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
        f"{channel.label}   {qualifier_expectation(channel)}"
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


class ChannelChip(QWidget):
    def __init__(self, label: str, style: ChannelTraceStyle, parent=None):
        super().__init__(parent)
        self.label = label
        self.style = style
        self.setFont(ui_font(11))
        text_width = QFontMetrics(self.font()).horizontalAdvance(label)
        self.setFixedSize(PAD_X + SWATCH_WIDTH + GAP + text_width + PAD_X, CHIP_HEIGHT)
        self.setToolTip(label)

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
        painter.drawText(
            QRectF(PAD_X + SWATCH_WIDTH + GAP, 0, rect.width(), rect.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.label,
        )


class ChannelChipRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(GAP)
        self._layout.addStretch()
        self.hide()

    def set_channels(
        self, labels: Sequence[str], styles: Sequence[ChannelTraceStyle]
    ) -> None:
        while self._layout.count() > 1:
            chip = self._layout.takeAt(0).widget()
            # Hidden at once: deleteLater waits for the event loop.
            chip.hide()
            chip.deleteLater()
        for label, style in zip(labels, styles):
            self._layout.insertWidget(self._layout.count() - 1, ChannelChip(label, style))
        self.setVisible(bool(labels))

    def chips(self) -> list[ChannelChip]:
        return [
            self._layout.itemAt(i).widget() for i in range(self._layout.count() - 1)
        ]

    def labels(self) -> list[str]:
        return [chip.label for chip in self.chips()]
