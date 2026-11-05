from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from manic.ui.combo_box import ComboBox
from manic.ui.dialog_kit import (
    MARGIN,
    button_box,
    description_label,
    form_layout,
    form_row,
    hint_label,
    style_dialog,
    title_label,
    window_title,
)


class _PathEdit(QLineEdit):
    """Read-only path field; hovering shows the full path only when it does not fit."""

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.ToolTip:
            hidden = self.fontMetrics().horizontalAdvance(self.text()) > (
                self.contentsRect().width() - 8
            )
            if hidden:
                QToolTip.showText(event.globalPos(), self.text(), self)
            else:
                QToolTip.hideText()
            return True
        return super().event(event)


def _file_picker(on_browse) -> tuple[QWidget, QLineEdit]:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    edit = _PathEdit()
    edit.setReadOnly(True)
    edit.setPlaceholderText("No file selected")
    layout.addWidget(edit, stretch=1)
    button = QPushButton("Browse…")
    button.setAutoDefault(False)
    button.clicked.connect(on_browse)
    layout.addWidget(button)
    return row, edit


class UpdateOldDataDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(window_title("Process External Data"))
        style_dialog(self)
        self.setModal(True)
        self.setMinimumWidth(560)

        self.compounds_path = None
        self.raw_values_path = None
        self.internal_standard: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        layout.setSpacing(8)
        layout.addWidget(title_label("Process external data"))
        layout.addWidget(
            description_label(
                "Rebuild a MANIC export from a Raw Values workbook and its compound "
                "list when the original CDF files are not available."
            )
        )
        layout.addSpacing(12)

        form = form_layout()
        c_row, self.c_edit = _file_picker(self._browse_compounds)
        form_row(form, "Compounds file", c_row)
        r_row, self.r_edit = _file_picker(self._browse_raw)
        form_row(form, "Raw Values workbook", r_row)

        self.is_combo = ComboBox()
        self.is_combo.addItem("No internal standard", None)
        self.is_combo.currentIndexChanged.connect(self._on_is_changed)
        form_row(form, "Internal standard", self.is_combo)
        form_row(form, "", hint_label("Lists the compounds once you choose a compounds file."))
        layout.addLayout(form)

        layout.addSpacing(16)
        layout.addStretch()
        self.buttons, self._ok_button = button_box("Rebuild export…")
        self._ok_button.setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _browse_compounds(self):
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Compounds File",
            "",
            "Excel/CSV (*.xlsx *.xls *.csv);;All files (*.*)",
        )
        if path:
            self.compounds_path = path
            self.c_edit.setText(path)
            # Populate internal standard dropdown from compounds file
            try:
                from manic.io.legacy_rebuild import _read_compounds_as_dicts

                names = [c["compound_name"] for c in _read_compounds_as_dicts(path)]
            except Exception:
                # Keep dropdown minimal if parsing fails
                names = []
            self.is_combo.clear()
            self.is_combo.addItem("No internal standard", None)
            for name in names:
                self.is_combo.addItem(name, name)
            self._update_ok()

    def _browse_raw(self):
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, "Select Raw Values Workbook", "", "Excel (*.xlsx);;All files (*.*)"
        )
        if path:
            self.raw_values_path = path
            self.r_edit.setText(path)
            self._update_ok()

    def _update_ok(self):
        ok = bool(self.compounds_path) and bool(self.raw_values_path)
        self._ok_button.setEnabled(ok)

    def get_paths(self):
        return self.compounds_path, self.raw_values_path

    def _on_is_changed(self, idx: int):
        self.internal_standard = self.is_combo.currentData()

    def get_internal_standard(self) -> str | None:
        return self.internal_standard
