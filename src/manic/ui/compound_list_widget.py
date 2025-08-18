from typing import List

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from src.manic.utils.constants import FONT


class CompoundListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setFont(QFont(FONT, 10))
        self.setFixedHeight(150)
        self._show_empty()

    def _show_empty(self):
        self.clear()
        item = QListWidgetItem("- No Compounds Loaded -")
        self.addItem(item)
        self.setCurrentItem(item)

    def update_compounds(self, compounds: List[str]):
        self.clear()
        if not compounds:
            self._show_empty()
        else:
            for c in compounds:
                self.addItem(QListWidgetItem(c))
            # select first by default
            self.setCurrentRow(0)
