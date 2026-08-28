import logging
import math
import sys
import warnings
from typing import Dict, List, Optional, Set

import numpy as np
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QEvent, QMargins, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsTextItem,
    QGridLayout,
    QLabel,
    QMenu,
    QRubberBand,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from manic.constants import create_font
from manic.io.compound_reader import read_compound_with_session
from manic.processors.eic_processing import get_eics_for_compound
from manic.processors.display_deconvolution import (
    display_y_max,
    plot_display,
)
from manic.processors.integration import compute_linear_baseline
from manic.utils.timer import measure_time

# Import shared colors
from .channel_labels import channel_legend_label, has_defined_channel
from .colors import dark_red_colour, label_colors, selection_color, steel_blue_colour

logger = logging.getLogger(__name__)

PLOT_Y_AXIS_HEADROOM = 1.05


class ElidingLabel(QLabel):
    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self._full_text = text

    def setText(self, text: str) -> None:
        self._full_text = text
        super().setText(text)

    def fullText(self) -> str:
        return self._full_text

    def resizeEvent(self, event):
        fm = QFontMetrics(self.font())
        elided = fm.elidedText(self._full_text, Qt.ElideRight, self.width())
        super().setText(elided)
        super().resizeEvent(event)


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
            self.m_pressPos = event.pos()
        elif event.button() == Qt.RightButton:
            self.right_clicked.emit(self, event.globalPosition())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to distinguish click from drag"""
        if event.button() == Qt.LeftButton and hasattr(self, "m_pressPos"):
            # Calculate distance moved
            dist = (event.pos() - self.m_pressPos).manhattanLength()
            if dist < QApplication.startDragDistance():
                # It's a click, not a drag
                self.clicked.emit(self)
        super().mouseReleaseEvent(event)

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


_SUPERSCRIPT_MAP = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def _superscript(n: int) -> str:
    return str(n).translate(_SUPERSCRIPT_MAP)


class GraphView(QWidget):
    """
    Re-implements the old grid-of-charts look with pyqtgraph,
    but fetches data via the new processors/io stack.
    """

    # Signal to emit when plot selection changes
    selection_changed = Signal(list)  # List of selected sample names

    def __init__(self, parent=None):
        super().__init__(parent)

        outer_layout = QVBoxLayout(self)
        outer_layout.setSpacing(0)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.channel_legend = QLabel("")
        self.channel_legend.setContentsMargins(4, 2, 4, 2)
        self.channel_legend.setStyleSheet(
            "color: #333; font-size: 11px; background: transparent;"
        )
        self.channel_legend.hide()
        outer_layout.addWidget(self.channel_legend, stretch=0)

        grid_host = QWidget()
        outer_layout.addWidget(grid_host, stretch=1)

        self._layout = QGridLayout(grid_host)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # Track selected plots
        self._selected_plots: Set[ClickableChartView] = set()

        # Store all current plots for easy access
        self._current_plots: List[ClickableChartView] = []

        # Store current compound and samples for integration window updates
        self._current_compound: str = ""
        self._current_samples: List[str] = []

        self.use_corrected = False
        self._prepared_displays = {}

        # Unlabelled identity QC status per sample (drives tile highlighting)
        self._identity_status: Dict[str, str] = {}

        # Shared y-axis scaling across tiles (off = per-tile autoscaling)
        self._shared_y_scale: bool = False
        # (scale_factor, scale_exp, shared_scaled_max); None = per-tile autoscale
        self._scale_override: tuple[float, int, float] | None = None
        self._last_validation_data: Dict[str, bool] | None = None

        # Track max grid dimensions we've used, so we can reliably reset
        # stretch/min-size for any historical rows/cols when the grid shrinks.
        self._max_rows_seen = 0
        self._max_cols_seen = 0

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

        # Rubberband selection state
        self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self._drag_origin = None
        self._is_dragging = False

        # Install event filter on self to handle background drags
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        """
        Event filter to handle rubberband selection across child widgets.
        """
        # Handle Drag Press
        if event.type() == QEvent.MouseButtonPress:
            me = event
            if me.button() == Qt.LeftButton:
                self._drag_origin = self.mapFromGlobal(me.globalPos())
                self._is_dragging = False
            # Always return False to let children process press events (e.g. for click detection)
            return False

        # Handle Drag Move
        elif event.type() == QEvent.MouseMove:
            me = event
            if not (me.buttons() & Qt.LeftButton):
                return False

            if self._handle_drag_move(me):
                return True  # Consume event if we are dragging

        # Handle Drag Release
        elif event.type() == QEvent.MouseButtonRelease:
            me = event
            if me.button() != Qt.LeftButton:
                return False

            if self._handle_drag_release(me):
                return True  # Consume event if we were dragging

        return super().eventFilter(obj, event)

    def _handle_drag_move(self, me):
        """Handle mouse move events for drag selection"""
        if self._drag_origin is None:
            return False

        current_pos = self.mapFromGlobal(me.globalPos())

        if not self._is_dragging:
            # Check drag threshold
            if (
                current_pos - self._drag_origin
            ).manhattanLength() < QApplication.startDragDistance():
                return False

            # Start drag
            self._is_dragging = True
            self._rubber_band.setGeometry(
                QRect(self._drag_origin, current_pos).normalized()
            )
            self._rubber_band.show()
        else:
            # Continue drag
            rect = QRect(self._drag_origin, current_pos).normalized()
            self._rubber_band.setGeometry(rect)
            self._update_selection_from_rubberband(rect)

        return True

    def _handle_drag_release(self, me):
        """Handle mouse release events for drag selection"""
        if not self._is_dragging:
            self._drag_origin = None
            return False

        self._rubber_band.hide()

        # Final update
        final_pos = self.mapFromGlobal(me.globalPos())
        rect = QRect(self._drag_origin, final_pos).normalized()
        self._update_selection_from_rubberband(rect)

        # Emit selection changed signal
        selected_samples = [plot.sample_name for plot in self._selected_plots]
        self.selection_changed.emit(selected_samples)

        self._drag_origin = None
        self._is_dragging = False
        return True

    def _update_selection_from_rubberband(self, band_rect: QRect):
        """Update selection based on rubberband geometry"""
        # Check modifier keys for add/subtract behavior
        modifiers = QApplication.keyboardModifiers()
        is_additive = bool(modifiers & (Qt.ControlModifier | Qt.ShiftModifier))

        for container in self._current_plots:
            # Note: _current_plots contains chart views
            # Get parent container for geometry check
            chart_container = container.parent()
            if not chart_container:
                continue

            # Map the container rect into GraphView coordinates (the grid
            # lives in an inner host widget since the legend strip was added)
            top_left = chart_container.mapTo(self, chart_container.rect().topLeft())
            container_rect = QRect(top_left, chart_container.size())

            if band_rect.intersects(container_rect):
                if not container.is_selected:
                    container.set_selected(True)
                    self._selected_plots.add(container)
            elif not is_additive:
                # Standard behavior: deselect items outside rubberband unless holding Ctrl/Shift
                if container.is_selected:
                    container.set_selected(False)
                    self._selected_plots.discard(container)

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
            self.channel_legend.hide()
            return

        # Store current compound and samples for integration window updates
        self._current_compound = compound_name
        self._current_samples = samples

        with measure_time("get_eics_from_db"):
            eics = get_eics_for_compound(
                compound_name, samples, use_corrected=False
            )

        num = len(eics)
        if num == 0:
            self.channel_legend.hide()
            return

        self._last_validation_data = validation_data

        self._scale_override = None
        prepared_displays = []
        for eic in eics:
            compound = read_compound_with_session(eic.compound_name, eic.sample_name)
            prepared_displays.append(
                plot_display(
                    eic.time,
                    eic.intensity,
                    compound,
                    use_corrected=self.use_corrected,
                )
            )
        self._prepared_displays = {
            (eic.sample_name, eic.compound_name): prepared
            for eic, prepared in zip(eics, prepared_displays)
        }
        if self._shared_y_scale:
            global_max = max(
                (
                    display_y_max(prepared.intensity)
                    for prepared in prepared_displays
                    if np.asarray(prepared.intensity).size
                ),
                default=0.0,
            )
            if global_max > 0:
                scale_exp = int(np.floor(np.log10(global_max)))
                scale_factor = 10**scale_exp
                self._scale_override = (
                    scale_factor,
                    scale_exp,
                    global_max / scale_factor,
                )

        self._update_channel_legend(compound_name, eics)

        cols = math.ceil(math.sqrt(num))
        rows = math.ceil(num / cols)

        self._max_rows_seen = max(self._max_rows_seen, rows)
        self._max_cols_seen = max(self._max_cols_seen, cols)

        # Clear ALL stretch factors/min sizes for any historical rows/cols,
        # then set stretch=1 only for active rows/cols.
        # This is critical when reducing sample count.
        max_rows_to_reset = max(self._max_rows_seen, self._layout.rowCount())
        max_cols_to_reset = max(self._max_cols_seen, self._layout.columnCount())

        for i in range(max_rows_to_reset):
            self._layout.setRowStretch(i, 0)
            self._layout.setRowMinimumHeight(i, 0)
        for i in range(max_cols_to_reset):
            self._layout.setColumnStretch(i, 0)
            self._layout.setColumnMinimumWidth(i, 0)

        # Set stretch factors for active rows/cols
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

        self._prepared_displays.clear()
        if self._identity_status:
            self.set_identity_status(self._identity_status)

    def select_sample(self, sample_name: str) -> bool:
        """Select the plot for ``sample_name``; return False if not shown."""
        for plot in self._current_plots:
            if plot.sample_name == sample_name:
                self.select_only_plot(plot)
                return True
        return False

    def set_identity_status(self, status_by_sample: Optional[Dict[str, str]]):
        """Update unlabelled identity QC highlighting on existing tiles."""
        self._identity_status = dict(status_by_sample or {})
        for plot in self._current_plots:
            container = plot.parent()
            if container is not None:
                self._restyle_container(container)

    def set_shared_y_scale(self, enabled: bool):
        """Toggle one common y-axis scale across all tiles and re-plot."""
        enabled = bool(enabled)
        if enabled == self._shared_y_scale:
            return
        self._shared_y_scale = enabled
        self._replot_current()

    def _replot_current(self) -> None:
        """Re-plot the current compound/samples after a display toggle."""
        if self._current_compound and self._current_samples:
            self.plot_compound(
                self._current_compound,
                self._current_samples,
                self._last_validation_data,
            )

    def _resolve_y_scaling(self, eic_intensity) -> tuple[float, int, float]:
        """Return (scale_factor, scale_exp, scaled_y_max) for one tile.

        With shared y-scale enabled, the override carries the dataset-wide
        scaled max so every tile gets the same axis range; otherwise each tile
        autoscales to its own tallest peak.
        """
        if self._scale_override is not None:
            return self._scale_override
        unscaled_y_max = display_y_max(eic_intensity)
        scale_exp = int(np.floor(np.log10(unscaled_y_max))) if unscaled_y_max > 0 else 0
        scale_factor = 10**scale_exp
        scaled_y_max = unscaled_y_max / scale_factor if scale_factor != 0 else 0
        return scale_factor, scale_exp, scaled_y_max

    def _update_channel_legend(self, compound_name: str, eics) -> None:
        """Show a colour key naming each plotted channel above the grid."""
        multi_trace = bool(
            eics and getattr(eics[0].intensity, "ndim", 1) > 1
        )
        if not multi_trace:
            self.channel_legend.hide()
            return
        try:
            compound = read_compound_with_session(compound_name, None)
            intensity = eics[0].intensity
            n_traces = (
                intensity.shape[0] if getattr(intensity, "ndim", 1) > 1 else 1
            )
            n_names = min(n_traces, len(compound.analysis_channels))
            if n_names == 0:
                self.channel_legend.hide()
                return

            parts = []
            for index in range(n_names):
                color = label_colors[index % len(label_colors)].name()
                label = channel_legend_label(compound, index)
                parts.append(f'<span style="color:{color}">●</span> {label}')
            self.channel_legend.setText(
                f"<b>{compound_name}</b>&nbsp;&nbsp;" + "&nbsp;&nbsp;".join(parts)
            )
            self.channel_legend.show()
        except LookupError:
            self.channel_legend.hide()
        except Exception:
            logger.exception("Failed to update channel colour key")
            self.channel_legend.hide()

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

    def _on_plot_right_clicked(self, clicked_plot: ClickableChartView, global_pos):
        """Handle right-click on plot - show consolidated context menu"""
        try:
            self._show_context_menu(global_pos.toPoint(), clicked_plot)
        except Exception as e:
            logger.error(f"Failed to show context menu: {e}")

    def _show_context_menu(self, global_pos, clicked_plot=None):
        """
        Show context menu.
        Simplified: 'View Detailed' only works if you right-click a specific plot.
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

        # Selection actions
        select_all_action = context_menu.addAction("Select All")
        select_all_action.triggered.connect(self.select_all_plots)

        deselect_all_action = context_menu.addAction("Deselect All")
        deselect_all_action.triggered.connect(self.clear_selection)

        select_only_action = context_menu.addAction("Select Only This Sample")
        if clicked_plot is not None:
            select_only_action.triggered.connect(
                lambda: self.select_only_plot(clicked_plot)
            )
        else:
            select_only_action.setEnabled(False)
            select_only_action.setToolTip("Right-click a specific plot")

        # Plot-specific actions
        context_menu.addSeparator()

        # Add detailed view action
        detailed_action = context_menu.addAction("View Detailed...")

        if clicked_plot is not None:
            # Case: Right-clicked a specific plot.
            # Enable detailed view for this plot regardless of other selections.
            detailed_action.triggered.connect(
                lambda: self._show_detailed_view(
                    clicked_plot.compound_name, clicked_plot.sample_name
                )
            )
        else:
            # Case: Right-clicked background.
            # Disable detailed view entirely.
            detailed_action.setEnabled(False)
            detailed_action.setToolTip("Right-click a specific plot to view details")

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
                compound_name=compound_name,
                sample_name=sample_name,
                parent=self,
                use_corrected=self.use_corrected,
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

    def clear_selection(self):
        """Clear all plot selections"""
        for plot in self._selected_plots:
            plot.set_selected(False)
        self._selected_plots.clear()
        self.selection_changed.emit([])

    def select_only_plot(self, plot: ClickableChartView):
        """Select only the provided plot, deselecting all others."""
        if plot is None:
            return

        if plot not in self._current_plots:
            return

        if (
            len(self._selected_plots) == 1
            and plot in self._selected_plots
            and plot.is_selected
        ):
            return

        for selected_plot in list(self._selected_plots):
            selected_plot.set_selected(False)
        self._selected_plots.clear()

        plot.set_selected(True)
        self._selected_plots.add(plot)
        self.selection_changed.emit([plot.sample_name])

    def clear_all_plots(self, force_destroy: bool = True):
        """Clear all plots from the graph view

        Args:
            force_destroy: If True, completely destroy widgets (slower but prevents artifacts).
                          If False, use pooling (faster but may have visual artifacts).
        """
        self.clear_selection()
        self._current_compound = ""
        self._current_samples = []
        self._identity_status = {}
        self.channel_legend.hide()
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

    def deselect_all_plots(self):
        """Deselect all currently selected plots"""
        self.clear_selection()

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

        # Qt fires contextMenuEvent in addition to the chart view's right-click
        # signal. Previously this path always passed clicked_plot=None, so if it
        # won the race it greyed out "View Detailed" even over a real plot. Hit-
        # test the cursor position so the correct plot is used either way.
        clicked_plot = self._plot_at_global_pos(event.globalPos())
        self._show_context_menu(event.globalPos(), clicked_plot=clicked_plot)

    def _plot_at_global_pos(self, global_pos):
        """Return the plot whose area contains the given global position."""
        for plot in self._current_plots:
            try:
                top_left = plot.mapToGlobal(plot.rect().topLeft())
                if QRect(top_left, plot.size()).contains(global_pos):
                    return plot
            except RuntimeError:
                continue
        return None

    def refresh_plots_with_session_data(
        self, validation_data: Optional[Dict[str, bool]] = None
    ):
        """
        Refresh the current plots using session data where available.

        This method rebuilds all current plots, using session activity data
        where it exists, while preserving the current plot selection state.

        Args:
            validation_data: Optional dictionary mapping sample names to validation status
                           (True=valid, False=invalid) for visual styling.
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
                self.plot_compound(
                    self._current_compound, self._current_samples, validation_data
                )

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
            except Exception as e:
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

        # Create caption label with fixed height + elided text
        caption = ElidingLabel(eic.sample_name)
        caption.setAlignment(Qt.AlignCenter)
        caption.setFont(create_font(8, QFont.Weight.Bold))  # Cross-platform font
        caption.setStyleSheet("color: black; padding: 1px;")
        # Fixed height prevents QGridLayout rows from becoming uneven due to
        # per-row max sizeHint() differences when some captions wrap.
        caption.setWordWrap(False)
        caption.setFixedHeight(18)
        caption.setToolTip(eic.sample_name)
        caption.setText(eic.sample_name)

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

        # Connect click signals for new container
        chart_view.clicked.connect(self._on_plot_clicked)
        chart_view.right_clicked.connect(self._on_plot_right_clicked)

        # Apply validation styling
        self._apply_validation_styling(container, is_valid)

        # Install event filter for rubberband selection on ALL interactive parts
        # Note: QChartView/QGraphicsView events happen on the viewport widget!
        container.installEventFilter(self)
        chart_view.installEventFilter(self)
        chart_view.viewport().installEventFilter(self)
        caption.installEventFilter(self)

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

            # Reset container sizing to clear any cached geometry from previous use
            # This is critical when widgets are moved to a different row/col
            container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            container.setMinimumSize(0, 0)
            chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            chart_view.setMinimumSize(0, 0)
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

            # Ensure event filter is installed on all parts (idempotent)
            # Must include viewport for charts!
            container.removeEventFilter(self)
            container.installEventFilter(self)

            chart_view.removeEventFilter(self)
            chart_view.installEventFilter(self)

            chart_view.viewport().removeEventFilter(self)
            chart_view.viewport().installEventFilter(self)

            container.caption.removeEventFilter(self)
            container.caption.installEventFilter(self)

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
            prepared = self._plot_display_for(eic, compound)

            eic_intensity = eic.intensity

            # Compute y_max and scaling (with edge case handling)
            scale_factor, scale_exp, scaled_y_max = self._resolve_y_scaling(
                prepared.intensity
            )

            # Reuse existing axes
            axes = chart.axes()
            x_axis = axes[0] if axes else None
            y_axis = axes[1] if len(axes) > 1 else None

            # Create new series with updated data
            if x_axis and y_axis:
                self._add_eic_series(
                    chart,
                    x_axis,
                    y_axis,
                    eic.time,
                    eic_intensity,
                    compound,
                    scale_factor,
                    prepared=prepared,
                )

            # Update axis ranges
            if x_axis and y_axis:
                rt = compound.retention_time
                x_min = float(np.min(eic.time))
                x_max = float(np.max(eic.time))
                x_axis.setRange(x_min, x_max)
                y_axis.setRange(0, scaled_y_max * PLOT_Y_AXIS_HEADROOM)

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

                # Add baseline lines if baseline correction is enabled
                self._add_baseline_lines(
                    chart,
                    x_axis,
                    y_axis,
                    eic.time,
                    eic_intensity,
                    compound,
                    scale_factor,
                    prepared=prepared,
                )

            # Add scale factor text if needed
            if scale_exp != 0:
                html_text = (
                    f'×10<span style="font-size: 14pt;">{_superscript(scale_exp)}</span>'
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
        prepared = self._plot_display_for(eic, compound)

        # Create chart
        chart = QChart()
        chart.setBackgroundVisible(False)
        chart.setPlotAreaBackgroundVisible(True)
        chart.setPlotAreaBackgroundBrush(QColor(255, 255, 255))
        chart.legend().hide()

        eic_intensity = eic.intensity

        # Compute y_max and scaling (with edge case handling)
        scale_factor, scale_exp, scaled_y_max = self._resolve_y_scaling(
            prepared.intensity
        )

        font = create_font(8)

        # Create axes
        x_axis = QValueAxis()
        y_axis = QValueAxis()
        chart.addAxis(x_axis, Qt.AlignBottom)
        chart.addAxis(y_axis, Qt.AlignLeft)

        self._add_eic_series(
            chart,
            x_axis,
            y_axis,
            eic.time,
            eic_intensity,
            compound,
            scale_factor,
            prepared=prepared,
        )

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

        y_axis.setRange(0, scaled_y_max * PLOT_Y_AXIS_HEADROOM)
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

        # Add baseline lines if baseline correction is enabled
        self._add_baseline_lines(
            chart,
            x_axis,
            y_axis,
            eic.time,
            eic_intensity,
            compound,
            scale_factor,
            prepared=prepared,
        )

        # Create chart view first to get access to scene
        chart_view = ClickableChartView(chart, eic.sample_name, eic.compound_name)

        # Add only scale factor in top-left corner if needed
        if scale_exp != 0:
            # Use HTML to make only the superscript larger
            html_text = (
                f'×10<span style="font-size: 14pt;">{_superscript(scale_exp)}</span>'
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
        self,
        chart,
        x_axis,
        y_axis,
        x_pos,
        y_start,
        y_end,
        color,
        dashed=False,
        *,
        role: str | None = None,
        width: float = 1.2,
    ):
        """Add a vertical guide line to the chart."""
        line_series = QLineSeries()
        line_series.append(x_pos, y_start)
        line_series.append(x_pos, y_end)
        if role:
            line_series.setProperty("guide_role", role)
        pen = QPen(color, width)
        if dashed:
            pen.setStyle(Qt.DashLine)
        line_series.setPen(pen)
        chart.addSeries(line_series)
        line_series.attachAxis(x_axis)
        line_series.attachAxis(y_axis)
        return line_series

    def _add_baseline_lines(
        self,
        chart,
        x_axis,
        y_axis,
        eic_time: np.ndarray,
        eic_intensity: np.ndarray,
        compound,
        scale_factor: float,
        prepared=None,
    ):
        baseline_flag = getattr(compound, "baseline_correction", 0)
        if not baseline_flag:
            return

        logger.debug(f"Drawing baseline lines for {compound.compound_name}")

        if prepared is None:
            prepared = plot_display(
                eic_time,
                eic_intensity,
                compound,
                use_corrected=self.use_corrected,
            )
        display = prepared.display
        if display is not None and display.bundle.shows_model_overlays(
            independent_channels=getattr(compound, "is_unlabelled_target", False)
        ):
            drew_baseline = False
            draw_matrix = (
                prepared.intensity
                if prepared.intensity.ndim > 1
                else prepared.intensity.reshape(1, -1)
            )
            for channel in display.bundle.channels:
                if channel.result.model is None:
                    continue
                selected_trace = np.asarray(
                    draw_matrix[channel.index], dtype=np.float64
                ).reshape(-1)
                trace_mask = np.asarray(channel.result.selected_mask, dtype=bool).reshape(-1)
                if not np.any(trace_mask):
                    continue
                baseline_result = compute_linear_baseline(
                    eic_time[trace_mask], selected_trace[trace_mask]
                )
                if baseline_result is None:
                    continue
                td_base, baseline_y = baseline_result
                baseline_y_scaled = (
                    baseline_y / scale_factor if scale_factor != 0 else baseline_y
                )
                qcolor = (
                    label_colors[channel.index % len(label_colors)]
                    if eic_intensity.ndim > 1
                    else dark_red_colour
                )
                baseline_series = QLineSeries()
                baseline_series.append(td_base[0], baseline_y_scaled[0])
                baseline_series.append(td_base[-1], baseline_y_scaled[-1])
                baseline_pen = QPen(qcolor, 1.2)
                baseline_pen.setStyle(Qt.DashLine)
                baseline_series.setPen(baseline_pen)
                chart.addSeries(baseline_series)
                baseline_series.attachAxis(x_axis)
                baseline_series.attachAxis(y_axis)
                drew_baseline = True
            if drew_baseline:
                return

        l_boundary = compound.retention_time - compound.loffset
        r_boundary = compound.retention_time + compound.roffset

        mask = (eic_time > l_boundary) & (eic_time < r_boundary)
        if not np.any(mask):
            return

        td_win = eic_time[mask]
        draw_intensity = prepared.intensity
        multi_trace = draw_intensity.ndim > 1

        if multi_trace:
            for i, intensity_trace in enumerate(draw_intensity):
                idata_win = intensity_trace[mask]
                baseline_result = compute_linear_baseline(td_win, idata_win)
                if baseline_result is not None:
                    td_base, baseline_y = baseline_result
                    baseline_y_scaled = (
                        baseline_y / scale_factor if scale_factor != 0 else baseline_y
                    )

                    baseline_series = QLineSeries()
                    baseline_series.append(td_base[0], baseline_y_scaled[0])
                    baseline_series.append(td_base[-1], baseline_y_scaled[-1])

                    baseline_pen = QPen(label_colors[i % len(label_colors)], 1.2)
                    baseline_pen.setStyle(Qt.DashLine)
                    baseline_series.setPen(baseline_pen)
                    chart.addSeries(baseline_series)
                    baseline_series.attachAxis(x_axis)
                    baseline_series.attachAxis(y_axis)
        else:
            idata_win = draw_intensity[mask]
            baseline_result = compute_linear_baseline(td_win, idata_win)
            if baseline_result is not None:
                td_base, baseline_y = baseline_result
                baseline_y_scaled = (
                    baseline_y / scale_factor if scale_factor != 0 else baseline_y
                )

                baseline_series = QLineSeries()
                baseline_series.append(td_base[0], baseline_y_scaled[0])
                baseline_series.append(td_base[-1], baseline_y_scaled[-1])

                baseline_pen = QPen(dark_red_colour, 1.2)
                baseline_pen.setStyle(Qt.DashLine)
                baseline_series.setPen(baseline_pen)
                chart.addSeries(baseline_series)
                baseline_series.attachAxis(x_axis)
                baseline_series.attachAxis(y_axis)

    def _add_model_component_series(
        self,
        chart,
        x_axis,
        y_axis,
        model,
        component_index: int,
        *,
        multi_trace: bool,
        scale_factor: float,
        selected: bool,
        color_index: int | None = None,
    ):
        """Draw one fitted component over the integration or fit window."""
        t_left, t_right = (
            (model.integration_left, model.integration_right)
            if selected
            else (model.fit_left, model.fit_right)
        )
        if not (t_right > t_left):
            return

        grid = np.linspace(t_left, t_right, 256)
        values = model.evaluate(grid, component_index)
        matrix = values if values.ndim > 1 else values.reshape(1, -1)
        for i, row in enumerate(matrix):
            series_index = color_index if color_index is not None else i
            qcolor = (
                label_colors[series_index % len(label_colors)]
                if multi_trace
                else dark_red_colour
            )
            if selected:
                pen = QPen(QColor(qcolor), 2.2)
            else:
                overlay_color = QColor(qcolor)
                overlay_color.setAlpha(95)
                pen = QPen(overlay_color, 1.2)
                pen.setStyle(Qt.DotLine)

            scaled = row / scale_factor if scale_factor != 0 else row
            finite = np.isfinite(scaled)
            if not np.any(finite):
                continue
            series = QLineSeries()
            series.appendNp(
                np.ascontiguousarray(grid[finite], dtype=np.float64),
                np.ascontiguousarray(scaled[finite], dtype=np.float64),
            )
            series.setPen(pen)
            chart.addSeries(series)
            series.attachAxis(x_axis)
            series.attachAxis(y_axis)

    def _plot_display_for(self, eic, compound):
        prepared = self._prepared_displays.pop(
            (eic.sample_name, eic.compound_name), None
        )
        if prepared is not None:
            return prepared
        return plot_display(
            eic.time,
            eic.intensity,
            compound,
            use_corrected=self.use_corrected,
        )

    def _add_eic_series(
        self,
        chart,
        x_axis,
        y_axis,
        eic_time: np.ndarray,
        eic_intensity: np.ndarray,
        compound,
        scale_factor: float,
        prepared=None,
    ):
        if prepared is None:
            prepared = plot_display(
                eic_time,
                eic_intensity,
                compound,
                use_corrected=self.use_corrected,
            )
        display = prepared.display
        bundle = None if display is None else display.bundle
        draw_intensity = prepared.intensity

        if bundle is None or not bundle.shows_model_overlays(
            independent_channels=getattr(compound, "is_unlabelled_target", False)
        ):
            self._add_trace_series(
                chart,
                x_axis,
                y_axis,
                eic_time,
                draw_intensity,
                scale_factor,
                selected=False,
                raw_context=False,
                compound=compound,
            )
            return

        if not prepared.includes_raw_underlay:
            self._add_trace_series(
                chart,
                x_axis,
                y_axis,
                eic_time,
                draw_intensity,
                scale_factor,
                selected=True,
                raw_context=False,
                compound=compound,
            )
            return

        multi_trace = eic_intensity.ndim > 1
        self._add_trace_series(
            chart,
            x_axis,
            y_axis,
            eic_time,
            eic_intensity,
            scale_factor,
            selected=False,
            raw_context=True,
            compound=compound,
        )
        unfitted_indices: list[int] = []
        for channel in bundle.channels:
            model = channel.result.model
            if model is None:
                unfitted_indices.append(channel.index)
                continue
            self._add_model_component_series(
                chart,
                x_axis,
                y_axis,
                model,
                model.selected_index,
                multi_trace=multi_trace,
                scale_factor=scale_factor,
                selected=True,
                color_index=channel.index,
            )
            for component_index in range(model.n_components):
                if component_index == model.selected_index:
                    continue
                self._add_model_component_series(
                    chart,
                    x_axis,
                    y_axis,
                    model,
                    component_index,
                    multi_trace=multi_trace,
                    scale_factor=scale_factor,
                    selected=False,
                    color_index=channel.index,
                )
        if unfitted_indices:
            self._add_trace_series(
                chart,
                x_axis,
                y_axis,
                eic_time,
                eic_intensity,
                scale_factor,
                selected=True,
                raw_context=False,
                compound=compound,
                channel_indices=tuple(unfitted_indices),
            )

    def _add_trace_series(
        self,
        chart,
        x_axis,
        y_axis,
        eic_time: np.ndarray,
        eic_intensity: np.ndarray,
        scale_factor: float,
        *,
        selected: bool,
        raw_context: bool,
        selected_mask: np.ndarray | None = None,
        compound=None,
        channel_indices: tuple[int, ...] | None = None,
    ):
        matrix = eic_intensity if eic_intensity.ndim > 1 else eic_intensity.reshape(1, -1)
        mask_matrix = None
        if selected_mask is not None:
            mask_matrix = (
                selected_mask
                if selected_mask.ndim > 1
                else selected_mask.reshape(1, -1)
            )

        multi_trace = eic_intensity.ndim > 1
        for i, trace in enumerate(matrix):
            if channel_indices is not None and i not in channel_indices:
                continue
            qcolor = label_colors[i % len(label_colors)] if multi_trace else dark_red_colour
            pen_color = QColor(qcolor)
            if raw_context:
                pen_color.setAlpha(75)
                width = 1.0
            else:
                width = 2.2 if selected else 2.0

            pen = QPen(pen_color, width)
            series = QLineSeries()
            scaled_trace = trace / scale_factor if scale_factor != 0 else trace
            keep = np.isfinite(scaled_trace)
            if mask_matrix is not None:
                keep &= np.asarray(mask_matrix[i, :], dtype=bool)
            if np.any(keep):
                xs = np.ascontiguousarray(eic_time[keep], dtype=np.float64)
                ys = np.ascontiguousarray(scaled_trace[keep], dtype=np.float64)
                series.appendNp(
                    np.ascontiguousarray(xs, dtype=np.float64),
                    np.ascontiguousarray(ys, dtype=np.float64),
                )
            series.setPen(pen)
            if (
                not raw_context
                and multi_trace
                and has_defined_channel(compound, i)
            ):
                series.setName(channel_legend_label(compound, i))
            chart.addSeries(series)
            series.attachAxis(x_axis)
            series.attachAxis(y_axis)

    def _update_graph_sizes(self) -> None:
        # Invalidate first, then activate to force recalculation
        self._layout.invalidate()
        self._layout.activate()
        self._layout.update()

        # Update the parent widget geometry
        parent = self.parent()
        if parent:
            parent.updateGeometry()
            parent.update()

    def _apply_validation_styling(self, container: QWidget, is_valid: bool):
        """Record peak-height validation state and restyle the tile."""
        container.is_valid_peak = is_valid
        self._restyle_container(container)

    def _restyle_container(self, container: QWidget):
        is_valid = getattr(container, "is_valid_peak", True)
        sample_name = getattr(container.chart_view, "sample_name", "")
        status = self._identity_status.get(sample_name)

        if status == "not_detected":
            container.setStyleSheet("""
                QWidget {
                    background-color: rgba(236, 239, 241, 130);
                    border: 1px solid #9ca3af;
                    border-radius: 4px;
                }
            """)
        elif not is_valid:
            container.setStyleSheet("""
                QWidget {
                    background-color: rgba(255, 200, 200, 120);
                }
            """)
        else:
            container.setStyleSheet("")

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

            # Reset tracked grid size on full teardown
            self._max_rows_seen = 0
            self._max_cols_seen = 0
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
                        # Ensure pooled containers are parented to the view itself
                        # so they aren't destroyed when the layout is deleted
                        widget.setParent(self)
                    else:
                        # Safe to delete non-pooled widgets
                        widget.deleteLater()

        # purge persistent row/col tracking by resetting stretches
        # Recreating the layout causes a crash because the old layout
        # remains associated with the widget in ways that deleteLater()
        # doesn't handle immediately during the plot cycle.
        max_rows_to_reset = max(self._max_rows_seen, self._layout.rowCount())
        max_cols_to_reset = max(self._max_cols_seen, self._layout.columnCount())

        for i in range(max_cols_to_reset):
            self._layout.setColumnStretch(i, 0)
            self._layout.setColumnMinimumWidth(i, 0)
        for i in range(max_rows_to_reset):
            self._layout.setRowStretch(i, 0)
            self._layout.setRowMinimumHeight(i, 0)

        # Force repaint/update. Prefer update() over repaint() to avoid synchronous paints.
        self.updateGeometry()
        self.update()
