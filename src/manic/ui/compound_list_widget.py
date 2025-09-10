from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMenu, QMessageBox

from manic.constants import FONT


class CompoundListWidget(QListWidget):
    internal_standard_selected = Signal(str)
    compound_deleted = Signal(str)

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
        # Block signals during update to prevent multiple selection events
        self.blockSignals(True)

        self.clear()
        if not compounds:
            self._show_empty()
        else:
            for c in compounds:
                self.addItem(QListWidgetItem(c))
            # select first by default
            self.setCurrentRow(0)

        # Re-enable signals after update is complete
        self.blockSignals(False)

        # Emit a single selection changed signal if we have a selection
        if self.currentItem():
            self.itemSelectionChanged.emit()

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
                    border: none;
                }
                QMenu::item {
                    background-color: white;
                    color: black;
                    padding: 5px 15px;
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

            # Add separator
            menu.addSeparator()

            # Add "Delete Compound" action
            delete_action = menu.addAction("Delete Compound")
            delete_action.triggered.connect(
                lambda: self._confirm_delete_compound(item.text())
            )

            menu.exec_(self.mapToGlobal(position))

    def _confirm_delete_compound(self, compound_name: str):
        """Show confirmation dialog before deleting compound"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Delete Compound")
        msg_box.setText(f"Are you sure you want to delete compound '{compound_name}'?")
        msg_box.setInformativeText(
            "This will remove the compound from the list and from any exported data. "
            "You can restore it later from Settings > Recover Deleted Compounds."
        )
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        # Remove the icon to match the rest of the app

        # Style the message box with clean styling, no borders or images
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: white;
                color: black;
                border: none;
            }
            QMessageBox QLabel {
                color: black;
                background-color: transparent;
                border: none;
            }
            QMessageBox QPushButton {
                background-color: #f0f0f0;
                color: black;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                min-width: 70px;
                font-weight: normal;
            }
            QMessageBox QPushButton:hover {
                background-color: #e0e0e0;
            }
            QMessageBox QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QMessageBox QFrame {
                border: none;
            }
            QMessageBox * {
                border: none;
            }
        """)

        reply = msg_box.exec()

        if reply == QMessageBox.StandardButton.Yes:
            self.compound_deleted.emit(compound_name)
