from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np
from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSet,
    QChart,
    QChartView,
    QHorizontalStackedBarSeries,
    QValueAxis,
)
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from manic.io.compound_reader import read_compound_with_session
from manic.io.eic_reader import EIC
from manic.processors.eic_correction_manager import read_corrected_eic

from .colors import label_colors

logger = logging.getLogger(__name__)


class IsotopologueRatioWidget(QWidget):
    """
    Horizontal stacked bar chart showing isotopologue ratios for each sample.

    Uses on-demand integration to calculate ratios from EIC data within
    user-defined integration boundaries (retention_time ± offsets).

    Horizontal layout is better for handling many samples as as there is more vertical space.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("isotopologueRatioWidget")

        # Flag to use corrected data when available
        self.use_corrected = True

        # Create chart and chart view
        self.chart = QChart()
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Enable double-click on chart view
        self.chart_view.mouseDoubleClickEvent = self._chart_view_double_click

        # Setup chart appearance
        self.chart.setBackgroundVisible(False)
        self.chart.setPlotAreaBackgroundVisible(True)
        self.chart.setPlotAreaBackgroundBrush(QColor(255, 255, 255))
        self.chart.legend().setVisible(False)
        self.chart.setTitle("Label Incorporation")
        self.chart.setTitleFont(QFont("Arial", 12, QFont.Bold))
        self.chart.setTitleBrush(QColor("black"))
        self.chart.setMargins(QMargins(2, 1, 5, 1))

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chart_view)

        # Responsive height for toolbar integration
        self.setMinimumHeight(200)
        self.setMaximumHeight(330)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # Data storage
        self._current_eics: Optional[List[EIC]] = None
        self._current_compound: str = ""
        self._last_total_abundances: Optional[np.ndarray] = None
        self._last_eics: Optional[List[EIC]] = None
        self._current_ratios: Optional[np.ndarray] = None
        self._current_sample_names: Optional[List[str]] = None

    def update_ratios(self, compound_name: str, eics: List[EIC]) -> None:
        """
        Update the chart with new isotopologue ratios.

        Args:
            compound_name: Name of the compound
            eics: List of EIC data for each sample
        """
        if not eics or not compound_name:
            self._clear_chart()
            return

        self._current_eics = eics
        self._current_compound = compound_name

        # Calculate both ratios and total abundances using unified integration
        ratios, total_abundances = self._calculate_integrated_data(eics, compound_name)

        if ratios is None:
            self._clear_chart()
            return

        # Store total abundances for sharing with total abundance widget
        self._last_total_abundances = total_abundances
        self._last_eics = eics

        # Check if this compound has isotopologues
        if eics[0].intensity.ndim == 1:
            # Single trace - don't show isotopologue chart (it would just be 100%)
            self._clear_chart()
            # But we still have the abundance data stored for the total abundance widget
            return

        # Order EICs to match graph window layout (left-to-right, top-to-bottom in grid)
        # But reverse for horizontal bars (QtCharts displays from bottom-to-top)
        ordered_eics, ordered_ratios = self._order_like_graph_window(eics, ratios)

        # Reverse order so top graph corresponds to top bar
        ordered_eics.reverse()
        ordered_ratios = np.flipud(ordered_ratios)  # Flip array upside down

        # Store current data for popup
        self._current_ratios = ordered_ratios
        self._current_sample_names = [eic.sample_name for eic in ordered_eics]

        # Update chart
        self._update_chart(ordered_ratios, self._current_sample_names)

    def _calculate_integrated_data(
        self, eics: List[EIC], compound_name: str
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Calculate both isotopologue ratios and total abundances using unified integration.

        Integrates each isotopologue trace within the integration boundaries
        defined by retention_time ± offsets, then calculates both ratios and total abundances.

        Args:
            eics: List of EIC data
            compound_name: Name of compound for integration parameters

        Returns:
            Tuple of (ratios_array, total_abundances_array) or (None, None) if no data
            - ratios: Array of shape (n_samples, n_isotopologues) with ratios
            - total_abundances: Array of shape (n_samples,) with total integrated areas
        """
        ratios = []
        total_abundances = []

        for eic in eics:
            # Get integration parameters (with session overrides if available)
            compound = read_compound_with_session(compound_name, eic.sample_name)

            # Define integration boundaries
            rt = compound.retention_time
            loffset = compound.loffset
            roffset = compound.roffset

            left_bound = rt - loffset
            right_bound = rt + roffset

            # Find time points within integration window
            mask = (eic.time >= left_bound) & (eic.time <= right_bound)

            if not np.any(mask):
                # No data points in integration window
                if eic.intensity.ndim == 1:
                    # Single trace
                    ratios.append(np.array([1.0]))  # 100% for single isotope
                    total_abundances.append(0.0)
                else:
                    # Multi-trace
                    num_isotopologues = eic.intensity.shape[0]
                    ratios.append(np.zeros(num_isotopologues))
                    total_abundances.append(0.0)
                continue

            # Check if single or multi-trace
            if eic.intensity.ndim == 1:
                # Single trace - integrate directly
                area = np.trapz(eic.intensity[mask], eic.time[mask])
                area = max(0, area)  # Ensure non-negative

                # For single trace: ratio is always 1.0 (100%)
                ratios.append(np.array([1.0]))
                total_abundances.append(area)
            else:
                # Multi-trace - check for corrected data if enabled
                intensity_to_use = eic.intensity

                if self.use_corrected:
                    corrected = read_corrected_eic(eic.sample_name, compound_name)
                    if corrected is not None:
                        intensity_to_use = corrected
                        logger.info(
                            f"Using corrected data for {compound_name} in {eic.sample_name}"
                        )
                    else:
                        logger.debug(
                            f"No corrected data available for {compound_name} in {eic.sample_name}"
                        )

                # Integrate each isotopologue
                isotope_areas = []
                for i in range(intensity_to_use.shape[0]):
                    area = np.trapz(intensity_to_use[i, mask], eic.time[mask])
                    isotope_areas.append(max(0, area))  # Ensure non-negative

                # Calculate total abundance (sum of all isotopologue areas)
                total_area = sum(isotope_areas)
                total_abundances.append(total_area)

                # Calculate ratios from same areas
                if total_area > 0:
                    ratios.append(np.array(isotope_areas) / total_area)
                else:
                    ratios.append(np.zeros(len(isotope_areas)))

        if ratios:
            return np.array(ratios), np.array(total_abundances)
        else:
            return None, None

    def _order_like_graph_window(
        self, eics: List[EIC], ratios: np.ndarray
    ) -> tuple[List[EIC], np.ndarray]:
        """
        Order EICs and ratios to match the graph window's grid layout.

        Graph window uses: row = i // cols, col = i % cols
        This creates a left-to-right, top-to-bottom ordering.

        Args:
            eics: Original EIC list
            ratios: Original ratios array

        Returns:
            Tuple of (ordered_eics, ordered_ratios) matching graph layout
        """
        import math

        num = len(eics)
        if num == 0:
            return eics, ratios

        # Same grid calculation as graph window
        cols = math.ceil(math.sqrt(num))
        rows = math.ceil(num / cols)

        # Create ordering that matches graph window grid positions
        # Graph adds widgets as: row = i // cols, col = i % cols
        # So we maintain the same order - no reordering needed!
        # The graph window processes EICs in the same order they come from the database

        return eics, ratios

    def _update_chart(self, ratios: np.ndarray, sample_names: List[str]) -> None:
        """
        Update the horizontal stacked bar chart with new ratio data.

        Args:
            ratios: Array of shape (n_samples, n_isotopologues)
            sample_names: List of sample names for y-axis labels
        """
        # Clear existing data
        self.chart.removeAllSeries()

        # Create horizontal stacked bar series
        bar_series = QHorizontalStackedBarSeries()

        # Make bars wider (taller in horizontal orientation)
        bar_series.setBarWidth(0.8)

        n_samples, n_isotopologues = ratios.shape

        # Create one bar set per isotopologue (M+0, M+1, etc.)
        bar_sets = []
        for i in range(n_isotopologues):
            bar_set = QBarSet(f"M+{i}")
            bar_set.setColor(label_colors[i % len(label_colors)])

            # Add ratio values for this isotopologue across all samples
            for j in range(n_samples):
                bar_set.append(ratios[j, i])

            bar_sets.append(bar_set)
            bar_series.append(bar_set)

        # Add series to chart
        self.chart.addSeries(bar_series)

        # Setup axes
        self._setup_axes(sample_names)

        # Attach series to axes
        bar_series.attachAxis(self.chart.axes(Qt.Horizontal)[0])
        bar_series.attachAxis(self.chart.axes(Qt.Vertical)[0])

    def _setup_axes(self, sample_names: List[str]) -> None:
        """Setup chart axes for horizontal layout."""
        # Remove existing axes
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)

        # X-axis (horizontal): Ratio values (0 to 1)
        x_axis = QValueAxis()
        x_axis.setRange(0, 1)
        x_axis.setLabelFormat("%.1f")
        x_axis.setLabelsFont(QFont("Arial", 8))
        x_axis.setGridLineVisible(False)
        x_axis.setLineVisible(False)
        x_axis.setTickCount(6)  # 0, 0.2, 0.4, 0.6, 0.8, 1.0
        x_axis.setLabelsVisible(True)

        # Y-axis (vertical): Sample names - hidden to save space
        y_axis = QBarCategoryAxis()
        y_axis.append(sample_names)
        y_axis.setLabelsFont(QFont("Arial", 8))
        y_axis.setGridLineVisible(False)
        y_axis.setLineVisible(False)
        y_axis.setLabelsVisible(False)  # Hide sample names to save space

        # Add axes to chart
        self.chart.addAxis(x_axis, Qt.AlignBottom)
        self.chart.addAxis(y_axis, Qt.AlignLeft)

    def _clear_chart(self) -> None:
        """Clear the chart when no data is available."""
        self.chart.removeAllSeries()
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)

        # Reset data
        self._current_eics = None
        self._current_compound = ""
        self._last_total_abundances = None
        self._last_eics = None
        self._current_ratios = None
        self._current_sample_names = None

    def get_last_total_abundances(
        self,
    ) -> tuple[Optional[np.ndarray], Optional[List[EIC]]]:
        """Get the last calculated total abundances to share with total abundance widget"""
        return self._last_total_abundances, self._last_eics

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
        return (
            self._current_ratios is not None
            and self._current_sample_names is not None
            and len(self._current_ratios) > 0
        )

    def set_use_corrected(self, use_corrected: bool) -> None:
        """
        Set whether to use corrected data when available.

        Args:
            use_corrected: If True, use natural abundance corrected data
        """
        logger.info(f"Setting use_corrected to {use_corrected}")
        self.use_corrected = use_corrected
        # Refresh current display if we have data
        if self._current_eics and self._current_compound:
            logger.info(f"Refreshing display for {self._current_compound}")
            self.update_ratios(self._current_compound, self._current_eics)

    def _show_popup_chart(self):
        """Show enlarged chart in popup dialog."""
        try:
            from manic.ui.chart_popup_dialog import ChartPopupDialog

            dialog = ChartPopupDialog(
                chart_type="isotopologue_ratios",
                title="Label Incorporation",
                data=self._current_ratios,
                sample_names=self._current_sample_names,
                parent=self,
            )
            dialog.exec()

        except Exception as e:
            print(f"Failed to show popup chart: {e}")
