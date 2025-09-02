import logging
import math
from typing import List, Set

import numpy as np
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QMargins, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsTextItem,
    QGridLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from manic.io.compound_reader import read_compound_with_session
from manic.processors.eic_processing import get_eics_for_compound
from manic.utils.timer import measure_time

logger = logging.getLogger(__name__)

# Import shared colors
from .colors import dark_red_colour, label_colors, selection_color, steel_blue_colour


class ClickableChartView(QChartView):
    """Custom QChartView that can be selected"""

    clicked = Signal(object)  # Signal to emit when clicked

    def __init__(self, chart, sample_name, parent=None):
        super().__init__(chart, parent)
        self.sample_name = sample_name
        self.is_selected = False
        self.setRenderHint(QPainter.Antialiasing)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def mousePressEvent(self, event):
        """Handle mouse clicks"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        """Set the selection state and update appearance"""
        self.is_selected = selected
        self.update_appearance()

    def update_appearance(self):
        """Update the visual appearance based on selection state"""
        if self.is_selected:
            # Set light green background
            self.chart().setPlotAreaBackgroundBrush(selection_color)
        else:
            # Set normal white background
            self.chart().setPlotAreaBackgroundBrush(QColor(255, 255, 255))


class GraphView(QWidget):
    """
    Re-implements the old grid-of-charts look with pyqtgraph,
    but fetches data via the new processors/io stack.
    """

    # Signal to emit when plot selection changes
    selection_changed = Signal(list)  # List of selected sample names

    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QGridLayout(self)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # Track selected plots
        self._selected_plots: Set[ClickableChartView] = set()

        # Store all current plots for easy access
        self._current_plots: List[ClickableChartView] = []

        # Store current compound and samples for integration window updates
        self._current_compound: str = ""
        self._current_samples: List[str] = []

        # throttle resize events – avoids constant redraw while user resizes
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._update_graph_sizes)

    # public function
    def plot_compound(self, compound_name: str, samples: List[str]) -> None:
        """
        Build one mini-plot per active sample for the selected *compound*.
        """

        logging.info("plotting compound")
        self._clear_layout()
        if not samples:
            return

        # Store current compound and samples for integration window updates
        self._current_compound = compound_name
        self._current_samples = samples

        # time db retreival for debugging
        with measure_time("get_eics_from_db"):
            eics = get_eics_for_compound(compound_name, samples)  # new pipeline

        num = len(eics)
        if num == 0:
            return
        cols = math.ceil(math.sqrt(num))
        rows = math.ceil(num / cols)

        # Set stretch factors once, outside the loop
        for col in range(cols):
            self._layout.setColumnStretch(col, 1)
        for row in range(rows):
            self._layout.setRowStretch(row, 1)

        # time plot building for debugging
        with measure_time("build_plots_and_add_to_layout"):
            # Build all plots with captions first
            plot_containers = [self._build_plot_with_caption(eic) for eic in eics]

            # Extract chart views for click handling
            self._current_plots = [
                container.chart_view for container in plot_containers
            ]

            # Connect click signals
            for container in plot_containers:
                container.chart_view.clicked.connect(self._on_plot_clicked)

            # Add to layout in one go
            for i, container in enumerate(plot_containers):
                row = i // cols
                col = i % cols
                self._layout.addWidget(container, row, col)

        # ensure the added widgets are correctly sized with stretch factors
        self._update_graph_sizes()

    def _on_plot_clicked(self, clicked_plot: ClickableChartView):
        """Handle plot click - toggle selection"""
        if clicked_plot.is_selected:
            # Deselect if already selected
            self._selected_plots.discard(clicked_plot)
            clicked_plot.set_selected(False)
        else:
            # Select the clicked plot
            self._selected_plots.add(clicked_plot)
            clicked_plot.set_selected(True)

        # Emit signal with currently selected sample names
        selected_samples = [plot.sample_name for plot in self._selected_plots]
        self.selection_changed.emit(selected_samples)

        # Update integration window title
        self._update_integration_title()

    def _update_integration_title(self):
        """Update the integration window title based on selection"""
        if not self._selected_plots:
            title = "Selected Plots: All"
        elif len(self._selected_plots) == 1:
            sample_name = next(iter(self._selected_plots)).sample_name
            title = f"Selected Plots: {sample_name}"
        else:
            title = f"Selected Plots: {len(self._selected_plots)} samples"

        # Integration window title is updated via signals

    def get_selected_samples(self) -> List[str]:
        """Get list of currently selected sample names"""
        return [plot.sample_name for plot in self._selected_plots]

    def get_current_compound(self) -> str:
        """Get the currently displayed compound"""
        return self._current_compound

    def get_current_samples(self) -> List[str]:
        """Get the list of all currently displayed samples"""
        return self._current_samples.copy()

    def clear_selection(self):
        """Clear all plot selections"""
        for plot in self._selected_plots:
            plot.set_selected(False)
        self._selected_plots.clear()
        self.selection_changed.emit([])

    def select_all_plots(self):
        """Select all currently displayed plots"""
        for plot in self._current_plots:
            if not plot.is_selected:
                plot.set_selected(True)
                self._selected_plots.add(plot)
        
        # Emit signal with all selected sample names
        selected_samples = [plot.sample_name for plot in self._selected_plots]
        self.selection_changed.emit(selected_samples)
        self._update_integration_title()

    def deselect_all_plots(self):
        """Deselect all currently selected plots"""
        self.clear_selection()
        self._update_integration_title()

    def contextMenuEvent(self, event):
        """
        Handle right-click context menu for plot selection.
        
        This method is automatically called by Qt when:
        - User right-clicks anywhere in the graph window
        - User presses the context menu key on keyboard  
        - User performs platform-specific context menu gesture
        
        Qt's QWidget base class automatically detects right-click events
        and converts them to context menu events, then calls this override.
        """
        if not self._current_plots:
            return
        
        # Create context menu with selection options
        context_menu = QMenu(self)
        
        # Add select all action
        select_all_action = context_menu.addAction("Select All")
        select_all_action.triggered.connect(self.select_all_plots)
        
        # Add deselect all action
        deselect_all_action = context_menu.addAction("Deselect All")
        deselect_all_action.triggered.connect(self.deselect_all_plots)
        
        # Show the menu at the cursor position (where right-click occurred)
        context_menu.exec_(event.globalPos())

    def refresh_plots_with_session_data(self):
        """
        Refresh the current plots using session data where available.

        This method rebuilds all current plots, using session activity data
        where it exists, while preserving the current plot selection state.
        """
        if not self._current_compound or not self._current_samples:
            logger.warning("Cannot refresh plots: no current compound or samples")
            return

        # Store current selection state
        selected_sample_names = {plot.sample_name for plot in self._selected_plots}

        try:
            with measure_time("refresh_plots_with_session_data"):
                # Clear existing selection tracking before re-plotting
                self._selected_plots.clear()

                # Re-plot the compound with the same samples
                self.plot_compound(self._current_compound, self._current_samples)

                # Restore selection state - need to be careful with timing
                # since _current_plots is updated in plot_compound
                restored_count = 0
                for plot in self._current_plots:
                    if plot.sample_name in selected_sample_names:
                        plot.set_selected(True)
                        self._selected_plots.add(plot)
                        restored_count += 1

                # Emit selection signal to update integration window
                selected_samples = [plot.sample_name for plot in self._selected_plots]
                self.selection_changed.emit(selected_samples)

                logger.info(
                    f"Refreshed {len(self._current_plots)} plots for '{self._current_compound}' "
                    f"with session data. Restored {restored_count} selections."
                )

        except Exception as e:
            logger.error(f"Failed to refresh plots with session data: {e}")
            # Try to maintain some UI state even if refresh fails
            try:
                selected_samples = [plot.sample_name for plot in self._selected_plots]
                self.selection_changed.emit(selected_samples)
            except:
                pass  # Don't cascade failures

    #  internal functions
    def _build_plot_with_caption(self, eic) -> QWidget:
        """Create a widget containing a plot with sample name caption below."""
        # Create the plot
        chart_view = self._build_plot(eic)

        # Create caption label
        caption = QLabel(eic.sample_name)
        caption.setAlignment(Qt.AlignCenter)
        caption.setFont(QFont("Arial", 9, QFont.Bold))
        caption.setStyleSheet("color: black; padding: 2px;")
        caption.setMaximumHeight(20)

        # Create container widget
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(chart_view)
        layout.addWidget(caption)

        # Store reference to chart_view for click handling
        container.chart_view = chart_view

        return container

    def _build_plot(self, eic) -> ClickableChartView:
        """Create a ClickableChartView with EIC data and guide lines."""
        # Use session data if available, otherwise use default compound data
        compound = read_compound_with_session(eic.compound_name, eic.sample_name)

        # Create chart
        chart = QChart()
        chart.setBackgroundVisible(False)
        chart.setPlotAreaBackgroundVisible(True)
        chart.setPlotAreaBackgroundBrush(QColor(255, 255, 255))
        chart.legend().hide()

        eic_intensity = eic.intensity
        multi_trace = eic_intensity.ndim > 1

        # Compute y_max and scaling (with edge case handling)
        all_intensities = eic_intensity.flatten() if multi_trace else eic_intensity
        unscaled_y_max = float(np.max(all_intensities))
        scale_exp = int(np.floor(np.log10(unscaled_y_max))) if unscaled_y_max > 0 else 0
        scale_factor = 10**scale_exp
        scaled_intensity = eic_intensity / scale_factor
        scaled_y_max = unscaled_y_max / scale_factor if scale_factor != 0 else 0

        # Create reusable font and dark red pen
        font = QFont("Arial", 8)
        dark_red_pen = QPen(dark_red_colour, 2)

        # Create axes
        x_axis = QValueAxis()
        y_axis = QValueAxis()
        chart.addAxis(x_axis, Qt.AlignBottom)
        chart.addAxis(y_axis, Qt.AlignLeft)

        if multi_trace:
            # Pre-create pens for multi-trace to reuse
            pens = [
                QPen(label_colors[i % len(label_colors)], 2)
                for i in range(len(scaled_intensity))
            ]

            for i, intensity in enumerate(scaled_intensity):
                series = QLineSeries()
                for x, y in zip(eic.time, intensity):
                    series.append(x, y)
                series.setPen(pens[i])
                series.setName(f"Label {i}")  # Or use actual mass if you want
                chart.addSeries(series)
                series.attachAxis(x_axis)
                series.attachAxis(y_axis)
        else:
            series = QLineSeries()
            for x, y in zip(eic.time, scaled_intensity):
                series.append(x, y)
            series.setPen(dark_red_pen)
            chart.addSeries(series)
            series.attachAxis(x_axis)
            series.attachAxis(y_axis)

        # Set up axes
        x_axis.setGridLineVisible(False)
        y_axis.setGridLineVisible(False)
        x_axis.setLabelsFont(font)
        y_axis.setLabelsFont(font)

        # Set ranges
        # Use the actual EIC time range (this will reflect the tR window used during extraction)
        rt = compound.retention_time  # Still needed for guide lines
        x_min = float(np.min(eic.time))
        x_max = float(np.max(eic.time))
        x_axis.setRange(x_min, x_max)

        y_axis.setRange(0, scaled_y_max)
        y_axis.setLabelFormat("%.2g")

        # Set tick count (number of major ticks/labels)
        x_axis.setTickCount(5)
        y_axis.setTickCount(5)

        # Add guide lines
        self._add_guide_line(
            chart, x_axis, y_axis, rt, 0, scaled_y_max, QColor(0, 0, 0)
        )  # RT line

        left_line_pos = rt - compound.loffset
        right_line_pos = rt + compound.roffset

        self._add_guide_line(
            chart,
            x_axis,
            y_axis,
            left_line_pos,
            0,
            scaled_y_max,
            steel_blue_colour,
            dashed=True,
        )  # Left offset
        self._add_guide_line(
            chart,
            x_axis,
            y_axis,
            right_line_pos,
            0,
            scaled_y_max,
            steel_blue_colour,
            dashed=True,
        )  # Right offset

        # helper function get superscript num
        def superscript(n):
            sup_map = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
            return str(n).translate(sup_map)

        # Create chart view first to get access to scene
        chart_view = ClickableChartView(chart, eic.sample_name)

        # Add only scale factor in top-left corner if needed
        if scale_exp != 0:
            # Use HTML to make only the superscript larger
            html_text = (
                f'×10<span style="font-size: 14pt;">{superscript(scale_exp)}</span>'
            )
            scale_text = QGraphicsTextItem()
            scale_text.setHtml(html_text)
            scale_text.setFont(QFont("Arial", 10))  # Base font size for ×10
            scale_text.setDefaultTextColor(QColor(80, 80, 80))
            scale_text.setPos(10, 10)  # Top-left corner
            chart.scene().addItem(scale_text)

        # Remove chart title to maximize space
        chart.setTitle("")
        chart.setMargins(QMargins(-13, -10, -13, -15))

        return chart_view

    def _add_guide_line(
        self, chart, x_axis, y_axis, x_pos, y_start, y_end, color, dashed=False
    ):
        """Add a vertical guide line to the chart."""
        line_series = QLineSeries()
        line_series.append(x_pos, y_start)
        line_series.append(x_pos, y_end)
        pen = QPen(color, 1.2)  # pen width 1.2
        if dashed:
            pen.setStyle(Qt.DashLine)
        line_series.setPen(pen)
        chart.addSeries(line_series)
        line_series.attachAxis(x_axis)
        line_series.attachAxis(y_axis)

    def _update_graph_sizes(self) -> None:
        # Invalidate the layout to force recalculation
        self._layout.invalidate()
        self._layout.update()

        # Update the parent widget geometry
        parent = self.parent()
        if parent:
            parent.updateGeometry()
            parent.update()
            parent.repaint()

    def _clear_layout(self) -> None:
        if not self._layout:
            return

        # Clear selections
        self._selected_plots.clear()
        self._current_plots.clear()

        # Remove all widgets and delete them
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Clear any stretch factors from previous layouts
        for i in range(self._layout.columnCount()):
            self._layout.setColumnStretch(i, 0)
        for i in range(self._layout.rowCount()):
            self._layout.setRowStretch(i, 0)
