from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
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
from manic.ui import theme
from manic.ui.combo_box import ComboBox
from manic.ui.dialog_kit import (
    MARGIN,
    SECTION_SPACING,
    button_box,
    description_label,
    hint_label,
    section_label,
    status_icon,
    style_dialog,
    title_label,
    window_title,
)

_STATE_ORDER = {"unset": 0, "no_match": 1, "matched": 2}


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


class _MmFileTable(QTableWidget):
    """Opens showing up to eight rows; shrinks to three when the screen is short."""

    preferred_height = 0

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), self.preferred_height)


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
        self.setWindowTitle(window_title("Check Data Setup"))
        style_dialog(self)
        self.setModal(True)
        self.setMinimumWidth(680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        layout.setSpacing(8)

        title = title_label("Check your data setup")
        title.setObjectName("checklistTitle")
        layout.addWidget(title)
        layout.addWidget(
            description_label(
                "Confirm the internal standard and which samples count as standard "
                "mixtures before you start reviewing."
            )
        )

        layout.addSpacing(SECTION_SPACING - 8)
        layout.addWidget(section_label("Internal standard"))
        is_row = QHBoxLayout()
        is_row.setSpacing(12)
        self.internal_standard_combo = ComboBox()
        self.internal_standard_combo.setObjectName("internalStandardCombo")
        self.internal_standard_combo.addItem("No internal standard", None)
        for name in compound_names:
            self.internal_standard_combo.addItem(name, name)
        if current_internal_standard:
            index = self.internal_standard_combo.findText(current_internal_standard)
            if index >= 0:
                self.internal_standard_combo.setCurrentIndex(index)
        is_row.addWidget(self.internal_standard_combo, 1)

        self._is_icon = QLabel()
        is_row.addWidget(self._is_icon)
        self._is_status = QLabel()
        self._is_status.setObjectName("internalStandardStatus")
        self._is_status.setMinimumWidth(56)
        is_row.addWidget(self._is_status)
        layout.addLayout(is_row)
        layout.addWidget(
            hint_label(
                "Weak peaks are only flagged (shown in red) when an internal "
                "standard is set."
            )
        )
        self.internal_standard_combo.currentIndexChanged.connect(
            self._update_internal_standard_status
        )
        self._update_internal_standard_status()

        layout.addSpacing(SECTION_SPACING - 8)
        layout.addWidget(section_label("Standard mixture (MM) files"))
        self._mm_summary = description_label(_summary_text(mm_report))
        layout.addWidget(self._mm_summary)

        self.mm_file_table = _MmFileTable(0, 3)
        self.mm_file_table.setObjectName("mmFileTable")
        self.mm_file_table.setHorizontalHeaderLabels(
            ["Compound", "MM pattern", "Matched files"]
        )
        self.mm_file_table.verticalHeader().setVisible(False)
        header = self.mm_file_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.mm_file_table.setTextElideMode(Qt.ElideMiddle)
        self.mm_file_table.setWordWrap(False)
        self.mm_file_table.setShowGrid(False)
        self.mm_file_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.mm_file_table.setFocusPolicy(Qt.NoFocus)
        self.mm_file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.mm_file_table.verticalHeader().setDefaultSectionSize(30)
        self.mm_file_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._fill_mm_table(mm_report)
        layout.addWidget(self.mm_file_table, stretch=1)

        layout.addWidget(
            hint_label(
                "Each pattern picks the standard mixture samples for that compound; "
                "hover a row to see the full pattern and every matched file. "
                "Patterns are edited in the compound list spreadsheet (the mmfiles "
                "column) or the Add Compound dialog."
            )
        )

        self.user_guide_link = QLabel('<a href="guide">Open the user guide</a>')
        self.user_guide_link.setObjectName("userGuideLink")
        self.user_guide_link.setProperty("role", "hint")
        self.user_guide_link.setTextFormat(Qt.RichText)
        self.user_guide_link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.user_guide_link.linkActivated.connect(
            lambda _href: self.open_user_guide_requested.emit()
        )
        layout.addWidget(self.user_guide_link)

        layout.addSpacing(8)
        buttons, _apply = button_box("Apply", "Continue without changes")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_internal_standard(self) -> str | None:
        value = self.internal_standard_combo.currentData()
        if value is None:
            return None
        return str(value)

    def _update_internal_standard_status(self) -> None:
        chosen = self.internal_standard_combo.currentData() is not None
        self._is_status.setText("Set" if chosen else "Optional")
        self._is_status.setProperty("role", None if chosen else "hint")
        self._is_status.style().unpolish(self._is_status)
        self._is_status.style().polish(self._is_status)
        self._is_icon.setPixmap(status_icon(True).pixmap(14, 14) if chosen else QPixmap())
        self._is_icon.setVisible(chosen)

    def _fill_mm_table(self, report: list[MmFileStatus]) -> None:
        rows = sorted(report, key=lambda status: _STATE_ORDER[status.state])
        table = self.mm_file_table
        table.setRowCount(len(rows))
        warning_fill = theme.color("warning_soft")
        for row, status in enumerate(rows):
            matched = status.state == "matched"
            tooltip = (
                f"Pattern: {status.pattern or 'not set'}\n"
                + (
                    "Matched files:\n" + "\n".join(status.matched)
                    if matched
                    else _matched_cell_text(status)
                )
            )
            values = (
                status.compound_name,
                _pattern_cell_text(status),
                _matched_cell_text(status),
            )
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemIsEnabled)
                item.setToolTip(tooltip)
                if column == 2:
                    item.setIcon(status_icon(matched))
                    if not matched:
                        item.setBackground(warning_fill)
                table.setItem(row, column, item)
        table.resizeColumnToContents(0)
        table.setColumnWidth(0, min(table.columnWidth(0) + 16, 200))
        table.setColumnWidth(1, 200)
        self._fit_table_height()

    def _fit_table_height(self) -> None:
        table = self.mm_file_table
        header = max(table.horizontalHeader().sizeHint().height(), 24)
        row_h = table.verticalHeader().defaultSectionSize()
        frame = 2 * table.frameWidth()
        rows = max(table.rowCount(), 1)
        table.setMinimumHeight(header + min(rows, 3) * row_h + frame)
        table.preferred_height = header + min(rows, 8) * row_h + frame
