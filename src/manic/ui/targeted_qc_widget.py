from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from manic.io.compound_reader import read_compound, read_compound_with_session

_STATUS_STYLES = {
    "supported": ("Supported", "#E6F4EA", "#166534"),
    "review_required": ("Review", "#FDE8D7", "#B45309"),
    "not_detected": ("Not detected", "#ECEFF1", "#546E7A"),
    "not_assessed": ("Not assessed", "#E8EEF9", "#3B5BA9"),
}
_PASS_BG = "#E6F4EA"
_PASS_FG = "#166534"
_FAIL_BG = "#FBDFDB"
_FAIL_FG = "#B3261E"

# Display order: failures and unknowns first, clean samples last.
_STATUS_SORT_RANK = {
    "review_required": 0,
    "not_detected": 1,
    "not_assessed": 2,
    "supported": 3,
}

_MAX_QUALIFIERS = 2

# Fixed pixel widths for the compact columns; the sample column takes the rest.
_STATUS_COL_WIDTH = 76
_OBSERVED_RT_COL_WIDTH = 48
_RT_COL_WIDTH = 44
_QUALIFIER_COL_WIDTH = 38


class TargetedQcWidget(QWidget):
    """Per-sample identity QC summary for unlabelled targeted compounds.

    Shows, for each selected sample: whether the quantifier was found, how far
    the apex sits from the expected retention time, and each qualifier ratio
    against its expected reference — so a failing check is visible at a glance.
    """

    sample_activated = Signal(str)  # emitted when a table row is clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.title = QLabel("Targeted identity QC")
        self.title.setStyleSheet("font-weight: 600; color: #15324b; font-size: 11px;")
        layout.addWidget(self.title)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color: #15324b; font-size: 11px;")
        self.summary.hide()
        layout.addWidget(self.summary)

        self.reference = QLabel("")
        self.reference.setWordWrap(True)
        self.reference.setStyleSheet("color: #5b6770; font-size: 11px;")
        layout.addWidget(self.reference)

        self.show_issues_only = QCheckBox("Show issues only")
        self.show_issues_only.setToolTip(
            "Hide samples whose configured identity checks are supported."
        )
        self.show_issues_only.toggled.connect(self._apply_issue_filter)
        layout.addWidget(self.show_issues_only)

        self.placeholder = QLabel(
            "Select an unlabelled compound and one or more samples to see "
            "retention-time and qualifier-ratio checks."
        )
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet(
            "background-color: #f5f8fa; color: #5b6770; "
            "border: 1px solid #d7e0e7; border-radius: 6px; padding: 8px;"
        )
        layout.addWidget(self.placeholder, stretch=1)

        self.table = QTableWidget(0, 4)
        self.observed_retention_times: dict[str, float] = {}
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setShowGrid(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setTextElideMode(Qt.ElideMiddle)
        self.table.setStyleSheet(
            "QTableWidget { font-size: 11px; gridline-color: #e3e9ee; }"
            "QHeaderView::section { background-color: #eef3f7; color: #15324b;"
            " font-size: 11px; padding: 1px; border: none; }"
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.hide()
        layout.addWidget(self.table, stretch=1)

        self.details = QLabel("")
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.PlainText)
        self.details.setStyleSheet(
            "background-color: #f5f8fa; color: #334155; "
            "border: 1px solid #d7e0e7; border-radius: 4px; padding: 5px; "
            "font-size: 11px;"
        )
        self.details.hide()
        layout.addWidget(self.details)

    def _on_cell_clicked(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is not None and item.text():
            detail = item.data(Qt.UserRole)
            if detail:
                self.details.setText(f"{item.text()}: {detail}")
                self.details.show()
            else:
                self.details.hide()
            self.sample_activated.emit(item.text())

    def _apply_issue_filter(self, _checked: bool | None = None) -> None:
        issues_only = self.show_issues_only.isChecked()
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 1)
            status = status_item.data(Qt.UserRole) if status_item is not None else None
            self.table.setRowHidden(row, bool(issues_only and status == "supported"))

    def clear(self) -> None:
        self.title.setText("Targeted identity QC")
        self.summary.setText("")
        self.summary.hide()
        self.reference.setText("")
        self.table.setRowCount(0)
        self.observed_retention_times.clear()
        self.table.hide()
        self.details.setText("")
        self.details.hide()
        self.placeholder.show()

    def update_results(
        self, compound_name: str, sample_names: list[str], provider
    ) -> dict[str, str]:
        """Refresh the table; return identity status per sample name."""
        if not compound_name or not sample_names:
            self.clear()
            return {}

        compound = None
        try:
            compound = read_compound(compound_name)
        except Exception:
            pass

        rows = []
        for sample_name in sample_names:
            try:
                result = provider.assess_unlabelled_identity(
                    sample_name, compound_name
                )
                rows.append((sample_name, result, None))
            except Exception as exc:
                rows.append((sample_name, None, str(exc)))

        statuses = {
            sample_name: result.status.value if result is not None else "unavailable"
            for sample_name, result, _error in rows
        }
        self.observed_retention_times = {
            sample_name: float(result.observed_rt)
            for sample_name, result, _error in rows
            if result is not None and result.observed_rt is not None
        }

        rows.sort(
            key=lambda row: (
                _STATUS_SORT_RANK.get(
                    row[1].status.value if row[1] is not None else "unavailable",
                    2,
                ),
                row[0],
            )
        )

        channels = (
            compound.analysis_channels
            if compound is not None and compound.is_unlabelled_target
            else ()
        )
        qualifiers = channels[1:] if len(channels) > 1 else ()

        self.title.setText(f"Targeted identity QC — {compound_name}")
        self.summary.setText(self._summary_text(statuses))
        self.summary.show()
        current_rts = []
        for sample_name in sample_names:
            try:
                current_rts.append(
                    float(
                        read_compound_with_session(
                            compound_name, sample_name
                        ).retention_time
                    )
                )
            except Exception:
                continue
        current_rt = current_rts[0] if current_rts else None
        if current_rt is not None and any(
            abs(rt - current_rt) > 1e-9 for rt in current_rts
        ):
            current_rt = None
        self.reference.setText(
            self._reference_text(compound, qualifiers, current_rt=current_rt)
        )

        n_qual = min(len(qualifiers), _MAX_QUALIFIERS) or 1
        headers = ["Sample", "Status", "Obs RT", "ΔRT"] + [
            f"V{q.ordinal}" for q in qualifiers[:_MAX_QUALIFIERS]
        ]
        if len(headers) < 5:
            headers.append("V1")

        self.table.setColumnCount(4 + n_qual)
        self.table.setHorizontalHeaderLabels(headers[: 4 + n_qual])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        fixed_widths = (
            _STATUS_COL_WIDTH,
            _OBSERVED_RT_COL_WIDTH,
            _RT_COL_WIDTH,
        ) + (_QUALIFIER_COL_WIDTH,) * n_qual
        for column, width in enumerate(fixed_widths, start=1):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
            self.table.setColumnWidth(column, width)
        for index, qualifier in enumerate(qualifiers[:_MAX_QUALIFIERS]):
            item = self.table.horizontalHeaderItem(4 + index)
            if item is not None:
                item.setToolTip(self._qualifier_tooltip(qualifier))

        self.table.setRowCount(len(rows))
        for row_index, (sample_name, result, error) in enumerate(rows):
            self._fill_row(row_index, sample_name, result, error, n_qual)
        self._apply_issue_filter()

        self.placeholder.hide()
        self.table.show()
        return statuses

    @staticmethod
    def _summary_text(statuses: dict[str, str]) -> str:
        total = len(statuses)
        supported = sum(1 for s in statuses.values() if s == "supported")
        review = sum(1 for s in statuses.values() if s == "review_required")
        undetected = sum(1 for s in statuses.values() if s == "not_detected")
        unavailable = sum(1 for s in statuses.values() if s == "unavailable")
        parts = [f"{supported} of {total} supported"]
        if review:
            parts.append(f"{review} need{'s' if review == 1 else ''} review")
        if undetected:
            parts.append(f"{undetected} not detected")
        if unavailable:
            parts.append(f"{unavailable} unavailable")
        return " · ".join(parts)

    def _reference_text(self, compound, qualifiers, current_rt=None) -> str:
        if compound is None:
            return ""
        if current_rt is None:
            rt = "tR (per sample)"
        else:
            rt = f"tR {current_rt:.3f}"
        if compound.rt_tolerance is not None:
            rt += f" ±{compound.rt_tolerance:.3f}"
        parts = [f"{rt} min"]
        for qualifier in qualifiers[:_MAX_QUALIFIERS]:
            if qualifier.expected_ratio is None:
                continue
            tol = (
                f" ±{qualifier.ratio_tolerance:.0%}"
                if qualifier.ratio_tolerance is not None
                else ""
            )
            parts.append(f"V{qualifier.ordinal} {qualifier.expected_ratio:.3f}{tol}")
        return "Expected: " + " · ".join(parts)

    @staticmethod
    def _qualifier_tooltip(qualifier) -> str:
        text = (
            f"V ion {qualifier.ordinal} (m/z {qualifier.mz:g}) area "
            "÷ Q ion area"
        )
        if qualifier.expected_ratio is not None:
            text += f"; expected {qualifier.expected_ratio:.3f}"
            if qualifier.ratio_tolerance is not None:
                text += f" ±{qualifier.ratio_tolerance:.0%}"
        return text

    def _make_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        return item

    @staticmethod
    def _style_outcome(item: QTableWidgetItem, passed: bool | None) -> None:
        """Colour a cell by check outcome."""
        if passed is True:
            item.setBackground(QColor(_PASS_BG))
            item.setForeground(QColor(_PASS_FG))
        elif passed is False:
            item.setBackground(QColor(_FAIL_BG))
            item.setForeground(QColor(_FAIL_FG))

    def _fill_row(self, row_index, sample_name, result, error, n_qual) -> None:
        name_item = QTableWidgetItem(sample_name)
        name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        name_item.setToolTip(sample_name)
        self.table.setItem(row_index, 0, name_item)

        if result is None:
            name_item.setData(Qt.UserRole, error or "QC unavailable")
            status_item = self._make_item("Unavailable")
            status_item.setData(Qt.UserRole, "unavailable")
            status_item.setBackground(QColor("#F5F5F5"))
            status_item.setForeground(QColor("#757575"))
            status_item.setToolTip(escape(error or "QC unavailable"))
            self.table.setItem(row_index, 1, status_item)
            for column in range(2, 4 + n_qual):
                self.table.setItem(row_index, column, self._make_item("—"))
            return

        label, bg, fg = _STATUS_STYLES.get(
            result.status.value, (result.status.value, "#F5F5F5", "#616161")
        )
        if result.reasons:
            name_item.setData(Qt.UserRole, "\n".join(result.reasons))
        else:
            name_item.setData(Qt.UserRole, "All configured identity checks passed")
        status_item = self._make_item(label)
        status_item.setData(Qt.UserRole, result.status.value)
        status_item.setBackground(QColor(bg))
        status_item.setForeground(QColor(fg))
        if result.reasons:
            status_item.setToolTip(escape("\n".join(result.reasons)))
        self.table.setItem(row_index, 1, status_item)

        if result.observed_rt is not None:
            observed_item = self._make_item(f"{result.observed_rt:.2f}")
            observed_item.setToolTip(f"Observed Q-ion apex: {result.observed_rt:.4f} min")
        else:
            observed_item = self._make_item("—")
        self.table.setItem(row_index, 2, observed_item)

        if result.rt_error is not None:
            rt_item = self._make_item(f"{result.rt_error:+.2f}")
            rt_item.setToolTip(f"ΔRT {result.rt_error:+.4f} min")
            self._style_outcome(rt_item, result.rt_passed)
        else:
            rt_item = self._make_item("—")
        self.table.setItem(row_index, 3, rt_item)

        for column in range(n_qual):
            ratio = (
                result.qualifier_ratios[column]
                if column < len(result.qualifier_ratios)
                else None
            )
            if ratio is None or ratio.observed_ratio is None:
                self.table.setItem(row_index, 4 + column, self._make_item("—"))
                continue
            ratio_item = self._make_item(f"{ratio.observed_ratio:.2f}")
            tooltip = f"V/Q ratio {ratio.observed_ratio:.4f}"
            if ratio.channel.expected_ratio is not None:
                tooltip += f" (expected {ratio.channel.expected_ratio:.3f}"
                if ratio.channel.ratio_tolerance is not None:
                    tooltip += f" ±{ratio.channel.ratio_tolerance:.0%}"
                tooltip += ")"
            ratio_item.setToolTip(tooltip)
            self._style_outcome(ratio_item, ratio.passed)
            self.table.setItem(row_index, 4 + column, ratio_item)
