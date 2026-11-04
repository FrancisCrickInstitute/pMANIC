from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
)

from manic.models.database import get_deleted_compounds, soft_delete_compound
from manic.ui.compound_recovery_dialog import CompoundRecoveryDialog
from manic.ui.theme import set_style_property


class CompoundListWidget(QListWidget):
    internal_standard_selected = Signal(str)
    compounds_deleted = Signal(list)  # Emits list of deleted compound names
    compounds_restored = Signal(list)  # Emits list of restored compound names
    add_compound_requested = Signal()
    internal_standard_cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setMinimumHeight(72)
        self.setUniformItemSizes(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemSelectionChanged.connect(self._center_current_item)
        # Track pending selection index for post-deletion selection
        self._pending_selection_index = None
        self._context_item: QListWidgetItem | None = None

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

    def update_compounds(
        self, compounds: List[str], selected_name: str | None = None
    ):
        # Block signals during update to prevent multiple selection events
        self.blockSignals(True)

        self.clear()
        if not compounds:
            self._show_empty()
        else:
            for c in compounds:
                self.addItem(QListWidgetItem(c))
            if selected_name and selected_name in compounds:
                self.setCurrentRow(compounds.index(selected_name))
                self._pending_selection_index = None
            elif self._pending_selection_index is not None:
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

    def real_names(self) -> List[str]:
        """Compound names in list order, without the empty-list placeholder."""
        return [
            item.text()
            for item in (self.item(row) for row in range(self.count()))
            if item and not item.text().startswith("- No")
        ]

    def real_count(self) -> int:
        return len(self.real_names())

    def mousePressEvent(self, event):
        # Right-click selects the item, selection centres it, and the list scrolls
        # before the context menu is requested. Capture the target now, while it
        # is still under the cursor.
        if event.button() == Qt.RightButton:
            self._context_item = self.itemAt(event.position().toPoint())
        super().mousePressEvent(event)

    def _show_context_menu(self, position):
        """Show context menu when right-clicking on a compound"""
        item = self._context_item or self.itemAt(position)
        self._context_item = None
        menu = QMenu(self)


        add_action = menu.addAction("Add Compound...")
        add_action.triggered.connect(self.add_compound_requested.emit)
        menu.addSeparator()

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
            total_compounds = self.real_count()
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

        confirm = msg_box.button(QMessageBox.StandardButton.Yes)
        confirm.setText("Delete")
        set_style_property(confirm, "variant", "danger")
        msg_box.button(QMessageBox.StandardButton.No).setText("Cancel")

        reply = msg_box.exec()

        if reply == QMessageBox.StandardButton.Yes:
            # Calculate the next index to select after deletion
            current_index = self.currentRow()
            total_before = self.real_count()

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
