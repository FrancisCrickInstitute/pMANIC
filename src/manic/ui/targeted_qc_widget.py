from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from manic.io.compound_reader import read_compound

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

_MAX_QUALIFIERS = 2


class TargetedQcWidget(QWidget):
    """Per-sample identity QC summary for unlabelled targeted compounds.

    Shows, for each selected sample: whether the quantifier was found, how far
    the apex sits from the expected retention time, and each qualifier ratio
    against its expected reference — so a failing check is visible at a glance.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.title = QLabel("Targeted identity QC")
        self.title.setStyleSheet("font-weight: 600; color: #15324b;")
        layout.addWidget(self.title)

        self.reference = QLabel("")
        self.reference.setWordWrap(True)
        self.reference.setStyleSheet("color: #5b6770; font-size: 11px;")
        layout.addWidget(self.reference)

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

        self.table = QTableWidget(0, 3)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setShowGrid(True)
        self.table.setStyleSheet(
            "QTableWidget { font-size: 11px; gridline-color: #e3e9ee; }"
            "QHeaderView::section { background-color: #eef3f7; color: #15324b;"
            " font-size: 11px; padding: 2px; border: none; }"
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.table.hide()
        layout.addWidget(self.table, stretch=1)

    def clear(self) -> None:
        self.title.setText("Targeted identity QC")
        self.reference.setText("")
        self.table.setRowCount(0)
        self.table.hide()
        self.placeholder.show()

    def update_results(
        self, compound_name: str, sample_names: list[str], provider
    ) -> None:
        if not compound_name or not sample_names:
            self.clear()
            return

        compound = None
        try:
            compound = read_compound(compound_name)
        except Exception:
            pass

        rows = []
        for sample_name in sample_names:
            try:
                rows.append(
                    (
                        sample_name,
                        provider.assess_unlabelled_identity(
                            sample_name, compound_name
                        ),
                        None,
                    )
                )
            except Exception as exc:
                rows.append((sample_name, None, str(exc)))

        channels = (
            compound.analysis_channels
            if compound is not None and compound.is_unlabelled_target
            else ()
        )
        qualifiers = channels[1:] if len(channels) > 1 else ()

        self.title.setText(f"Targeted identity QC — {compound_name}")
        self.reference.setText(self._reference_text(compound, qualifiers))

        n_qual = min(len(qualifiers), _MAX_QUALIFIERS) or 1
        headers = ["Sample", "Status", "ΔRT"] + [
            f"Q{q.ordinal}" for q in qualifiers[:_MAX_QUALIFIERS]
        ]
        if len(headers) < 4:
            headers.append("Q1")

        self.table.setColumnCount(3 + n_qual)
        self.table.setHorizontalHeaderLabels(headers[: 3 + n_qual])
        for index, qualifier in enumerate(qualifiers[:_MAX_QUALIFIERS]):
            item = self.table.horizontalHeaderItem(3 + index)
            if item is not None:
                item.setToolTip(
                    self._qualifier_tooltip(qualifier)
                )

        self.table.setRowCount(len(rows))
        for row_index, (sample_name, result, error) in enumerate(rows):
            self._fill_row(row_index, sample_name, result, error, n_qual)

        self.placeholder.hide()
        self.table.show()

    def _reference_text(self, compound, qualifiers) -> str:
        if compound is None:
            return ""
        parts = []
        if compound.rt_tolerance is not None:
            parts.append(
                f"RT {compound.retention_time:.3f} ±{compound.rt_tolerance:.3f} min"
            )
        else:
            parts.append(f"RT {compound.retention_time:.3f} min")
        for qualifier in qualifiers[:_MAX_QUALIFIERS]:
            if qualifier.expected_ratio is not None:
                tol = (
                    f" ±{qualifier.ratio_tolerance:.0%}"
                    if qualifier.ratio_tolerance is not None
                    else ""
                )
                parts.append(
                    f"Q{qualifier.ordinal} {qualifier.expected_ratio:.3f}{tol}"
                )
        return "Expected: " + " · ".join(parts) if parts else ""

    @staticmethod
    def _qualifier_tooltip(qualifier) -> str:
        text = (
            f"Qualifier {qualifier.ordinal} (m/z {qualifier.mz:g}) area "
            "÷ quantifier area"
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

    def _fill_row(self, row_index, sample_name, result, error, n_qual) -> None:
        name_item = QTableWidgetItem(sample_name)
        name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        name_item.setToolTip(sample_name)
        self.table.setItem(row_index, 0, name_item)

        if result is None:
            status_item = self._make_item("Unavailable")
            status_item.setBackground(QColor("#F5F5F5"))
            status_item.setForeground(QColor("#757575"))
            status_item.setToolTip(escape(error or "QC unavailable"))
            self.table.setItem(row_index, 1, status_item)
            for column in range(2, 3 + n_qual):
                self.table.setItem(row_index, column, self._make_item("—"))
            return

        label, bg, fg = _STATUS_STYLES.get(
            result.status.value, (result.status.value, "#F5F5F5", "#616161")
        )
        status_item = self._make_item(label)
        status_item.setBackground(QColor(bg))
        status_item.setForeground(QColor(fg))
        if result.reasons:
            status_item.setToolTip(escape("\n".join(result.reasons)))
        self.table.setItem(row_index, 1, status_item)

        if result.rt_error is not None:
            rt_item = self._make_item(f"{result.rt_error:+.3f}")
            if result.rt_passed is True:
                rt_item.setForeground(QColor(_PASS_FG))
            elif result.rt_passed is False:
                rt_item.setBackground(QColor(_FAIL_BG))
                rt_item.setForeground(QColor(_FAIL_FG))
        else:
            rt_item = self._make_item("—")
        self.table.setItem(row_index, 2, rt_item)

        for column in range(n_qual):
            ratio = (
                result.qualifier_ratios[column]
                if column < len(result.qualifier_ratios)
                else None
            )
            if ratio is None or ratio.observed_ratio is None:
                self.table.setItem(row_index, 3 + column, self._make_item("—"))
                continue
            ratio_item = self._make_item(f"{ratio.observed_ratio:.3f}")
            if ratio.passed is True:
                ratio_item.setBackground(QColor(_PASS_BG))
                ratio_item.setForeground(QColor(_PASS_FG))
            elif ratio.passed is False:
                ratio_item.setBackground(QColor(_FAIL_BG))
                ratio_item.setForeground(QColor(_FAIL_FG))
            self.table.setItem(row_index, 3 + column, ratio_item)
