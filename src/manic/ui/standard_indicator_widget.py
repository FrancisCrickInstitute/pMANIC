from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel

from manic.constants import FONT


class StandardIndicator(QLabel):
    def __init__(self, parent=None):
        super().__init__("- No Standard Selected -", parent)
        self.setFont(QFont(FONT, 12))
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "border: 1px solid lightgray; border-radius: 10px; padding: 5px;"
        )
