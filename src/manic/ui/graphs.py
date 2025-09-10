import logging
import math
import sys
import warnings
from typing import Dict, List, Set

import numpy as np
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QMargins, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsTextItem,
    QGridLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from manic.constants import create_font
from manic.io.compound_reader import read_compound_with_session
from manic.processors.eic_processing import get_eics_for_compound
from manic.utils.timer import measure_time

logger = logging.getLogger(__name__)

# Import shared colors
from .colors import dark_red_colour, label_colors, selection_color, steel_blue_colour


class ClickableChartView(QChartView):
    """Custom QChartView that can be selected"""

    clicked = Signal(object)  # Signal to emit when clicked
    right_clicked = Signal(
        object, object
    )  # Signal to emit when right-clicked (view, position)

    def __init__(self, chart, sample_name, compound_name="", parent=None):
        super().__init__(chart, parent)
        self.sample_name = sample_name
        self.compound_name = compound_name
        self.is_selected = False
        self.setRenderHint(QPainter.Antialiasing)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def mousePressEvent(self, event):
        """Handle mouse clicks"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self)
        elif event.button() == Qt.RightButton:
            self.right_clicked.emit(self, event.globalPosition())
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

        # Track whether to use corrected data
        self.use_corrected = True  # Default to using corrected data

        # Chart object pooling for performance optimization
        # Maintains reusable chart containers to avoid expensive creation/destruction cycles
        self._container_pool: List[
            QWidget
        ] = []  # Complete plot containers with captions
        self._available_containers: List[QWidget] = []

        # throttle resize events – avoids constant redraw while user resizes
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._update_graph_sizes)

    def set_use_corrected(self, use_corrected: bool):
        """Set whether to use natural abundance corrected data."""
        self.use_corrected = use_corrected
        logger.info(
            f"GraphView set to use {'corrected' if use_corrected else 'uncorrected'} data"
        )

    # public function
    def plot_compound(
        self,
        compound_name: str,
        samples: List[str],
        validation_data: Dict[str, bool] = None,
    ) -> None:
        """
        Build one mini-plot per active sample for the selected *compound*.
        """

        # Begin compound plotting - logging removed to reduce noise
        self._clear_layout()
        if not samples:
            return

        # Store current compound and samples for integration window updates
        self._current_compound = compound_name
        self._current_samples = samples

        # time db retreival for debugging
        with measure_time("get_eics_from_db"):
            eics = get_eics_for_compound(
                compound_name, samples, use_corrected=self.use_corrected
            )  # new pipeline

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
            # Build all plots with captions using chart pooling for performance
            # Pass validation data to determine background color
            plot_containers = [
                self._build_plot_with_caption(
                    eic,
                    is_valid=validation_data.get(eic.sample_name, True)
                    if validation_data
                    else True,
                )
                for eic in eics
            ]

            # Extract chart views for click handling
            self._current_plots = [
                container.chart_view for container in plot_containers
            ]

            # Connect click signals for newly created containers only
            # (Reused containers have signals connected in _update_container_data)
            for container in plot_containers:
                if container not in self._container_pool:
                    # This is a newly created container, connect signals
                    container.chart_view.clicked.connect(self._on_plot_clicked)
                    container.chart_view.right_clicked.connect(
                        self._on_plot_right_clicked
                    )

            # Add to layout efficiently with atomic visibility handling
            # Hide all containers first, add to layout, then show all at once
            # This prevents visual flashing and is more efficient than processEvents()
            for i, container in enumerate(plot_containers):
                row = i // cols
                col = i % cols
                container.hide()  # Ensure hidden before adding to layout
                self._layout.addWidget(container, row, col)

            # Show all containers at once for smooth appearance
            for container in plot_containers:
                container.show()

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

    def _on_plot_right_clicked(self, clicked_plot: ClickableChartView, global_pos):
        """Handle right-click on plot - show consolidated context menu"""
        try:
            self._show_context_menu(global_pos.toPoint(), clicked_plot)
        except Exception as e:
            logger.error(f"Failed to show context menu: {e}")

    def _show_context_menu(self, global_pos, clicked_plot=None):
        """
        Show consolidated context menu with appropriate options.

        The context menu automatically dismisses when clicking outside or when
        actions are triggered, providing a clean user experience.
        """
        # Close any existing context menu first
        if hasattr(self, "_active_context_menu") and self._active_context_menu:
            self._active_context_menu.close()

        context_menu = QMenu(self)
        self._active_context_menu = context_menu  # Store reference for cleanup

        # Set menu style to ensure black text on white background
        context_menu.setStyleSheet("""
            QMenu {
                background-color: white;
                color: black;
                border: 1px solid #d0d0d0;
            }
            QMenu::item {
                background-color: white;
                color: black;
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #e0e0e0;
                color: black;
            }
            QMenu::item:disabled {
                color: #a0a0a0;
            }
        """)

        # Ensure menu disappears when clicking outside or after actions
        context_menu.setAttribute(Qt.WA_DeleteOnClose)
        context_menu.aboutToHide.connect(self._on_context_menu_closed)

        # Add select all/deselect actions (always available)
        select_all_action = context_menu.addAction("Select All")
        select_all_action.triggered.connect(self.select_all_plots)

        deselect_all_action = context_menu.addAction("Deselect All")
        deselect_all_action.triggered.connect(self.clear_selection)

        # Add separator before detailed view option
        context_menu.addSeparator()

        # Add detailed view action (only if single plot clicked and none or one selected)
        if clicked_plot is not None and len(self._selected_plots) <= 1:
            detailed_action = context_menu.addAction("View Detailed...")
            detailed_action.triggered.connect(
                lambda: self._show_detailed_view(
                    clicked_plot.compound_name, clicked_plot.sample_name
                )
            )
        elif clicked_plot is None and len(self._selected_plots) == 1:
            # If right-clicked on empty space but exactly one plot is selected
            selected_plot = next(iter(self._selected_plots))
            detailed_action = context_menu.addAction("View Detailed...")
            detailed_action.triggered.connect(
                lambda: self._show_detailed_view(
                    selected_plot.compound_name, selected_plot.sample_name
                )
            )
        else:
            # Add disabled detailed view action to show it's not available
            detailed_action = context_menu.addAction("View Detailed...")
            detailed_action.setEnabled(False)
            detailed_action.setToolTip("Available only with single plot selection")

        # Show menu at position - use popup() instead of exec() for better behavior
        context_menu.popup(global_pos)

    def _on_context_menu_closed(self):
        """Handle context menu cleanup when it closes."""
        self._active_context_menu = None

    def _show_detailed_view(self, compound_name: str, sample_name: str):
        """Show detailed plot dialog for compound-sample combination"""
        try:
            from manic.ui.detailed_plot_dialog import DetailedPlotDialog

            dialog = DetailedPlotDialog(
                compound_name=compound_name, sample_name=sample_name, parent=self
            )
            dialog.exec()

        except Exception as e:
            logger.error(
                f"Failed to show detailed view for {compound_name}/{sample_name}: {e}"
            )
            # Show error message to user
            error_msg = QLabel(f"Error opening detailed view: {str(e)}")
            error_msg.setStyleSheet("color: red; padding: 10px;")
            error_msg.show()

    def get_selected_samples(self) -> List[str]:
        """Get list of currently selected sample names"""
        return [plot.sample_name for plot in self._selected_plots]

    def get_current_compound(self) -> str:
        """Get the currently displayed compound"""
        return self._current_compound

    def get_current_samples(self) -> List[str]:
        """Get the list of all currently displayed samples"""
        return self._current_samples.copy()

    def set_use_corrected(self, use_corrected: bool):
        """Set whether to use corrected data when reading EICs"""
        self.use_corrected = use_corrected
        logger.info(
            f"GraphView set to use {'corrected' if use_corrected else 'uncorrected'} data"
        )

    def clear_selection(self):
        """Clear all plot selections"""
        for plot in self._selected_plots:
            plot.set_selected(False)
        self._selected_plots.clear()
        self.selection_changed.emit([])

    def clear_all_plots(self, force_destroy: bool = True):
        """Clear all plots from the graph view
        
        Args:
            force_destroy: If True, completely destroy widgets (slower but prevents artifacts).
                          If False, use pooling (faster but may have visual artifacts).
        """
        self.clear_selection()
        self._current_compound = ""
        self._current_samples = []
        # Note: _current_plots will be cleared in _clear_layout
        self._clear_layout(force_destroy=force_destroy)
        
        # Force immediate update to prevent visual artifacts
        self.update()
        self.repaint()
        QApplication.processEvents()

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

        # Use consolidated context menu (no specific plot clicked)
        self._show_context_menu(event.globalPos(), clicked_plot=None)

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

    def _get_container_from_pool(self, eic, is_valid: bool = True) -> QWidget:
        """
        Retrieve a complete plot container from the pool or create a new one.

        Container pooling improves performance by reusing complete plot widgets
        (including chart view and caption) rather than creating new ones. This
        maintains proper Qt parent-child relationships and avoids deletion issues.
        Updates are applied before showing to prevent visual flashing.

        Args:
            eic: EIC object containing the data to display

        Returns:
            QWidget container with chart_view attribute configured with EIC data
        """
        if self._available_containers:
            # Reuse existing container from pool
            container = self._available_containers.pop()
            # Update data atomically (container update handles visibility)
            self._update_container_data(container, eic, is_valid)
            # Container will be shown by _update_container_data after update is complete
            return container
        else:
            # Pool exhausted, create new container and add to pool tracking
            container = self._create_plot_container(eic, is_valid)
            self._container_pool.append(container)
            return container

    def _create_plot_container(self, eic, is_valid: bool = True) -> QWidget:
        """
        Create a new plot container with chart view and caption.

        This method creates the complete widget structure needed for a plot,
        including the chart view and sample name caption, maintaining the
        same structure as the original _build_plot_with_caption method.

        Args:
            eic: EIC object containing the data to display

        Returns:
            QWidget container with chart_view attribute
        """
        # Create the plot
        chart_view = self._build_plot(eic)

        # Create caption label with adaptive sizing for large datasets
        caption = QLabel(eic.sample_name)
        caption.setAlignment(Qt.AlignCenter)
        caption.setFont(create_font(8, QFont.Weight.Bold))  # Cross-platform font
        caption.setStyleSheet("color: black; padding: 1px;")
        caption.setWordWrap(True)  # Allow text wrapping for long sample names
        caption.setMinimumHeight(15)  # Ensure minimum visibility
        caption.setMaximumHeight(25)  # Increase max height for better visibility

        # Create container widget
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(chart_view)
        layout.addWidget(caption)

        # Store references for easy access
        container.chart_view = chart_view
        container.caption = caption

        # Apply validation styling
        self._apply_validation_styling(container, is_valid)

        return container

    def _update_container_data(self, container: QWidget, eic, is_valid: bool = True):
        """
        Update an existing container with new EIC data.

        This method efficiently reuses container widgets by updating both
        the chart view data and the caption text without recreating the
        widget structure. Updates are performed atomically to prevent visual flashing.

        Args:
            container: Existing container widget to update
            eic: New EIC data to display
        """
        # Keep container hidden during update to prevent visual flashing
        container.hide()

        # Immediately clear any stale content to prevent flashing
        chart_view = container.chart_view
        chart_view.chart().removeAllSeries()  # Clear chart data
        container.caption.setText("")  # Clear caption text

        try:
            # Ensure the chart view is properly reset and not selected
            chart_view.set_selected(False)

            # Disconnect existing signals to avoid multiple connections
            # Suppress RuntimeWarnings about failed disconnections
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=RuntimeWarning, message="Failed to disconnect.*"
                )
                try:
                    chart_view.clicked.disconnect(self._on_plot_clicked)
                    chart_view.right_clicked.disconnect(self._on_plot_right_clicked)
                except Exception:
                    pass  # Signals weren't connected

            # Mark that we'll connect signals (for future disconnections)
            chart_view._signal_connected = True

            # Update the chart with new data (chart will handle its own visibility)
            self._update_chart_data(chart_view, eic)

            # Update the caption
            container.caption.setText(eic.sample_name)

            # Apply validation styling
            self._apply_validation_styling(container, is_valid)

            # Reconnect signals for this specific usage
            chart_view.clicked.connect(self._on_plot_clicked)
            chart_view.right_clicked.connect(self._on_plot_right_clicked)

        finally:
            # Container visibility is managed at the layout level for smoother updates
            pass

    def _update_chart_data(self, chart_view: ClickableChartView, eic):
        """
        Update an existing chart with new EIC data without recreating Qt objects.

        This method efficiently reuses chart components by clearing existing series
        and repopulating with new data, preserving axes and other chart infrastructure.
        Updates are performed atomically to prevent visual flashing during updates.

        Args:
            chart_view: Existing ClickableChartView to update
            eic: New EIC data to display
        """
        chart = chart_view.chart()

        # Chart visibility is handled at the container level, no need to manage it here
        try:
            # Update chart view metadata
            chart_view.sample_name = eic.sample_name
            chart_view.compound_name = eic.compound_name
            chart_view.set_selected(False)  # Reset selection state

            # Clear existing series but preserve chart structure
            chart.removeAllSeries()

            # Clear any existing text items (scale factors) from previous data
            for item in chart.scene().items():
                if isinstance(item, QGraphicsTextItem):
                    chart.scene().removeItem(item)

            # Use session data if available, otherwise use default compound data
            compound = read_compound_with_session(eic.compound_name, eic.sample_name)

            eic_intensity = eic.intensity
            multi_trace = eic_intensity.ndim > 1

            # Compute y_max and scaling (with edge case handling)
            all_intensities = eic_intensity.flatten() if multi_trace else eic_intensity
            unscaled_y_max = float(np.max(all_intensities))
            scale_exp = (
                int(np.floor(np.log10(unscaled_y_max))) if unscaled_y_max > 0 else 0
            )
            scale_factor = 10**scale_exp
            scaled_intensity = eic_intensity / scale_factor
            scaled_y_max = unscaled_y_max / scale_factor if scale_factor != 0 else 0

            # Reuse existing axes
            axes = chart.axes()
            x_axis = axes[0] if axes else None
            y_axis = axes[1] if len(axes) > 1 else None

            # Create new series with updated data
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
                    series.setName(f"Label {i}")
                    chart.addSeries(series)
                    if x_axis and y_axis:
                        series.attachAxis(x_axis)
                        series.attachAxis(y_axis)
            else:
                series = QLineSeries()
                dark_red_pen = QPen(dark_red_colour, 2)
                for x, y in zip(eic.time, scaled_intensity):
                    series.append(x, y)
                series.setPen(dark_red_pen)
                chart.addSeries(series)
                if x_axis and y_axis:
                    series.attachAxis(x_axis)
                    series.attachAxis(y_axis)

            # Update axis ranges
            if x_axis and y_axis:
                rt = compound.retention_time
                x_min = float(np.min(eic.time))
                x_max = float(np.max(eic.time))
                x_axis.setRange(x_min, x_max)
                y_axis.setRange(0, scaled_y_max)

                # Re-add guide lines
                self._add_guide_line(
                    chart, x_axis, y_axis, rt, 0, scaled_y_max, QColor(0, 0, 0)
                )

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
                )
                self._add_guide_line(
                    chart,
                    x_axis,
                    y_axis,
                    right_line_pos,
                    0,
                    scaled_y_max,
                    steel_blue_colour,
                    dashed=True,
                )

            # Add scale factor text if needed
            if scale_exp != 0:

                def superscript(n):
                    sup_map = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
                    return str(n).translate(sup_map)

                html_text = (
                    f'×10<span style="font-size: 14pt;">{superscript(scale_exp)}</span>'
                )
                scale_text = QGraphicsTextItem()
                scale_text.setHtml(html_text)
                scale_text.setFont(create_font(10))  # Cross-platform font
                scale_text.setDefaultTextColor(QColor(80, 80, 80))
                scale_text.setPos(10, 10)
                chart.scene().addItem(scale_text)

        except Exception as e:
            # Log any chart update errors but don't let them break the container update
            logger.error(f"Error updating chart data: {e}")
            # Container will still be shown, just with potentially stale data

    def _return_containers_to_pool(self):
        """
        Return all current plot containers to the available pool for reuse.

        This method efficiently recycles complete plot containers by clearing their
        selection state and properly cleaning up signals. Containers retain their
        Qt structure for fast reuse in subsequent plot operations.
        """
        for plot in self._current_plots:
            # Clear selection state
            plot.set_selected(False)
            
            # Clear the chart data completely
            plot.chart().removeAllSeries()
            plot.chart().setTitle("")
            
            # Force the chart to update
            plot.update()

            # Find the parent container for this chart view
            container = plot.parent()
            while container and not hasattr(container, "chart_view"):
                container = container.parent()

            if container and container in self._container_pool:
                # Clear the caption
                if hasattr(container, "caption"):
                    container.caption.setText("")
                    container.caption.update()
                
                # Disconnect signals to prevent stale connections
                if hasattr(plot, "_signal_connected"):
                    try:
                        plot.clicked.disconnect(self._on_plot_clicked)
                        plot.right_clicked.disconnect(self._on_plot_right_clicked)
                        plot._signal_connected = False  # Mark as disconnected
                    except (TypeError, RuntimeError):
                        pass  # Signals weren't connected to these specific slots

                container.hide()  # Hide but don't delete
                self._available_containers.append(container)

        self._current_plots.clear()
        self._selected_plots.clear()

    #  internal functions
    def _build_plot_with_caption(self, eic, is_valid: bool = True) -> QWidget:
        """Create a widget containing a plot with sample name caption below."""
        # Create the plot container using pooling for performance
        return self._get_container_from_pool(eic, is_valid)

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
        font = create_font(8)  # Cross-platform font
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
        chart_view = ClickableChartView(chart, eic.sample_name, eic.compound_name)

        # Add only scale factor in top-left corner if needed
        if scale_exp != 0:
            # Use HTML to make only the superscript larger
            html_text = (
                f'×10<span style="font-size: 14pt;">{superscript(scale_exp)}</span>'
            )
            scale_text = QGraphicsTextItem()
            scale_text.setHtml(html_text)
            scale_text.setFont(create_font(10))  # Cross-platform base font for ×10
            scale_text.setDefaultTextColor(QColor(80, 80, 80))
            scale_text.setPos(10, 10)  # Top-left corner
            chart.scene().addItem(scale_text)

        # Remove chart title to maximize space
        chart.setTitle("")

        # Platform-specific margins to prevent text cutoff on Windows
        if sys.platform == "win32":
            # Windows needs more bottom margin due to font rendering differences
            chart.setMargins(QMargins(-13, -10, -13, -5))
        else:
            # macOS and Linux can use tighter margins
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

    def _apply_validation_styling(self, container: QWidget, is_valid: bool):
        """
        Apply visual styling to indicate peak height validation status.

        Args:
            container: The plot container widget
            is_valid: True if peak meets minimum height threshold, False otherwise
        """
        if is_valid:
            # Valid peak - use default styling
            container.setStyleSheet("")
        else:
            # Invalid peak - apply light red background
            container.setStyleSheet("""
                QWidget {
                    background-color: rgba(255, 200, 200, 120);
                }
            """)

    def _clear_layout(self, force_destroy: bool = False) -> None:
        if not self._layout:
            return

        if force_destroy:
            # Complete destruction mode - used for deletion to prevent artifacts
            # First, clear the current plots tracking
            self._current_plots.clear()
            self._selected_plots.clear()
            
            # Remove and delete ALL widgets from layout completely
            while self._layout.count():
                item = self._layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    # Completely delete the widget to ensure no visual artifacts
                    widget.setParent(None)
                    widget.deleteLater()
            
            # Clear the container pool completely - we'll rebuild it as needed
            for container in self._container_pool:
                if container and container.parent():
                    container.setParent(None)
                container.deleteLater()
            
            self._container_pool.clear()
            self._available_containers.clear()
        else:
            # Normal clearing with pooling - fast for regular operations
            # Return containers to pool for reuse
            self._return_containers_to_pool()
            
            # Remove all widgets from layout
            while self._layout.count():
                item = self._layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    # Check if widget is a pooled container before deletion
                    if widget in self._container_pool:
                        # Don't delete pooled containers, they're already handled
                        pass
                    else:
                        # Safe to delete non-pooled widgets
                        widget.deleteLater()

        # Clear any stretch factors from previous layouts
        for i in range(self._layout.columnCount()):
            self._layout.setColumnStretch(i, 0)
        for i in range(self._layout.rowCount()):
            self._layout.setRowStretch(i, 0)
            
        # Force complete repaint of the widget
        self.update()
        self.repaint()
