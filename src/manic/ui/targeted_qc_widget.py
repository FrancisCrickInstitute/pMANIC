from __future__ import annotations

from PySide6.QtCharts import QChart, QChartView
from PySide6.QtCore import QMargins, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter
from PySide6.QtWidgets import QLabel, QSizePolicy, QToolTip, QVBoxLayout, QWidget

from manic.ui.channel_labels import channel_legend_text
from manic.ui.chart_popup_dialog import ChartPopupDialog
from manic.ui.identity_chart import (
    IdentityChartBinding,
    add_identity_series,
    identity_cell_tooltip,
    show_identity_tooltip,
)
from manic.validation.unlabelled_identity import IdentityAssessmentSet


class TargetedQcWidget(QWidget):
    sample_activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("targetedQc")

        self.ion_legend = QLabel("")
        self.ion_legend.setWordWrap(True)
        self.ion_legend.setContentsMargins(4, 2, 4, 2)
        self.ion_legend.setStyleSheet(
            "color: #333; font-size: 11px; background: transparent;"
        )
        self.ion_legend.hide()

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
        layout.addWidget(self.ion_legend)
        layout.addWidget(self.chart_view)
        self.setMinimumHeight(200)
        self.setMaximumHeight(330)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._identity: IdentityAssessmentSet | None = None
        self._binding: IdentityChartBinding | None = None

    def update_results(self, identity: IdentityAssessmentSet) -> None:
        if not identity.samples:
            self.clear()
            return

        self._identity = identity
        self.ion_legend.setText(
            channel_legend_text(identity.compound_name, identity.channels)
        )
        self.ion_legend.show()
        self._binding = add_identity_series(
            self.chart,
            identity.samples,
            show_names=True,
        )
        self._connect_cell_signals()

    def clear(self) -> None:
        self._identity = None
        self._binding = None
        self.ion_legend.clear()
        self.ion_legend.hide()
        self.chart.removeAllSeries()
        for axis in list(self.chart.axes()):
            self.chart.removeAxis(axis)

    def _connect_cell_signals(self) -> None:
        if self._binding is None:
            return
        for series in self._binding.series:
            series.clicked.connect(self._on_cell_clicked)
            series.hovered.connect(self._on_cell_hovered)

    def _on_cell_clicked(self, point: QPointF) -> None:
        if self._binding is None:
            return
        cell = self._binding.cell_at(point)
        if cell is None:
            return
        self.sample_activated.emit(cell.sample_name)

    def _on_cell_hovered(self, point: QPointF, entered: bool) -> None:
        if not entered or self._binding is None:
            QToolTip.hideText()
            return
        cell = self._binding.cell_at(point)
        if cell is None:
            QToolTip.hideText()
            return
        show_identity_tooltip(self.chart_view, identity_cell_tooltip(cell))

    def _has_data(self) -> bool:
        return self._identity is not None and bool(self._identity.samples)

    def _chart_view_double_click(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._has_data():
            self._show_popup_chart()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._has_data():
            self._show_popup_chart()
        super().mouseDoubleClickEvent(event)

    def _show_popup_chart(self) -> None:
        if self._identity is None:
            return
        ChartPopupDialog.for_identity(self._identity, parent=self).exec()
