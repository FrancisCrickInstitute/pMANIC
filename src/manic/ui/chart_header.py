"""Title row for the sidebar summary charts, with a visible enlarge button."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from manic.ui import theme
from manic.ui.chart_style import text_style, ui_font
from manic.ui.icon_button import ThemedToolButton
from manic.ui.theme import color


def expand_icon() -> QIcon:
    """Two arrows pointing out to opposite corners."""
    size = 16
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(color("text_secondary"), 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    lo, hi, arm = 3.0, size - 3.0, 4.0
    for (cx, cy), (dx, dy) in (((hi, lo), (-1, 1)), ((lo, hi), (1, -1))):
        corner = QPointF(cx, cy)
        painter.drawLine(corner, QPointF(cx + dx * arm, cy))
        painter.drawLine(corner, QPointF(cx, cy + dy * arm))
        painter.drawLine(corner, QPointF(cx + dx * 4.5, cy + dy * 4.5))
    painter.end()
    return QIcon(pixmap)


class ChartHeader(QWidget):
    """'TOTAL ABUNDANCE ............ [expand]' above a summary chart."""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.title = QLabel(title.upper())
        font = ui_font(11, QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0.5)
        self.title.setFont(font)
        theme.style(self.title, text_style("text_tertiary", 11, 600))

        self.detail = QLabel()
        theme.style(self.detail, text_style("text_tertiary", 11))

        self.expand_button = ThemedToolButton(expand_icon)
        self.expand_button.setIconSize(QSize(16, 16))
        self.expand_button.setAutoRaise(True)
        self.expand_button.setProperty("variant", "ghost")
        self.expand_button.setCursor(Qt.PointingHandCursor)
        self.expand_button.setToolTip("Enlarge with sample names (or double-click the chart)")
        self.expand_button.setFixedSize(24, 24)
        self.expand_button.setEnabled(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 0)
        layout.setSpacing(6)
        layout.addWidget(self.title)
        layout.addWidget(self.detail)
        layout.addStretch()
        layout.addWidget(self.expand_button)

    def set_has_data(self, has_data: bool, detail: str = "") -> None:
        self.expand_button.setEnabled(has_data)
        self.detail.setText(detail if has_data else "")
