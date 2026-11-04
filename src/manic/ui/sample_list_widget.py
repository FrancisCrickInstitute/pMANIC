from collections.abc import Iterable
from typing import List

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
)

from manic.models.database import get_deleted_samples, soft_delete_samples
from manic.ui.sample_recovery_dialog import SampleRecoveryDialog


class SampleListWidget(QListWidget):
    samples_deleted = Signal(list)  # Emits list of deleted sample names
    samples_restored = Signal(list)  # Emits list of restored sample names

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setMinimumHeight(72)
        self.setUniformItemSizes(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemSelectionChanged.connect(self._center_current_item_if_single_selected)
        self._show_empty()

    def _show_empty(self):
        self.clear()
        item = QListWidgetItem("- No Samples Loaded -")
        self.addItem(item)
        self.setCurrentItem(item)

    def _center_current_item_if_single_selected(self):
        selected_items = self.selectedItems()
        if len(selected_items) != 1:
            return

        item = self.currentItem() or selected_items[0]
        if not item or item.text().startswith("- No"):
            return

        self.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)

    def update_samples(self, samples: List[str]):
        self.clear()
        if not samples:
            self._show_empty()
        else:
            for s in samples:
                self.addItem(QListWidgetItem(s))
            self.selectAll()

        self._center_current_item_if_single_selected()

    def set_selected_samples(self, names: Iterable[str]) -> None:
        wanted = set(names)
        matches = [
            item
            for item in (self.item(index) for index in range(self.count()))
            if item is not None
            and not item.text().startswith("- No")
            and item.text() in wanted
        ]
        if not matches:
            return
        with QSignalBlocker(self):
            self.clearSelection()
            for item in matches:
                item.setSelected(True)
        self.itemSelectionChanged.emit()

    def select_all_samples(self) -> None:
        if self.real_count() == 0:
            return
        with QSignalBlocker(self):
            self.selectAll()
        self.itemSelectionChanged.emit()

    def _get_valid_selected_samples(self) -> List[str]:
        """Get selected sample names, excluding placeholder items"""
        selected = []
        for item in self.selectedItems():
            text = item.text()
            if not text.startswith("- No"):
                selected.append(text)
        return selected

    def real_count(self) -> int:
        """Get total number of real samples (excluding placeholder)"""
        count = 0
        for i in range(self.count()):
            item = self.item(i)
            if item and not item.text().startswith("- No"):
                count += 1
        return count

    def _show_context_menu(self, position):
        """Show context menu when right-clicking on the sample list"""
        menu = QMenu(self)


        # Get selected samples
        selected_samples = self._get_valid_selected_samples()
        total_samples = self.real_count()

        # Delete action
        if len(selected_samples) == 1:
            delete_text = "Delete Sample"
        else:
            delete_text = f"Delete {len(selected_samples)} Samples"

        delete_action = menu.addAction(delete_text)

        # Enable delete only if:
        # - At least one sample is selected
        # - Not deleting ALL samples
        can_delete = len(selected_samples) > 0 and len(selected_samples) < total_samples
        delete_action.setEnabled(can_delete)

        if len(selected_samples) > 0 and len(selected_samples) >= total_samples:
            delete_action.setToolTip("Cannot delete all samples")

        delete_action.triggered.connect(
            lambda: self._confirm_delete_samples(selected_samples)
        )

        # Separator
        menu.addSeparator()

        # Recover action
        recover_action = menu.addAction("Recover Deleted Samples...")
        deleted_samples = get_deleted_samples()
        recover_action.setEnabled(len(deleted_samples) > 0)
        recover_action.triggered.connect(self._show_recovery_dialog)

        menu.exec_(self.mapToGlobal(position))

    def _confirm_delete_samples(self, sample_names: List[str]):
        """Show confirmation dialog before deleting samples"""
        if not sample_names:
            return

        msg_box = QMessageBox(self)

        if len(sample_names) == 1:
            msg_box.setWindowTitle("Delete Sample")
            msg_box.setText(f"Are you sure you want to delete sample '{sample_names[0]}'?")
        else:
            msg_box.setWindowTitle("Delete Samples")
            msg_box.setText(f"Are you sure you want to delete {len(sample_names)} samples?")
            # Add list of samples in informative text
            sample_list = "\n".join(f"  - {name}" for name in sample_names[:10])
            if len(sample_names) > 10:
                sample_list += f"\n  ... and {len(sample_names) - 10} more"
            msg_box.setInformativeText(sample_list)

        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        confirm = msg_box.button(QMessageBox.StandardButton.Yes)
        confirm.setText("Delete")
        confirm.setProperty("variant", "danger")
        msg_box.button(QMessageBox.StandardButton.No).setText("Cancel")

        reply = msg_box.exec()

        if reply == QMessageBox.StandardButton.Yes:
            # Perform deletion
            deleted_count = soft_delete_samples(sample_names)
            if deleted_count > 0:
                self.samples_deleted.emit(sample_names)

    def _show_recovery_dialog(self):
        """Show the sample recovery dialog"""
        dialog = SampleRecoveryDialog(self)
        dialog.samples_restored.connect(self.samples_restored.emit)
        dialog.exec()
