from typing import List

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from src.manic.utils.constants import FONT


class SampleListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setFont(QFont(FONT, 10))
        self.setMaximumHeight(150)
        self.setMinimumHeight(80)
        self._show_empty()

    def _show_empty(self):
        self.clear()
        item = QListWidgetItem("- No Samples Loaded -")
        self.addItem(item)
        self.setCurrentItem(item)

    def update_samples(self, samples: List[str]):
        self.clear()
        if not samples:
            self._show_empty()
        else:
            for s in samples:
                self.addItem(QListWidgetItem(s))
            self.selectAll()
