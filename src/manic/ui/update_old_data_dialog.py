from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QDialogButtonBox, QComboBox
)


class UpdateOldDataDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Old Data")
        self.setModal(True)

        self.compounds_path = None
        self.raw_values_path = None
        self.internal_standard: str | None = None

        layout = QVBoxLayout()

        # Compounds picker
        c_row = QHBoxLayout()
        c_row.addWidget(QLabel("Compounds File:"))
        self.c_edit = QLineEdit()
        self.c_edit.setReadOnly(True)
        c_row.addWidget(self.c_edit)
        c_btn = QPushButton("Browse…")
        c_btn.clicked.connect(self._browse_compounds)
        c_row.addWidget(c_btn)
        layout.addLayout(c_row)

        # Raw values picker
        r_row = QHBoxLayout()
        r_row.addWidget(QLabel("Raw Values Workbook:"))
        self.r_edit = QLineEdit()
        self.r_edit.setReadOnly(True)
        r_row.addWidget(self.r_edit)
        r_btn = QPushButton("Browse…")
        r_btn.clicked.connect(self._browse_raw)
        r_row.addWidget(r_btn)
        layout.addLayout(r_row)

        # Internal standard dropdown (optional)
        is_row = QHBoxLayout()
        is_row.addWidget(QLabel("Internal Standard (optional):"))
        self.is_combo = QComboBox()
        self.is_combo.addItem("(None)")
        self.is_combo.currentIndexChanged.connect(self._on_is_changed)
        is_row.addWidget(self.is_combo)
        layout.addLayout(is_row)

        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

    def _browse_compounds(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Select Compounds File", "", "Excel/CSV (*.xlsx *.xls *.csv);;All files (*.*)")
        if path:
            self.compounds_path = path
            self.c_edit.setText(path)
            # Populate internal standard dropdown from compounds file
            try:
                from manic.io.legacy_rebuild import _read_compounds_as_dicts
                compounds = _read_compounds_as_dicts(path)
                names = [c['compound_name'] for c in compounds]
                self.is_combo.clear()
                self.is_combo.addItem("(None)")
                for n in names:
                    self.is_combo.addItem(n)
            except Exception:
                # Keep dropdown minimal if parsing fails
                self.is_combo.clear()
                self.is_combo.addItem("(None)")
            self._update_ok()

    def _browse_raw(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Select Raw Values Workbook", "", "Excel (*.xlsx);;All files (*.*)")
        if path:
            self.raw_values_path = path
            self.r_edit.setText(path)
            self._update_ok()

    def _update_ok(self):
        ok = bool(self.compounds_path) and bool(self.raw_values_path)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(ok)

    def get_paths(self):
        return self.compounds_path, self.raw_values_path

    def _on_is_changed(self, idx: int):
        text = self.is_combo.currentText()
        self.internal_standard = None if text == "(None)" else text

    def get_internal_standard(self) -> str | None:
        return self.internal_standard
