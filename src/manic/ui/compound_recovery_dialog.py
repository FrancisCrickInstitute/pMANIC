from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from manic.constants import FONT
from manic.models.database import get_deleted_compounds, restore_compounds
from manic.utils.paths import resource_path
from manic.utils.utils import load_stylesheet


class CompoundRecoveryDialog(QDialog):
    """Dialog for recovering deleted compounds with multi-select support"""

    compounds_restored = Signal(list)  # Emits list of restored compound names

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recover Deleted Compounds")
        self.setModal(True)
        self.resize(400, 500)

        # Load and apply the stylesheet from resources
        stylesheet = load_stylesheet(resource_path("resources", "style.qss"))
        self.setStyleSheet(stylesheet)

        self._setup_ui()
        self._load_deleted_compounds()

    def _setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)

        # Title label
        title_label = QLabel("Select compounds to recover:")
        title_label.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # List widget for deleted compounds
        self.compound_list = QListWidget()
        self.compound_list.setFont(QFont(FONT, 10))
        self.compound_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.compound_list.itemSelectionChanged.connect(self._update_button_state)
        layout.addWidget(self.compound_list)

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

    def _load_deleted_compounds(self):
        """Load list of deleted compounds"""
        self.compound_list.clear()
        deleted_compounds = get_deleted_compounds()

        if not deleted_compounds:
            self.status_label.setText("No deleted compounds found.")
            self.restore_btn.setEnabled(False)

            # Add placeholder item
            item = QListWidgetItem("- No Deleted Compounds -")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.compound_list.addItem(item)
        else:
            self.status_label.setText(f"{len(deleted_compounds)} deleted compound(s) found.")

            for compound_name in deleted_compounds:
                item = QListWidgetItem(compound_name)
                self.compound_list.addItem(item)

    def _update_button_state(self):
        """Enable/disable restore button based on selection"""
        selected_items = self.compound_list.selectedItems()
        self.restore_btn.setEnabled(len(selected_items) > 0)

    def _on_restore_clicked(self):
        """Restore selected compounds immediately (no confirmation needed)"""
        selected_items = self.compound_list.selectedItems()

        if not selected_items:
            return

        # Get compound names from selection
        compound_names = [item.text() for item in selected_items]

        # Restore compounds
        restored_count = restore_compounds(compound_names)

        if restored_count > 0:
            # Emit the originally selected names. The UI will refresh from the
            # database, so the exact list vs actual count difference is acceptable.
            # Note: restored_count may be less than len(compound_names) if some
            # were already restored elsewhere.
            self.compounds_restored.emit(compound_names)
            self.accept()
        else:
            QMessageBox.warning(self, "Restore Failed", "No compounds were restored.")
