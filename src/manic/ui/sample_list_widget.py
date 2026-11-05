from collections.abc import Iterable
from typing import List

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
)

from manic.models.database import get_deleted_samples, soft_delete_samples
from manic.ui.sample_recovery_dialog import SampleRecoveryDialog
from manic.ui.theme import set_style_property


class SampleListWidget(QListWidget):
    """Samples with a checkbox each: checked samples are the ones shown in the grid.

    Row selection is separate and only picks rows for the context menu."""

    samples_deleted = Signal(list)  # Emits list of deleted sample names
    samples_restored = Signal(list)  # Emits list of restored sample names
    shown_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sampleList")
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setMinimumHeight(72)
        self.setUniformItemSizes(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemChanged.connect(self.shown_changed)
        self._show_empty()

    def _show_empty(self):
        self.clear()
        item = QListWidgetItem("- No Samples Loaded -")
        self.addItem(item)
        self.setCurrentItem(item)

    def _real_items(self) -> list[QListWidgetItem]:
        return [
            item
            for item in (self.item(row) for row in range(self.count()))
            if item is not None and not item.text().startswith("- No")
        ]

    def update_samples(self, samples: List[str]):
        with QSignalBlocker(self):
            self.clear()
            if not samples:
                self._show_empty()
            for name in samples:
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self.addItem(item)
        self.shown_changed.emit()

    def shown_samples(self) -> List[str]:
        """Checked samples in list order."""
        return [
            item.text()
            for item in self._real_items()
            if item.checkState() == Qt.CheckState.Checked
        ]

    def _set_checked(self, items, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        with QSignalBlocker(self):
            for item in items:
                item.setCheckState(state)
        self.shown_changed.emit()

    def set_shown_samples(self, names: Iterable[str]) -> None:
        wanted = set(names)
        items = self._real_items()
        if not any(item.text() in wanted for item in items):
            return
        with QSignalBlocker(self):
            for item in items:
                item.setCheckState(
                    Qt.CheckState.Checked
                    if item.text() in wanted
                    else Qt.CheckState.Unchecked
                )
        self.shown_changed.emit()

    def show_all_samples(self) -> None:
        if self.real_count() == 0:
            return
        self._set_checked(self._real_items(), True)

    def keyPressEvent(self, event):
        # Space toggles every highlighted row together, following the current row.
        current = self.currentItem()
        rows = self._valid_selected_items()
        if (
            event.key() == Qt.Key.Key_Space
            and current is not None
            and current in rows
            and len(rows) > 1
        ):
            self._set_checked(rows, current.checkState() != Qt.CheckState.Checked)
            event.accept()
            return
        super().keyPressEvent(event)

    def _valid_selected_items(self) -> list[QListWidgetItem]:
        return [
            item for item in self.selectedItems() if not item.text().startswith("- No")
        ]

    def _get_valid_selected_samples(self) -> List[str]:
        """Highlighted sample names in list order, excluding placeholder items"""
        return [item.text() for item in self._real_items() if item.isSelected()]

    def real_count(self) -> int:
        """Get total number of real samples (excluding placeholder)"""
        return len(self._real_items())

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

        menu.addSeparator()
        rows = self._valid_selected_items()
        show_only = menu.addAction(
            "Show Only This Sample" if len(rows) == 1 else f"Show Only {len(rows)} Samples"
        )
        show_only.setEnabled(bool(rows))
        show_only.triggered.connect(
            lambda: self.set_shown_samples(item.text() for item in rows)
        )
        hide = menu.addAction(
            "Hide This Sample" if len(rows) == 1 else f"Hide {len(rows)} Samples"
        )
        hide.setEnabled(bool(rows))
        hide.triggered.connect(lambda: self._set_checked(rows, False))
        show_all = menu.addAction("Show All Samples")
        show_all.setEnabled(len(self.shown_samples()) < total_samples)
        show_all.triggered.connect(self.show_all_samples)

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
            msg_box.setText(f"Delete {sample_names[0]}?")
            msg_box.setInformativeText("Recover Deleted Samples brings it back.")
        else:
            msg_box.setWindowTitle("Delete Samples")
            msg_box.setText(f"Delete {len(sample_names)} samples?")
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
        set_style_property(confirm, "variant", "danger")
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
