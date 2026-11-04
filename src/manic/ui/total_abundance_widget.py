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
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QPainter, QMouseEvent
from PySide6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout, QWidget

from manic.io.eic_reader import EIC
from manic.ui.chart_header import ChartHeader
from manic.ui.chart_style import scale_text, style_axis, style_chart
from manic.ui.colors import abundance_colour

logger = logging.getLogger(__name__)


def abundances_from_provider(provider, compound_name: str, sample_names: list[str]) -> np.ndarray:
    return np.asarray(
        [
            provider.get_compound_total_area(sample_name, compound_name)
            for sample_name in sample_names
        ],
        dtype=float,
    )


class TotalAbundanceWidget(QWidget):
    """
    Horizontal bar chart showing total abundance for each sample.

    Shows the sum of all isotopologue areas for each sample, representing
    the total amount of compound detected (ignoring isotopic distribution).

    Companion to the isotopologue ratio widget - same integration logic but
    displays total abundance instead of relative ratios.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("totalAbundanceWidget")

        # Create chart and chart view
        self.chart = QChart()
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_view.setFrameShape(QFrame.NoFrame)
        self.chart_view.setStyleSheet("background: transparent; border: none;")
        self.chart_view.setToolTip("Double-click to enlarge with sample names")

        # Enable double-click on chart view
        self.chart_view.mouseDoubleClickEvent = self._chart_view_double_click

        style_chart(self.chart, QMargins(4, 0, 8, 0))

        self.header = ChartHeader("Total abundance")
        self.header.expand_button.clicked.connect(self._show_popup_chart)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.chart_view)

        # Responsive height to match isotopologue widget
        self.setMinimumHeight(200)
        self.setMaximumHeight(330)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.bar_color = abundance_colour

        # Data storage
        self._current_eics: Optional[List[EIC]] = None
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

        self._current_eics = eics
        self._current_compound = compound_name

        # Order to match graph window layout
        ordered_eics, ordered_abundances = self._order_like_graph_window(
            eics, abundances
        )

        # Reverse order so top graph corresponds to top bar
        ordered_eics.reverse()
        ordered_abundances = np.flip(ordered_abundances)  # Flip array
        
        # Store current data for popup
        self._current_abundances = ordered_abundances
        self._current_sample_names = [eic.sample_name for eic in ordered_eics]

        # Update chart
        self._update_chart(
            ordered_abundances, self._current_sample_names
        )

    def _order_like_graph_window(
        self, eics: List[EIC], abundances: np.ndarray
    ) -> tuple[List[EIC], np.ndarray]:
        """
        Order EICs and abundances to match the graph window's grid layout.
        Same logic as isotopologue widget.
        """
        import math

        num = len(eics)
        if num == 0:
            return eics, abundances

        # Same grid calculation as graph window
        cols = math.ceil(math.sqrt(num))
        math.ceil(num / cols)

        # Graph processes EICs in database order, so no reordering needed
        return eics, abundances

    def _update_chart(self, abundances: np.ndarray, sample_names: List[str]) -> None:
        """
        Update the horizontal bar chart with new abundance data.

        Args:
            abundances: Array of total abundance values
            sample_names: List of sample names for y-axis labels
        """
        # Clear existing data
        self.chart.removeAllSeries()

        # Create horizontal bar series (not stacked)
        bar_series = QHorizontalBarSeries()

        # Make bars same width as isotopologue chart
        bar_series.setBarWidth(0.8)

        # Create single bar set with all abundance values
        bar_set = QBarSet("Total Abundance")
        bar_set.setColor(self.bar_color)
        bar_set.setBorderColor(self.bar_color)

        # Calculate scaling for display like EIC plots
        max_abundance = float(np.max(abundances)) if len(abundances) > 0 else 1.0
        scale_exp = int(np.floor(np.log10(max_abundance))) if max_abundance > 0 else 0
        scale_factor = 10**scale_exp if scale_exp != 0 else 1

        # Add scaled abundance values
        for abundance in abundances:
            scaled_abundance = abundance / scale_factor
            bar_set.append(scaled_abundance)

        bar_series.append(bar_set)

        # Add series to chart
        self.chart.addSeries(bar_series)

        # Setup axes
        self._setup_axes(sample_names, abundances)

        # Attach series to axes
        bar_series.attachAxis(self.chart.axes(Qt.Horizontal)[0])
        bar_series.attachAxis(self.chart.axes(Qt.Vertical)[0])

    def _setup_axes(self, sample_names: List[str], abundances: np.ndarray) -> None:
        """Setup chart axes for horizontal layout."""
        # Remove existing axes
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)

        # X-axis (horizontal): Abundance values with EIC-style scaling
        x_axis = QValueAxis()
        max_abundance = float(np.max(abundances)) if len(abundances) > 0 else 1.0

        # Calculate scaling factor like EIC plots
        scale_exp = int(np.floor(np.log10(max_abundance))) if max_abundance > 0 else 0
        scale_factor = 10**scale_exp if scale_exp != 0 else 1

        # Scale the range and data
        scaled_max = max_abundance / scale_factor
        x_axis.setRange(0, scaled_max * 1.05)  # Add 5% padding

        # Store scale info for later use
        self._scale_exp = scale_exp
        self._scale_factor = scale_factor

        x_axis.setLabelFormat("%.1f")
        style_axis(x_axis, grid=True)
        x_axis.setLineVisible(False)
        x_axis.setTickCount(3)
        self.header.set_has_data(True, scale_text(scale_exp))

        # Sample names are hidden here; the enlarged view shows them.
        y_axis = QBarCategoryAxis()
        y_axis.append(sample_names)
        style_axis(y_axis)
        y_axis.setLineVisible(False)
        y_axis.setLabelsVisible(False)

        # Add axes to chart
        self.chart.addAxis(x_axis, Qt.AlignBottom)
        self.chart.addAxis(y_axis, Qt.AlignLeft)

    def _clear_chart(self) -> None:
        """Clear the chart when no data is available."""
        self.chart.removeAllSeries()
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)
        self.header.set_has_data(False)

        # Reset data
        self._current_eics = None
        self._current_compound = ""
        self._current_abundances = None
        self._current_sample_names = None

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
                title="Total Abundance",
                data=self._current_abundances,
                sample_names=self._current_sample_names,
                parent=self,
                compound_name=self._current_compound,
            )
            dialog.exec()
            
        except Exception as e:
            logger.exception("Failed to show popup chart: %s", e)
