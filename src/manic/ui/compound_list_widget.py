from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMenu

from manic.constants import FONT


class CompoundListWidget(QListWidget):
    internal_standard_selected = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setFont(QFont(FONT, 10))
        self.setMaximumHeight(150)
        self.setMinimumHeight(80)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
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
    
    def _show_context_menu(self, position):
        """Show context menu when right-clicking on a compound"""
        item = self.itemAt(position)
        if item and not item.text().startswith("- No"):
            menu = QMenu(self)
            # Set menu style to ensure black text on white background
            menu.setStyleSheet("""
                QMenu {
                    background-color: white;
                    color: black;
                    border: 1px solid #d0d0d0;
                }
                QMenu::item {
                    background-color: white;
                    color: black;
                    padding: 5px 20px;
                }
                QMenu::item:selected {
                    background-color: #e0e0e0;
                    color: black;
                }
            """)
            
            # Add "Select as Internal Standard" action
            select_standard_action = menu.addAction("Select as Internal Standard")
            select_standard_action.triggered.connect(
                lambda: self.internal_standard_selected.emit(item.text())
            )
            
            menu.exec_(self.mapToGlobal(position))
