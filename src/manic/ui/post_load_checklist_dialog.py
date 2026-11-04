from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
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
    resize_to_screen,
    section_label,
    set_variant,
    status_icon,
    style_dialog,
    title_label,
    window_title,
)

_STATE_ORDER = {"unset": 0, "no_match": 1, "matched": 2}

# Load Compounds stays disabled while a list is loaded, so a corrected file needs
# Clear Session first; sessions store mm_files, so importing an old one undoes it.
_CHANGE_PATTERN_STEPS = (
    "For a compound already in the list:\n"
    "1. Edit its mmfiles cell in the compound list and save the file.\n"
    "2. Choose File → Clear Session. This removes the loaded compounds (including "
    "any added with Add Compound), the raw data, the internal standard, "
    "integration changes, peak reviews and curve-fit choices.\n"
    "3. Choose File → Load Compounds/Parameter List with the saved file, then "
    "File → Load Raw Data (CDF) with the same folder. File → Open Recent lists both.\n"
    "Change patterns before you review: importing a session exported earlier "
    "brings its old patterns back.\n\n"
    "For a compound that is not in the list yet, File → Add Compound... sets its "
    "MM pattern without reloading."
)


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
    """Opens showing up to eight rows; never fewer than four, so a short screen scrolls the dialog."""

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
        *,
        compound_list_path: str | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("postLoadChecklistDialog")
        self.setWindowTitle(window_title("Check Data Setup"))
        style_dialog(self)
        self.setModal(True)
        self.setMinimumWidth(680)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        outer.setSpacing(16)
        self.body = QWidget()
        self.body.setObjectName("checklistBody")
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(0, 0, 8, 0)
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
                "Weak peaks get an amber Below threshold badge only when an "
                "internal standard is set."
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
                "hover a row to see the full pattern and every matched file."
            )
        )

        layout.addLayout(self._source_file_row(compound_list_path))
        self.change_pattern_toggle = QPushButton()
        self.change_pattern_toggle.setObjectName("changePatternToggle")
        self.change_pattern_toggle.setCheckable(True)
        set_variant(self.change_pattern_toggle, "link")
        self.change_pattern_toggle.setCursor(Qt.PointingHandCursor)
        self.change_pattern_toggle.setAutoDefault(False)
        self.change_pattern_toggle.toggled.connect(self._show_change_pattern_steps)
        toggle_row = QHBoxLayout()
        toggle_row.addWidget(self.change_pattern_toggle)
        toggle_row.addStretch(1)
        layout.addLayout(toggle_row)
        self.change_pattern_steps = hint_label(_CHANGE_PATTERN_STEPS)
        self.change_pattern_steps.setObjectName("changePatternSteps")
        self.change_pattern_steps.setContentsMargins(16, 0, 0, 0)
        layout.addWidget(self.change_pattern_steps)
        self._show_change_pattern_steps(False)

        self.user_guide_link = QLabel('<a href="guide">Open the user guide</a>')
        self.user_guide_link.setObjectName("userGuideLink")
        self.user_guide_link.setProperty("role", "hint")
        self.user_guide_link.setTextFormat(Qt.RichText)
        self.user_guide_link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.user_guide_link.linkActivated.connect(
            lambda _href: self.open_user_guide_requested.emit()
        )
        layout.addWidget(self.user_guide_link)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("checklistScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.body)
        self.scroll.viewport().setAutoFillBackground(False)
        self.body.setAutoFillBackground(False)
        outer.addWidget(self.scroll, stretch=1)

        buttons, _apply = button_box("Apply", "Continue without changes")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        """As tall as the body, or as the screen allows; the body scrolls above the buttons."""
        width = max(self.width(), self.minimumWidth())
        chrome = self.sizeHint().height() - self.scroll.sizeHint().height()
        body = self.body.layout().totalHeightForWidth(width - 2 * MARGIN)
        resize_to_screen(self, width, chrome + body)

    def _show_change_pattern_steps(self, shown: bool) -> None:
        arrow = "▾" if shown else "▸"
        self.change_pattern_toggle.setText(f"{arrow} How do I change a pattern?")
        self.change_pattern_steps.setVisible(shown)
        if shown:
            self._fit_to_screen()
            # After the body has laid out the steps, or it scrolls to where they were.
            QTimer.singleShot(
                0, lambda: self.scroll.ensureWidgetVisible(self.change_pattern_steps, 0, 0)
            )

    def _source_file_row(self, path: str | None) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        self.compound_list_label = description_label(
            f"Compound list: {Path(path).name}" if path else "Compound list: the file you loaded"
        )
        self.compound_list_label.setObjectName("compoundListFile")
        self.compound_list_label.setWordWrap(False)
        row.addWidget(self.compound_list_label, 1)
        if path:
            self.compound_list_label.setToolTip(str(Path(path)))
            for name, text, target in (
                ("openCompoundListButton", "Open File", Path(path)),
                ("showCompoundListFolderButton", "Show in Folder", Path(path).parent),
            ):
                button = QPushButton(text)
                button.setObjectName(name)
                set_variant(button, "link")
                button.setCursor(Qt.PointingHandCursor)
                button.setAutoDefault(False)
                button.clicked.connect(
                    lambda _checked=False, t=target: QDesktopServices.openUrl(
                        QUrl.fromLocalFile(str(t))
                    )
                )
                row.addWidget(button)
        return row

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
        table.setMinimumHeight(header + min(rows, 4) * row_h + frame)
        table.preferred_height = header + min(rows, 8) * row_h + frame
