from typing import List

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from src.manic.utils.constants import FONT


class CompoundListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setFont(QFont(FONT, 10))
        self.setMaximumHeight(150)
        self.setMinimumHeight(80)
        # Custom scrollbar styling with rounded edges
        self.setStyleSheet("""
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 10px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
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
