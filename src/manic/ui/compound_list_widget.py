from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
)

from manic.constants import FONT
from manic.models.database import get_deleted_compounds, soft_delete_compound
from manic.ui.compound_recovery_dialog import CompoundRecoveryDialog


class CompoundListWidget(QListWidget):
    internal_standard_selected = Signal(str)
    compounds_deleted = Signal(list)  # Emits list of deleted compound names
    compounds_restored = Signal(list)  # Emits list of restored compound names
    internal_standard_cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setFont(QFont(FONT, 10))
        self.setMaximumHeight(150)
        self.setMinimumHeight(80)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemSelectionChanged.connect(self._center_current_item)
        # Track pending selection index for post-deletion selection
        self._pending_selection_index = None

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

    def _center_current_item(self):
        item = self.currentItem()
        if not item or item.text().startswith("- No"):
            return
        self.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)

    def update_compounds(self, compounds: List[str]):
        # Block signals during update to prevent multiple selection events
        self.blockSignals(True)

        self.clear()
        if not compounds:
            self._show_empty()
        else:
            for c in compounds:
                self.addItem(QListWidgetItem(c))
            # Select appropriate row (pending selection from deletion, or first by default)
            if self._pending_selection_index is not None:
                row_to_select = min(self._pending_selection_index, len(compounds) - 1)
                self.setCurrentRow(row_to_select)
                self._pending_selection_index = None
            else:
                self.setCurrentRow(0)

        # Re-enable signals after update is complete
        self.blockSignals(False)

        # Emit a single selection changed signal if we have a selection
        if self.currentItem():
            self.itemSelectionChanged.emit()
            self._center_current_item()

    def _get_total_compound_count(self) -> int:
        """Get total number of real compounds (excluding placeholder)"""
        count = 0
        for i in range(self.count()):
            item = self.item(i)
            if item and not item.text().startswith("- No"):
                count += 1
        return count

    def _show_context_menu(self, position):
        """Show context menu when right-clicking on a compound"""
        item = self.itemAt(position)
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
            QMenu::item:disabled {
                color: #999999;
            }
            QMenu::separator {
                height: 1px;
                background-color: #d0d0d0;
                margin: 4px 10px;
            }
        """)

        # Check if we clicked on a valid compound
        valid_item = item and not item.text().startswith("- No")

        if valid_item:
            # Add "Select as Internal Standard" action
            select_standard_action = menu.addAction("Select as Internal Standard")
            select_standard_action.triggered.connect(
                lambda: self.internal_standard_selected.emit(item.text())
            )

            # Add separator
            menu.addSeparator()

            # Add "Delete Compound" action
            delete_action = menu.addAction("Delete Compound")
            
            # Disable delete if this is the only compound
            total_compounds = self._get_total_compound_count()
            can_delete = total_compounds > 1
            delete_action.setEnabled(can_delete)
            delete_action.triggered.connect(
                lambda: self._confirm_delete_compound(item.text())
            )

            # Add separator
            menu.addSeparator()

        # Recover action (always available)
        recover_action = menu.addAction("Recover Deleted Compounds...")
        deleted_compounds = get_deleted_compounds()
        recover_action.setEnabled(len(deleted_compounds) > 0)
        recover_action.triggered.connect(self._show_recovery_dialog)

        # Add separator
        menu.addSeparator()

        # Add the Clear action (always available)
        clear_std_action = QAction("Clear Internal Standard", self)
        clear_std_action.triggered.connect(
            lambda: self.internal_standard_cleared.emit()
        )
        menu.addAction(clear_std_action)

        menu.exec_(self.mapToGlobal(position))

    def _confirm_delete_compound(self, compound_name: str):
        """Show confirmation dialog before deleting compound"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Delete Compound")
        msg_box.setText(f"Are you sure you want to delete compound '{compound_name}'?")
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

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
            # Calculate the next index to select after deletion
            current_index = self.currentRow()
            total_before = self._get_total_compound_count()

            if current_index >= total_before - 1:
                # Deleting last item, select the new last item (previous one)
                self._pending_selection_index = max(0, current_index - 1)
            else:
                # Deleting non-last item, stay at same index (next item moves up)
                self._pending_selection_index = current_index

            # Perform deletion
            if soft_delete_compound(compound_name):
                self.compounds_deleted.emit([compound_name])

    def _show_recovery_dialog(self):
        """Show the compound recovery dialog"""
        dialog = CompoundRecoveryDialog(self)
        dialog.compounds_restored.connect(self.compounds_restored.emit)
        dialog.exec()
