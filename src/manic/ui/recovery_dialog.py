
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox
)

from manic.constants import FONT
from manic.models.database import get_deleted_compounds, restore_compound, restore_all_compounds


class RecoveryDialog(QDialog):
    """Dialog for recovering deleted compounds"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recover Deleted Compounds")
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
        """)
        
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
        layout.addWidget(self.compound_list)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setFont(QFont(FONT, 9))
        self.status_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.status_label)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Restore selected button
        self.restore_selected_btn = QPushButton("Restore Selected")
        self.restore_selected_btn.setFont(QFont(FONT, 10))
        self.restore_selected_btn.clicked.connect(self._restore_selected)
        button_layout.addWidget(self.restore_selected_btn)
        
        # Restore all button
        self.restore_all_btn = QPushButton("Restore All")
        self.restore_all_btn.setFont(QFont(FONT, 10))
        self.restore_all_btn.clicked.connect(self._restore_all)
        button_layout.addWidget(self.restore_all_btn)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.setFont(QFont(FONT, 10))
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _create_styled_message_box(self, icon, title, text, buttons=None, default_button=None):
        """Create a properly styled message box with clean design, no borders or icons"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        # Remove icon to match the clean design of the rest of the app
        
        if buttons:
            msg_box.setStandardButtons(buttons)
        if default_button:
            msg_box.setDefaultButton(default_button)
            
        # Style message box with clean styling, no borders or images
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: white;
                color: black;
                border: none;
            }
            QLabel {
                color: black;
                background-color: transparent;
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
        """)
        
        return msg_box
    
    def _load_deleted_compounds(self):
        """Load list of deleted compounds"""
        self.compound_list.clear()
        deleted_compounds = get_deleted_compounds()
        
        if not deleted_compounds:
            self.status_label.setText("No deleted compounds found.")
            self.restore_selected_btn.setEnabled(False)
            self.restore_all_btn.setEnabled(False)
            
            # Add placeholder item
            item = QListWidgetItem("- No Deleted Compounds -")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.compound_list.addItem(item)
        else:
            self.status_label.setText(f"{len(deleted_compounds)} deleted compound(s) found.")
            self.restore_selected_btn.setEnabled(True)
            self.restore_all_btn.setEnabled(True)
            
            for compound_name in deleted_compounds:
                item = QListWidgetItem(compound_name)
                self.compound_list.addItem(item)
    
    def _restore_selected(self):
        """Restore selected compounds"""
        selected_items = self.compound_list.selectedItems()
        
        if not selected_items:
            msg_box = self._create_styled_message_box(
                QMessageBox.Icon.Information,
                "No Selection",
                "Please select one or more compounds to restore."
            )
            msg_box.exec()
            return
        
        # Confirm restoration
        compound_names = [item.text() for item in selected_items]
        if len(compound_names) == 1:
            message = f"Restore compound '{compound_names[0]}'?"
        else:
            message = f"Restore {len(compound_names)} selected compounds?"
        
        msg_box = self._create_styled_message_box(
            QMessageBox.Icon.Question,
            "Confirm Restore",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        reply = msg_box.exec()
        
        if reply == QMessageBox.StandardButton.Yes:
            restored_count = 0
            for compound_name in compound_names:
                if restore_compound(compound_name):
                    restored_count += 1
            
            if restored_count > 0:
                msg_box = self._create_styled_message_box(
                    QMessageBox.Icon.Information,
                    "Restore Complete",
                    f"Successfully restored {restored_count} compound(s)."
                )
                msg_box.exec()
                self._load_deleted_compounds()  # Refresh the list
                # Close the dialog after successful restore
                self.accept()
            else:
                msg_box = self._create_styled_message_box(
                    QMessageBox.Icon.Warning,
                    "Restore Failed",
                    "No compounds were restored. They may have already been restored."
                )
                msg_box.exec()
    
    def _restore_all(self):
        """Restore all deleted compounds"""
        deleted_count = len(get_deleted_compounds())
        
        if deleted_count == 0:
            msg_box = self._create_styled_message_box(
                QMessageBox.Icon.Information,
                "No Compounds",
                "There are no deleted compounds to restore."
            )
            msg_box.exec()
            return
        
        # Confirm restoration
        msg_box = self._create_styled_message_box(
            QMessageBox.Icon.Question,
            "Confirm Restore All",
            f"Restore all {deleted_count} deleted compounds?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        reply = msg_box.exec()
        
        if reply == QMessageBox.StandardButton.Yes:
            restored_count = restore_all_compounds()
            
            if restored_count > 0:
                msg_box = self._create_styled_message_box(
                    QMessageBox.Icon.Information,
                    "Restore Complete",
                    f"Successfully restored {restored_count} compound(s)."
                )
                msg_box.exec()
                self._load_deleted_compounds()  # Refresh the list
                # Close the dialog after successful restore
                self.accept()
            else:
                msg_box = self._create_styled_message_box(
                    QMessageBox.Icon.Warning,
                    "Restore Failed",
                    "No compounds were restored."
                )
                msg_box.exec()