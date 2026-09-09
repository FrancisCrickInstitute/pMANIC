import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import QLabel, QSizePolicy

from manic.constants import BLUE, GREEN, GREY, RED, create_font


class TitledPill(QLabel):
    """A full-width status pill reading ``Title: value``, elided to fit."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._full_text = ""
        self.setFont(create_font(10))
        self.setAlignment(Qt.AlignCenter)
        # Ignored: the text must never widen the toolbar, it elides to fit instead
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setFixedHeight(22 if sys.platform == "win32" else 20)

    def set_value(self, value: str, color: QColor) -> None:
        self._full_text = f"{self._title}: {value}"
        self.setToolTip(self._full_text)
        self.setStyleSheet(
            f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, "
            f"{color.alpha() / 255}); color: black; border-radius: 10px; padding: 2px;"
        )
        self._elide()

    def resizeEvent(self, event):
        self._elide()
        super().resizeEvent(event)

    def _elide(self) -> None:
        available = self.width() - 12
        self.setText(
            QFontMetrics(self.font()).elidedText(
                self._full_text, Qt.ElideRight, available
            )
        )


class StandardIndicator(TitledPill):
    def __init__(self, parent=None):
        super().__init__("Int Std", parent)
        self.internal_standard = None
        self.set_value("none", RED)

    def set_internal_standard(self, compound_name: str):
        self.internal_standard = compound_name
        self.set_value(compound_name, GREEN)

    def clear_internal_standard(self):
        self.internal_standard = None
        self.set_value("none", RED)


class CompoundIndicator(TitledPill):
    def __init__(self, parent=None):
        super().__init__("Compound", parent)
        self.set_compound("")

    def set_compound(self, compound_name: str):
        if compound_name:
            self.set_value(compound_name, BLUE)
        else:
            self.set_value("--", GREY)
