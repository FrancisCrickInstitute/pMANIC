from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMenu, QMessageBox

from manic.constants import FONT
from manic.models.database import get_deleted_samples, soft_delete_samples
from manic.ui.sample_recovery_dialog import SampleRecoveryDialog


class SampleListWidget(QListWidget):
    samples_deleted = Signal(list)  # Emits list of deleted sample names
    samples_restored = Signal(list)  # Emits list of restored sample names

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
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

    def _get_valid_selected_samples(self) -> List[str]:
        """Get selected sample names, excluding placeholder items"""
        selected = []
        for item in self.selectedItems():
            text = item.text()
            if not text.startswith("- No"):
                selected.append(text)
        return selected

    def _get_total_sample_count(self) -> int:
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

        # Get selected samples
        selected_samples = self._get_valid_selected_samples()
        total_samples = self._get_total_sample_count()

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
            # Perform deletion
            deleted_count = soft_delete_samples(sample_names)
            if deleted_count > 0:
                self.samples_deleted.emit(sample_names)

    def _show_recovery_dialog(self):
        """Show the sample recovery dialog"""
        dialog = SampleRecoveryDialog(self)
        dialog.samples_restored.connect(self.samples_restored.emit)
        dialog.exec()
