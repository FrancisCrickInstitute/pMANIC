from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from manic.models.mm_file_check import MmFileStatus

_STATE_ORDER = {"unset": 0, "no_match": 1, "matched": 2}
_WARNING_CELL = QColor(255, 243, 205)
_UNSET_STATUS = "color: #dc3545;"
_SET_STATUS = "color: #212529;"


def _matched_cell_text(status: MmFileStatus) -> str:
    if status.state == "unset":
        return "No pattern"
    if status.state == "no_match":
        return "No files matched"
    preview = ", ".join(status.matched[:3])
    count = len(status.matched)
    noun = "file" if count == 1 else "files"
    return f"{count} {noun}: {preview}"


def _pattern_cell_text(status: MmFileStatus) -> str:
    if status.state == "unset":
        return "Not set"
    return status.pattern or "Not set"


def _summary_text(report: list[MmFileStatus]) -> str:
    total = len(report)
    with_pattern = sum(1 for row in report if row.pattern is not None)
    unmatched = sum(1 for row in report if row.state == "no_match")
    summary = f"{with_pattern} of {total} compounds have an MM pattern."
    if unmatched == 1:
        return f"{summary} 1 pattern matches no sample files."
    if unmatched:
        return f"{summary} {unmatched} patterns match no sample files."
    return summary


class PostLoadChecklistDialog(QDialog):
    open_user_guide_requested = Signal()

    def __init__(
        self,
        compound_names: list[str],
        current_internal_standard: str | None,
        mm_report: list[MmFileStatus],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("postLoadChecklistDialog")
        self.setWindowTitle("Check your data setup")
        self.setModal(True)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Check your data setup")
        title.setObjectName("checklistTitle")
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        explanation = QLabel(
            "Weak peaks are only flagged (shown in red) when an internal standard is set."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        is_heading = QLabel("Internal standard")
        is_font = is_heading.font()
        is_font.setBold(True)
        is_heading.setFont(is_font)
        layout.addWidget(is_heading)

        is_row = QHBoxLayout()
        is_row.setSpacing(12)
        self.internal_standard_combo = QComboBox()
        self.internal_standard_combo.setObjectName("internalStandardCombo")
        self.internal_standard_combo.addItem("No internal standard", None)
        for name in compound_names:
            self.internal_standard_combo.addItem(name, name)
        if current_internal_standard:
            index = self.internal_standard_combo.findText(current_internal_standard)
            if index >= 0:
                self.internal_standard_combo.setCurrentIndex(index)
        is_row.addWidget(self.internal_standard_combo, 1)

        self._is_status = QLabel()
        self._is_status.setObjectName("internalStandardStatus")
        is_row.addWidget(self._is_status)
        layout.addLayout(is_row)
        self.internal_standard_combo.currentIndexChanged.connect(
            self._update_internal_standard_status
        )
        self._update_internal_standard_status()

        mm_heading = QLabel("MM file selection")
        mm_font = mm_heading.font()
        mm_font.setBold(True)
        mm_heading.setFont(mm_font)
        layout.addWidget(mm_heading)

        self._mm_summary = QLabel(_summary_text(mm_report))
        self._mm_summary.setWordWrap(True)
        layout.addWidget(self._mm_summary)

        self.mm_file_table = QTableWidget(0, 3)
        self.mm_file_table.setObjectName("mmFileTable")
        self.mm_file_table.setHorizontalHeaderLabels(
            ["Compound", "MM pattern", "Matched files"]
        )
        self.mm_file_table.verticalHeader().setVisible(False)
        self.mm_file_table.horizontalHeader().setStretchLastSection(True)
        self.mm_file_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.mm_file_table.horizontalHeader().setHighlightSections(False)
        self.mm_file_table.setShowGrid(False)
        self.mm_file_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.mm_file_table.setFocusPolicy(Qt.NoFocus)
        self.mm_file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.mm_file_table.verticalHeader().setDefaultSectionSize(32)
        self.mm_file_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._fill_mm_table(mm_report)
        layout.addWidget(self.mm_file_table)

        hint = QLabel(
            "MM patterns are edited in the compound list spreadsheet "
            "(the mmfiles column) or the Add Compound dialog."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(hint)

        self.user_guide_link = QLabel('<a href="guide">Open the user guide</a>')
        self.user_guide_link.setObjectName("userGuideLink")
        self.user_guide_link.setTextFormat(Qt.RichText)
        self.user_guide_link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.user_guide_link.linkActivated.connect(
            lambda _href: self.open_user_guide_requested.emit()
        )
        layout.addWidget(self.user_guide_link)

        buttons = QDialogButtonBox()
        apply_button = buttons.addButton("Apply", QDialogButtonBox.AcceptRole)
        buttons.addButton("Skip", QDialogButtonBox.RejectRole)
        apply_button.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_internal_standard(self) -> str | None:
        value = self.internal_standard_combo.currentData()
        if value is None:
            return None
        return str(value)

    def _update_internal_standard_status(self) -> None:
        if self.internal_standard_combo.currentData() is None:
            self._is_status.setText("Not set")
            self._is_status.setStyleSheet(_UNSET_STATUS)
        else:
            self._is_status.setText("Set")
            self._is_status.setStyleSheet(_SET_STATUS)

    def _fill_mm_table(self, report: list[MmFileStatus]) -> None:
        rows = sorted(report, key=lambda status: _STATE_ORDER[status.state])
        table = self.mm_file_table
        table.setRowCount(len(rows))
        for row, status in enumerate(rows):
            values = (
                status.compound_name,
                _pattern_cell_text(status),
                _matched_cell_text(status),
            )
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemIsEnabled)
                if column == 2 and status.state in ("unset", "no_match"):
                    item.setBackground(_WARNING_CELL)
                table.setItem(row, column, item)
        self._fit_table_height()

    def _fit_table_height(self) -> None:
        table = self.mm_file_table
        header = max(table.horizontalHeader().sizeHint().height(), 24)
        row_h = table.verticalHeader().defaultSectionSize()
        frame = 2 * table.frameWidth()
        visible_rows = min(max(table.rowCount(), 1), 8)
        table.setFixedHeight(header + visible_rows * row_h + frame)
