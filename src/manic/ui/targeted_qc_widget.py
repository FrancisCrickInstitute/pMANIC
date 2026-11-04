from __future__ import annotations

from PySide6.QtCharts import QBarSet, QChart, QChartView
from PySide6.QtCore import QMargins, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QToolTip, QVBoxLayout, QWidget

from manic.ui.chart_header import ChartHeader
from manic.ui.chart_popup_dialog import (
    ChartPopupDialog,
    identity_key_html,
    identity_key_tooltip,
)
from manic.ui.chart_style import style_chart, text_style
from manic.ui.identity_chart import (
    IdentityGridBinding,
    add_identity_grid,
    identity_cell_tooltip,
    identity_chart_height,
    show_identity_tooltip,
)
from manic.ui import theme
from manic.validation.unlabelled_identity import IdentityAssessmentSet, QualifierStatus


class TargetedQcWidget(QWidget):
    sample_activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("targetedQc")

        self.chart = QChart()
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_view.setFrameShape(QFrame.NoFrame)
        self.chart_view.setStyleSheet("background: transparent; border: none;")
        self.chart_view.setToolTip(
            "One row per sample. Click a row to select that sample; "
            "double-click to enlarge with sample names."
        )
        self.chart_view.mouseDoubleClickEvent = self._chart_view_double_click

        style_chart(self.chart, QMargins(0, 0, 0, 0))

        self.header = ChartHeader("Identity")
        self.header.expand_button.clicked.connect(self._show_popup_chart)

        self.key = QLabel()
        self.key.setTextFormat(Qt.RichText)
        self.key.setWordWrap(True)
        self.key.setAlignment(Qt.AlignHCenter)
        theme.style(self.key, text_style("text_secondary", 11))
        self.key.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 4)
        layout.setSpacing(2)
        layout.addWidget(self.header)
        layout.addWidget(self.chart_view)
        layout.addWidget(self.key)
        layout.addStretch()
        self.setMinimumHeight(200)
        self.setMaximumHeight(330)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._identity: IdentityAssessmentSet | None = None
        self._binding: IdentityGridBinding | None = None

    def update_results(self, identity: IdentityAssessmentSet) -> None:
        if not identity.samples:
            self.clear()
            return

        self._identity = identity
        self._binding = add_identity_grid(
            self.chart, identity.samples, show_sample_names=False
        )
        self.chart_view.setMaximumHeight(identity_chart_height(len(identity.samples)))
        self._connect_cell_signals()
        failed = sum(
            any(q.status is QualifierStatus.FAILED for q in sample.qualifiers)
            for sample in identity.samples
        )
        count = len(identity.samples)
        self.header.set_has_data(
            True, f"{count} sample{'s' if count != 1 else ''}"
            + (f" · {failed} sample{'s' if failed != 1 else ''} failed" if failed else "")
        )
        self.key.setText(identity_key_html(identity))
        self.key.setToolTip(identity_key_tooltip(identity))
        self.key.show()

    def clear(self) -> None:
        self._identity = None
        self._binding = None
        self.header.set_has_data(False)
        self.key.hide()
        self.chart_view.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        add_identity_grid(self.chart, ())

    def _connect_cell_signals(self) -> None:
        if self._binding is None:
            return
        for bar_set in self._binding.bar_sets:
            bar_set.hovered.connect(
                lambda status, index, bound=bar_set: self._on_grid_hovered(
                    bound, status, index
                )
            )
            bar_set.clicked.connect(
                lambda index, bound=bar_set: self._on_grid_clicked(bound, index)
            )

    def _on_grid_clicked(self, bar_set: QBarSet, _index: int) -> None:
        if self._binding is None:
            return
        cell = self._binding.cell_for(bar_set)
        if cell is None:
            return
        self.sample_activated.emit(cell.sample_name)

    def _on_grid_hovered(self, bar_set: QBarSet, status: bool, index: int) -> None:
        if (
            not status
            or self._binding is None
            or index < 0
            or index >= bar_set.count()
            or bar_set.at(index) <= 0
        ):
            QToolTip.hideText()
            return
        cell = self._binding.cell_for(bar_set)
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
        dialog = ChartPopupDialog.for_identity(self._identity, parent=self)
        dialog.sample_activated.connect(self.sample_activated)
        dialog.exec()
