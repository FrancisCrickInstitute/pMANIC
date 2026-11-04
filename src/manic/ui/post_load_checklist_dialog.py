from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
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
# Clear Session first; the guide carries the rest (what it removes, old sessions).
_CHANGE_PATTERN_STEPS = (
    "1. Edit the mmfiles cell in the compound list and save the file.\n"
    "2. File → Clear Session. This discards the session's review work.\n"
    "3. Load the compound list and the raw data again."
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

        layout.addSpacing(SECTION_SPACING - 8)
        layout.addWidget(section_label("Internal standard"))
        self._initial_internal_standard = current_internal_standard
        self.internal_standard_combo = ComboBox()
        self.internal_standard_combo.setObjectName("internalStandardCombo")
        self.internal_standard_combo.addItem("No internal standard", None)
        for name in compound_names:
            self.internal_standard_combo.addItem(name, name)
        if current_internal_standard:
            index = self.internal_standard_combo.findText(current_internal_standard)
            if index >= 0:
                self.internal_standard_combo.setCurrentIndex(index)
        layout.addWidget(self.internal_standard_combo)
        layout.addWidget(
            hint_label(
                "Weak peaks get an amber Below threshold badge only when an "
                "internal standard is set."
            )
        )

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
        self.change_pattern_steps = QWidget()
        self.change_pattern_steps.setObjectName("changePatternSteps")
        steps = QVBoxLayout(self.change_pattern_steps)
        steps.setContentsMargins(16, 0, 0, 0)
        steps.setSpacing(4)
        self.change_pattern_text = hint_label(_CHANGE_PATTERN_STEPS)
        steps.addWidget(self.change_pattern_text)
        self.user_guide_link = QLabel(
            '<a href="guide" style="text-decoration: none;">Details in the user guide</a>'
        )
        self.user_guide_link.setObjectName("userGuideLink")
        self.user_guide_link.setProperty("role", "hint")
        self.user_guide_link.setTextFormat(Qt.RichText)
        self.user_guide_link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.user_guide_link.linkActivated.connect(
            lambda _href: self.open_user_guide_requested.emit()
        )
        steps.addWidget(self.user_guide_link)
        layout.addWidget(self.change_pattern_steps)
        self._show_change_pattern_steps(False)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("checklistScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.body)
        self.scroll.viewport().setAutoFillBackground(False)
        self.body.setAutoFillBackground(False)
        outer.addWidget(self.scroll, stretch=1)

        # Unchanged, the dialog has one way out; Apply and discard appear once a
        # different standard is staged.
        self.buttons = QDialogButtonBox()
        self.primary_button = self.buttons.addButton("Continue", QDialogButtonBox.AcceptRole)
        self.primary_button.setDefault(True)
        set_variant(self.primary_button, "primary")
        self.discard_button = self.buttons.addButton(
            "Continue without changes", QDialogButtonBox.RejectRole
        )
        self.discard_button.setAutoDefault(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)
        self.internal_standard_combo.currentIndexChanged.connect(self._sync_buttons)
        self._sync_buttons()
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

    def _sync_buttons(self) -> None:
        changed = self.selected_internal_standard() != self._initial_internal_standard
        self.primary_button.setText("Apply" if changed else "Continue")
        self.discard_button.setVisible(changed)

    def _fill_mm_table(self, report: list[MmFileStatus]) -> None:
        rows = sorted(report, key=lambda status: _STATE_ORDER[status.state])
        table = self.mm_file_table
        table.setRowCount(len(rows))
        warning_fill = theme.color("warning_soft")
        pattern_width = 200
        metrics = table.fontMetrics()
        for row, status in enumerate(rows):
            matched = status.state == "matched"
            pattern = _pattern_cell_text(status)
            # Tooltips only where a cell hides something: an elided pattern or
            # files beyond the three listed.
            tooltips = (
                "",
                pattern if metrics.horizontalAdvance(pattern) > pattern_width - 16 else "",
                "\n".join(status.matched) if len(status.matched) > 3 else "",
            )
            values = (status.compound_name, pattern, _matched_cell_text(status))
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemIsEnabled)
                if tooltips[column]:
                    item.setToolTip(tooltips[column])
                if column == 2:
                    item.setIcon(status_icon(matched))
                    if not matched:
                        item.setBackground(warning_fill)
                table.setItem(row, column, item)
        table.resizeColumnToContents(0)
        table.setColumnWidth(0, min(table.columnWidth(0) + 16, 200))
        table.setColumnWidth(1, pattern_width)
        self._fit_table_height()

    def _fit_table_height(self) -> None:
        table = self.mm_file_table
        header = max(table.horizontalHeader().sizeHint().height(), 24)
        row_h = table.verticalHeader().defaultSectionSize()
        frame = 2 * table.frameWidth()
        rows = max(table.rowCount(), 1)
        table.setMinimumHeight(header + min(rows, 4) * row_h + frame)
        table.preferred_height = header + min(rows, 8) * row_h + frame
