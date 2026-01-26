from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from manic.constants import FONT
from manic.models.database import get_deleted_samples, restore_samples


class SampleRecoveryDialog(QDialog):
    """Dialog for recovering deleted samples with multi-select support"""

    samples_restored = Signal(list)  # Emits list of restored sample names

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recover Deleted Samples")
        self.setModal(True)
        self.resize(400, 500)

        # Set dialog styling with clean design, no borders
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                color: black;
            }
            QLabel {
                color: black;
                background-color: transparent;
            }
            QListWidget {
                background-color: white;
                color: black;
                border: 1px solid #d0d0d0;
            }
            QPushButton {
                background-color: #f0f0f0;
                color: black;
                border: none;
                padding: 8px 24px;
                border-radius: 4px;
                min-width: 120px;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #999999;
            }
        """)

        self._setup_ui()
        self._load_deleted_samples()

    def _setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)

        # Title label
        title_label = QLabel("Select samples to recover:")
        title_label.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # List widget for deleted samples
        self.sample_list = QListWidget()
        self.sample_list.setFont(QFont(FONT, 10))
        self.sample_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.sample_list.itemSelectionChanged.connect(self._update_button_state)
        layout.addWidget(self.sample_list)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setFont(QFont(FONT, 9))
        self.status_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.status_label)

        # Button layout
        button_layout = QHBoxLayout()

        # Restore selected button
        self.restore_btn = QPushButton("Restore Selected")
        self.restore_btn.setFont(QFont(FONT, 10))
        self.restore_btn.clicked.connect(self._on_restore_clicked)
        self.restore_btn.setEnabled(False)
        button_layout.addWidget(self.restore_btn)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFont(QFont(FONT, 10))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _load_deleted_samples(self):
        """Load list of deleted samples"""
        self.sample_list.clear()
        deleted_samples = get_deleted_samples()

        if not deleted_samples:
            self.status_label.setText("No deleted samples found.")
            self.restore_btn.setEnabled(False)

            # Add placeholder item
            item = QListWidgetItem("- No Deleted Samples -")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.sample_list.addItem(item)
        else:
            self.status_label.setText(f"{len(deleted_samples)} deleted sample(s) found.")

            for sample_name in deleted_samples:
                item = QListWidgetItem(sample_name)
                self.sample_list.addItem(item)

    def _update_button_state(self):
        """Enable/disable restore button based on selection"""
        selected_items = self.sample_list.selectedItems()
        self.restore_btn.setEnabled(len(selected_items) > 0)

    def _on_restore_clicked(self):
        """Restore selected samples immediately (no confirmation needed)"""
        selected_items = self.sample_list.selectedItems()

        if not selected_items:
            return

        # Get sample names from selection
        sample_names = [item.text() for item in selected_items]

        # Restore samples
        restored_count = restore_samples(sample_names)

        if restored_count > 0:
            # Emit signal with list of restored sample names
            # Note: We emit the full list since all selected samples were in deleted state
            # and restore_samples() attempts to restore all of them
            self.samples_restored.emit(sample_names)
            # Close dialog
            self.accept()
