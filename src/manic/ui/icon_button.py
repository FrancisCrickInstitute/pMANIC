from collections.abc import Callable

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPainter
from PySide6.QtWidgets import QToolButton

from manic.ui import theme
from manic.utils.paths import resource_path


def svg_icon(svg: str) -> QIcon:
    """A resource SVG recoloured to the secondary text colour."""
    pixmap = QIcon(resource_path("resources", svg)).pixmap(QSize(40, 40))
    pixmap.setDevicePixelRatio(2)
    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), theme.color("text_secondary"))
    painter.end()
    return QIcon(pixmap)


class ThemedToolButton(QToolButton):
    """Tool button whose icon is drawn from theme tokens and redrawn on a scheme switch."""

    def __init__(self, make_icon: Callable[[], QIcon], parent=None):
        super().__init__(parent)
        self._make_icon = make_icon
        self.setIcon(make_icon())
        theme.notifier.changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, _remap: dict) -> None:
        self.setIcon(self._make_icon())


def icon_button(object_name: str, svg: str, tooltip: str) -> QToolButton:
    button = ThemedToolButton(lambda: svg_icon(svg))
    button.setObjectName(object_name)
    button.setIconSize(QSize(20, 20))
    button.setAutoRaise(True)
    button.setToolTip(tooltip)
    return button
