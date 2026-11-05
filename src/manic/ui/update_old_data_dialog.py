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
from manic.ui.post_load_checklist_dialog import StandardPicker


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

        self.standard_picker = StandardPicker([], None, set())
        self.standard_picker.setEnabled(False)
        form_row(form, "Internal standard", self.standard_picker)
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
            try:
                from manic.io.legacy_rebuild import _read_compounds_as_dicts

                compounds = _read_compounds_as_dicts(path)
            except Exception:
                # The rebuild reports the unreadable file; the standard stays unset.
                compounds = []
            names = [c["compound_name"] for c in compounds]
            # The rebuild is labelled: calibrating needs both amounts, as in the sidebar.
            lacking = {
                c["compound_name"]
                for c in compounds
                if not all((c[f] or 0) > 0 for f in ("int_std_amount", "amount_in_std_mix"))
            }
            self.standard_picker.set_names(names, lacking)
            self.standard_picker.setEnabled(bool(names))
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

    def get_internal_standard(self) -> str | None:
        return self.standard_picker.standard()
