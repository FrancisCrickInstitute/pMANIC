from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np
from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSet,
    QChart,
    QChartView,
    QHorizontalBarSeries,
    QValueAxis,
)
from PySide6.QtCore import QMargins, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsSimpleTextItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from manic.io.compound_reader import read_compound
from manic.io.eic_reader import EIC
from manic.ui import theme
from manic.ui.chart_header import ChartHeader
from manic.ui.chart_popup_dialog import PinnedAxis, bar_value_text, value_axis_ticks
from manic.ui.chart_style import (
    BarRows,
    abundance_scale,
    fit_category_names,
    fit_name_font,
    place_row_notes,
    scale_text,
    set_nice_ticks,
    style_axis,
    style_chart,
)
from manic.ui.sidebar_widgets import SummaryChartArea

from manic.ui.theme import color

logger = logging.getLogger(__name__)


def peak_area_label(compound_name: str) -> str:
    """What the bars measure, as DataProvider.get_compound_total_area takes it."""
    if read_compound(compound_name).is_unlabelled_target:
        return "Q-ion peak area"
    return "Peak area, sum of isotopologues"


def abundances_from_provider(provider, compound_name: str, sample_names: list[str]) -> np.ndarray:
    return np.asarray(
        [
            provider.get_compound_total_area(sample_name, compound_name)
            for sample_name in sample_names
        ],
        dtype=float,
    )


class TotalAbundanceWidget(QWidget):
    """Horizontal bar chart of each sample's peak area (peak_area_label names it).

    Companion to the isotopologue ratio widget: same integration, but the
    summed area instead of the ratios.
    """

    sample_activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("totalAbundanceWidget")

        self.chart = QChart()
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_view.setFrameShape(QFrame.NoFrame)
        self.chart_view.setStyleSheet("QChartView { background: transparent; border: none; }")

        self.chart_view.mouseDoubleClickEvent = self._chart_view_double_click
        self._rows = BarRows(
            self.chart,
            self.chart_view,
            lambda row: self.sample_activated.emit(self._current_sample_names[row]),
            lambda row, _value: self.hover_text(row),
            waits_for_double_click=True,
        )

        style_chart(self.chart, QMargins(8, 0, 8, 0))

        self.header = ChartHeader("Peak area")
        self.header.expand_button.clicked.connect(self._show_popup_chart)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        # The value axis stays above the rows while they scroll, as in the popup.
        self.value_axis = PinnedAxis(self.chart_view)
        layout.addWidget(self.value_axis)
        self.chart_area = SummaryChartArea(self.chart_view, 4)
        layout.addWidget(self.chart_area)
        self.chart.plotAreaChanged.connect(self._fit_names)
        # A bar too short to see reads as the popup prints it: "0", "<0.01" or "—".
        self._row_notes: list[QGraphicsSimpleTextItem] = []
        self.chart.plotAreaChanged.connect(self._place_row_notes)
        theme.notifier.changed.connect(self._place_row_notes)

        # The grid's selected samples, drawn in the accent colour.
        self._highlighted: set[str] = set()
        theme.notifier.changed.connect(self._paint_highlight)

        # No taller than its rows, so the panel stacks the next chart right under it.
        layout.setSizeConstraint(QVBoxLayout.SetMinAndMaxSize)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._current_compound: str = ""
        self._current_abundances: Optional[np.ndarray] = None
        self._current_sample_names: Optional[List[str]] = None


    def update_abundance_from_data(
        self, compound_name: str, eics: List[EIC], abundances: np.ndarray
    ) -> None:
        """
        Update chart using pre-calculated abundance data (shared from isotopologue widget).
        This avoids duplicate integration calculations.
        """
        if not eics or not compound_name or abundances is None:
            self._clear_chart()
            return

        self._current_compound = compound_name

        # Reverse order so top graph corresponds to top bar
        ordered_eics = eics[::-1]
        ordered_abundances = np.flip(abundances)
        
        self._current_abundances = ordered_abundances
        self._current_sample_names = [eic.sample_name for eic in ordered_eics]

        self._update_chart(
            ordered_abundances, self._current_sample_names
        )

    def _update_chart(self, abundances: np.ndarray, sample_names: List[str]) -> None:
        """One horizontal bar per sample, labelled with ``sample_names``."""
        self.chart.removeAllSeries()

        bar_series = QHorizontalBarSeries()

        # Make bars same width as isotopologue chart
        bar_series.setBarWidth(0.8)

        bar_set = QBarSet("Total Abundance")
        # Neutral ink, so the accent marks only the grid's selection (see _paint_highlight).
        bar_set.setColor(color("text_tertiary"))
        bar_set.setPen(QPen(Qt.NoPen))

        _top, scale_exp = abundance_scale(abundances)
        for abundance in abundances:
            bar_set.append(abundance / 10**scale_exp if np.isfinite(abundance) else 0.0)

        bar_series.append(bar_set)

        self.chart.addSeries(bar_series)
        self.chart_area.set_rows(len(sample_names))

        self._setup_axes(sample_names, abundances)

        bar_series.attachAxis(self.chart.axes(Qt.Horizontal)[0])
        bar_series.attachAxis(self.chart.axes(Qt.Vertical)[0])
        # New axes start with full names at the axis size; the plot area may not change to refit them.
        self._fit_names()
        self._paint_highlight()
        self._place_row_notes()
        self._rows.refresh()

    def _place_row_notes(self, *_args) -> None:
        texts = {}
        if self._has_data():
            _top, scale_exp = abundance_scale(self._current_abundances)
            for row, value in enumerate(self._current_abundances / 10**scale_exp):
                text = bar_value_text(value)
                if text in ("—", "0", "<0.01"):
                    texts[row] = text
        place_row_notes(self.chart, self._row_notes, texts)

    def _fit_names(self, *_args) -> None:
        axes = self.chart.axes(Qt.Vertical)
        if self._current_sample_names and axes:
            fit_name_font(self.chart, axes[0])
            fit_category_names(axes[0], self._current_sample_names, self.chart_view.width())

    def set_highlighted(self, sample_names) -> None:
        """Mark the bars of the samples selected in the grid and scroll to them."""
        self._highlighted = set(sample_names)
        self._paint_highlight()
        names = self._current_sample_names or []
        self.chart_area.show_rows(
            self.chart, [i for i, name in enumerate(names) if name in self._highlighted]
        )

    def _paint_highlight(self, *_args) -> None:
        if not self.chart.series() or not self._has_data():
            return
        bar_set = self.chart.series()[0].barSets()[0]
        bar_set.setSelectedColor(color("accent"))
        bar_set.deselectAllBars()
        bar_set.selectBars(
            [
                i
                for i, name in enumerate(self._current_sample_names)
                if name in self._highlighted
            ]
        )

    def hover_text(self, index: int) -> str:
        value = float(self._current_abundances[index])
        shown = f"{value:.3g}" if np.isfinite(value) else "—"
        return f"{self._current_sample_names[index]}\nPeak area  {shown}"

    def _setup_axes(self, sample_names: List[str], abundances: np.ndarray) -> None:
        """Setup chart axes for horizontal layout."""
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)

        x_axis = QValueAxis()
        max_abundance, scale_exp = abundance_scale(abundances)
        scaled_max = max_abundance / 10**scale_exp
        x_axis.setRange(0, scaled_max * 1.05)
        set_nice_ticks(x_axis, 0, scaled_max * 1.05, max_ticks=2)

        style_axis(x_axis, grid=True)
        x_axis.setLineVisible(False)
        x_axis.setLabelsVisible(False)
        self.header.set_has_data(True, scale_text(scale_exp))

        y_axis = QBarCategoryAxis()
        y_axis.append(sample_names)
        style_axis(y_axis)
        y_axis.setLineVisible(False)

        self.chart.addAxis(x_axis, Qt.AlignTop)
        self.chart.addAxis(y_axis, Qt.AlignLeft)
        self.value_axis.set_axis("", value_axis_ticks(x_axis))

    def _clear_chart(self) -> None:
        """Clear the chart when no data is available."""
        self.chart.removeAllSeries()
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)
        self.header.set_has_data(False)
        self.value_axis.set_axis("", [])
        self.chart_area.set_rows(0)

        self._current_compound = ""
        self._current_abundances = None
        self._current_sample_names = None
        self._place_row_notes()
        self._rows.refresh()

    def _chart_view_double_click(self, event: QMouseEvent):
        """Handle double-click on chart view to show popup chart."""
        if event.button() == Qt.LeftButton and self._has_data():
            self._show_popup_chart()
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Handle double-click on widget (but not chart view) to show popup chart."""
        if event.button() == Qt.LeftButton and self._has_data():
            self._show_popup_chart()
        super().mouseDoubleClickEvent(event)
    
    def _has_data(self) -> bool:
        """Check if chart has data to display."""
        return (self._current_abundances is not None and 
                self._current_sample_names is not None and 
                len(self._current_abundances) > 0)
    
    def _show_popup_chart(self):
        """Show enlarged chart in popup dialog."""
        try:
            from manic.ui.chart_popup_dialog import ChartPopupDialog
            
            dialog = ChartPopupDialog(
                chart_type="total_abundance",
                title="Peak area",
                data=self._current_abundances,
                sample_names=self._current_sample_names,
                parent=self,
                compound_name=self._current_compound,
                highlighted=self._highlighted,
                quantity=peak_area_label(self._current_compound),
            )
            dialog.sample_activated.connect(self.sample_activated)
            dialog.exec()
            
        except Exception as e:
            logger.exception("Failed to show popup chart: %s", e)
