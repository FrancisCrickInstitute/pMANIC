from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCharts import QBarSet, QChart, QChartView
from PySide6.QtCore import QMargins, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter
from PySide6.QtWidgets import QSizePolicy, QToolTip, QVBoxLayout, QWidget

from manic.ui.chart_popup_dialog import ChartPopupDialog
from manic.ui.identity_chart import (
    RatioVerdict,
    add_identity_series,
    show_identity_tooltip,
)


def ratio_verdict(result) -> RatioVerdict:
    if result is None:
        return RatioVerdict.NOT_GIVEN
    flags = [ratio.passed for ratio in result.qualifier_ratios]
    if not flags:
        return RatioVerdict.NOT_GIVEN
    n_pass = sum(value is True for value in flags)
    n_fail = sum(value is False for value in flags)
    if n_pass == len(flags):
        return RatioVerdict.VALIDATED
    if n_pass > 0:
        return RatioVerdict.PARTIAL
    if n_fail > 0:
        return RatioVerdict.MISMATCH
    return RatioVerdict.NOT_GIVEN


def _format_ratio(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"


def _format_tolerance(tolerance: float | None, expected: float | None) -> str:
    if tolerance is None:
        return "—"
    if expected in (None, 0):
        return f"±{tolerance:g}"
    return f"±{tolerance:.0%}"


def _row_note(result, error: str | None = None) -> str:
    if result is None:
        return error or "Could not compute identity"
    if not result.qualifier_ratios:
        return "No expected ratio"
    lines = []
    for ratio in result.qualifier_ratios:
        channel = ratio.channel
        expected = channel.expected_ratio
        label = f"V{channel.ordinal}" if channel.ordinal else "V"
        lines.append(
            f"{label}  expected {_format_ratio(expected)}  "
            f"{_format_tolerance(channel.ratio_tolerance, expected)}  "
            f"observed {_format_ratio(ratio.observed_ratio)}"
        )
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class _IdentityRow:
    sample_name: str
    verdict: RatioVerdict
    note: str


class TargetedQcWidget(QWidget):
    sample_activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("targetedQc")

        self.chart = QChart()
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_view.mouseDoubleClickEvent = self._chart_view_double_click

        self.chart.setBackgroundVisible(False)
        self.chart.setPlotAreaBackgroundVisible(True)
        self.chart.setPlotAreaBackgroundBrush(QColor(255, 255, 255))
        self.chart.setTitle("Identity")
        self.chart.setTitleFont(QFont("Arial", 12, QFont.Bold))
        self.chart.setTitleBrush(QColor("black"))
        self.chart.setMargins(QMargins(2, 1, 5, 1))
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignBottom)
        self.chart.legend().setFont(QFont("Arial", 8))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chart_view)
        self.setMinimumHeight(200)
        self.setMaximumHeight(330)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._rows: list[_IdentityRow] = []

    def update_results(
        self, compound_name: str, sample_names: list[str], provider
    ) -> dict[str, str]:
        if not compound_name or not sample_names:
            self.clear()
            return {}

        rows: list[_IdentityRow] = []
        statuses: dict[str, str] = {}
        for sample_name in sample_names:
            try:
                result = provider.assess_unlabelled_identity(
                    sample_name, compound_name
                )
                error = None
            except Exception as exc:
                result = None
                error = str(exc)
            statuses[sample_name] = (
                result.status.value if result is not None else "unavailable"
            )
            rows.append(
                _IdentityRow(
                    sample_name=sample_name,
                    verdict=ratio_verdict(result),
                    note=_row_note(result, error),
                )
            )

        self._rows = rows
        add_identity_series(
            self.chart,
            [(row.sample_name, row.verdict) for row in rows],
            show_names=True,
        )
        self._connect_bar_signals()
        return statuses

    def clear(self) -> None:
        self._rows = []
        self.chart.removeAllSeries()
        for axis in list(self.chart.axes()):
            self.chart.removeAxis(axis)

    def _connect_bar_signals(self) -> None:
        for series in self.chart.series():
            for bar_set in series.barSets():
                bar_set.clicked.connect(self._on_bar_clicked)
                bar_set.hovered.connect(
                    lambda status, index, bs=bar_set: self._on_bar_hovered(bs, status, index)
                )

    def _row_at(self, index: int) -> _IdentityRow | None:
        display = list(reversed(self._rows))
        if index < 0 or index >= len(display):
            return None
        return display[index]

    def _on_bar_clicked(self, index: int) -> None:
        row = self._row_at(index)
        if row is None:
            return
        self.sample_activated.emit(row.sample_name)

    def _on_bar_hovered(self, bar_set: QBarSet, status: bool, index: int) -> None:
        if not status:
            QToolTip.hideText()
            return
        row = self._row_at(index)
        if row is None or float(bar_set.at(index)) <= 0:
            QToolTip.hideText()
            return
        show_identity_tooltip(
            self.chart_view,
            f"{row.sample_name}\n{bar_set.label()}\n{row.note}",
        )

    def _has_data(self) -> bool:
        return bool(self._rows)

    def _chart_view_double_click(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._has_data():
            self._show_popup_chart()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._has_data():
            self._show_popup_chart()
        super().mouseDoubleClickEvent(event)

    def _show_popup_chart(self) -> None:
        dialog = ChartPopupDialog(
            chart_type="identity",
            title="Identity",
            data=[row.verdict.value for row in self._rows],
            sample_names=[row.sample_name for row in self._rows],
            parent=self,
            hover_notes=[row.note for row in self._rows],
        )
        dialog.exec()
