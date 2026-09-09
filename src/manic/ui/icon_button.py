from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QToolButton

from manic.utils.paths import resource_path


def icon_button(object_name: str, svg: str, tooltip: str) -> QToolButton:
    button = QToolButton()
    button.setObjectName(object_name)
    button.setIcon(QIcon(resource_path("resources", svg)))
    button.setIconSize(QSize(20, 20))
    button.setAutoRaise(True)
    button.setToolTip(tooltip)
    return button
