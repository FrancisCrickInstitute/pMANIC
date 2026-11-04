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
from PySide6.QtCore import QMargins, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QCursor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsRectItem,
    QLabel,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from manic.io.compound_reader import read_compound_with_session
from manic.io.eic_reader import EIC
from manic.processors.display_deconvolution import integrated_display_areas

from . import theme
from .chart_header import ChartHeader
from .chart_style import style_axis, style_chart
from .colors import label_colors
from .sidebar_widgets import (
    SUMMARY_CHART_HEIGHT,
    fit_sample_names,
    names_hint,
    summary_chart_height,
)
from .theme import color


def isotopologue_key_html(count: int) -> str:
    """'■ M+0  ■ M+1 ...' in the series colours; wraps between entries only."""
    return "&nbsp;&nbsp; ".join(
        f'<span style="color:{label_colors[i % len(label_colors)].name()}">■</span>'
        f"&nbsp;M+{i}"
        for i in range(count)
    )

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

        self.use_corrected = False

        # Create chart and chart view
        self.chart = QChart()
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_view.setFrameShape(QFrame.NoFrame)
        self.chart_view.setStyleSheet("background: transparent; border: none;")

        # Enable double-click on chart view
        self.chart_view.mouseDoubleClickEvent = self._chart_view_double_click

        style_chart(self.chart, QMargins(8, 0, 8, 0))

        self.header = ChartHeader("Label incorporation")
        self.header.expand_button.clicked.connect(self._show_popup_chart)

        self.key = QLabel()
        self.key.setObjectName("isotopologueKey")
        self.key.setWordWrap(True)
        self.key.setTextFormat(Qt.RichText)
        self.key.setContentsMargins(8, 2, 8, 0)
        theme.style(self.key, "color: @text_secondary; font-size: 11px;")
        self.key.hide()
        theme.notifier.changed.connect(self._refresh_key)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.key)
        layout.addWidget(self.chart_view)
        self.names_hint = names_hint()
        layout.addWidget(self.names_hint)

        # The grid's selected samples, marked beside their bars.
        self._highlighted: set[str] = set()
        self._marks: list[QGraphicsRectItem] = []
        self.chart.plotAreaChanged.connect(self._on_plot_area_changed)
        theme.notifier.changed.connect(self._paint_highlight)

        # Responsive height for toolbar integration
        self.setMinimumHeight(SUMMARY_CHART_HEIGHT[0])
        self.setMaximumHeight(SUMMARY_CHART_HEIGHT[1])
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
        # A reversed copy: the caller still holds this list and the abundances
        # shared with the abundance chart follow its original order.
        ordered_eics = ordered_eics[::-1]
        ordered_ratios = np.flipud(ordered_ratios)  # Flip array upside down

        # Store current data for popup
        self._current_ratios = ordered_ratios
        self._current_sample_names = [eic.sample_name for eic in ordered_eics]

        # Update chart
        self._update_chart(ordered_ratios, self._current_sample_names)

    def _calculate_integrated_data(
        self, eics: List[EIC], compound_name: str
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        ratios = []
        total_abundances = []
        multi_trace_samples = []

        for eic in eics:
            compound = read_compound_with_session(compound_name, eic.sample_name)
            isotope_areas = integrated_display_areas(
                eic.time,
                eic.intensity,
                compound,
                use_corrected=self.use_corrected,
            )
            total_area = sum(isotope_areas)
            total_abundances.append(total_area)

            if eic.intensity.ndim == 1:
                ratios.append(np.array([1.0]))
            else:
                multi_trace_samples.append(eic.sample_name)
                if total_area > 0:
                    ratios.append(np.array(isotope_areas) / total_area)
                else:
                    ratios.append(np.zeros(len(isotope_areas)))

        if multi_trace_samples:
            logger.info(
                f"Isotopologue integration for {compound_name}: "
                f"{len(multi_trace_samples)} samples processed "
                f"(preview={'on' if self.use_corrected else 'off'})"
            )

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
        math.ceil(num / cols)

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
            bar_set.setBorderColor(color("surface"))

            # Add ratio values for this isotopologue across all samples
            for j in range(n_samples):
                bar_set.append(ratios[j, i])
            bar_set.hovered.connect(self._on_bar_hovered)

            bar_sets.append(bar_set)
            bar_series.append(bar_set)

        # Add series to chart
        self.chart.addSeries(bar_series)
        # Header, axis and key take about 80 px around the bars.
        self.setMinimumHeight(summary_chart_height(len(sample_names), 80))

        # Setup axes
        self._setup_axes(sample_names)

        # Attach series to axes
        bar_series.attachAxis(self.chart.axes(Qt.Horizontal)[0])
        bar_series.attachAxis(self.chart.axes(Qt.Vertical)[0])
        self._refresh_key()
        self._on_plot_area_changed()

    def set_highlighted(self, sample_names) -> None:
        """Mark the bars of the samples selected in the grid."""
        self._highlighted = set(sample_names)
        self._paint_highlight()

    def highlighted_bars(self) -> list[str]:
        return [mark.data(0) for mark in self._marks if mark.data(0)]

    def _on_plot_area_changed(self, *_args) -> None:
        count = len(self._current_sample_names) if self._has_data() else 0
        fit_sample_names(self.chart, count, self.names_hint)
        self._paint_highlight()

    def _paint_highlight(self, *_args) -> None:
        # An accent outline would vanish against the blue M+0 segment, so the other
        # rows fade and an accent tick sits beside each selected bar.
        for mark in self._marks:
            self.chart.scene().removeItem(mark)
        self._marks = []
        if not self._has_data() or not self.chart.series():
            return
        names = self._current_sample_names
        if not self._highlighted.intersection(names):
            return
        series = self.chart.series()[0]
        plot = self.chart.plotArea()
        fade = QColor(color("surface"))
        fade.setAlphaF(0.7)
        half = series.barWidth() / 2
        for i, name in enumerate(names):
            top = self.chart.mapToPosition(QPointF(0, i + half), series).y()
            bottom = self.chart.mapToPosition(QPointF(0, i - half), series).y()
            if name in self._highlighted:
                rect, fill = QRectF(plot.left() - 6, top, 4, bottom - top), color("accent")
            else:
                rect, fill = QRectF(plot.left(), top, plot.width(), bottom - top), fade
            mark = QGraphicsRectItem(rect.normalized(), self.chart)
            mark.setPen(QPen(Qt.NoPen))
            mark.setBrush(fill)
            mark.setZValue(10)
            mark.setData(0, name if name in self._highlighted else None)
            self._marks.append(mark)

    def _refresh_key(self, *_args) -> None:
        count = 0 if self._current_ratios is None else self._current_ratios.shape[1]
        self.key.setText(isotopologue_key_html(count))
        self.key.setVisible(count > 1)

    def hover_text(self, index: int) -> str:
        """Sample name and every isotopologue share for one bar."""
        lines = [self._current_sample_names[index]]
        lines += [
            f"M+{i}  {share * 100:.1f}%"
            for i, share in enumerate(self._current_ratios[index])
        ]
        return "\n".join(lines)

    def _on_bar_hovered(self, status: bool, index: int) -> None:
        if not status or not self._has_data():
            QToolTip.hideText()
            return
        QToolTip.showText(QCursor.pos(), self.hover_text(index), self.chart_view)

    def _setup_axes(self, sample_names: List[str]) -> None:
        """Setup chart axes for horizontal layout."""
        # Remove existing axes
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)

        # X-axis (horizontal): Ratio values (0 to 1)
        x_axis = QValueAxis()
        x_axis.setRange(0, 1)
        x_axis.setLabelFormat("%.1f")
        style_axis(x_axis)
        x_axis.setLineVisible(False)
        x_axis.setTickCount(3)  # 0, 0.5, 1.0
        self.header.set_has_data(True)

        # Sample names show only when every bar has room for one.
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
        self.key.hide()
        self.names_hint.hide()

        # Reset data
        self._current_eics = None
        self._current_compound = ""
        self._last_total_abundances = None
        self._last_eics = None
        self._current_ratios = None
        self._current_sample_names = None
        self._paint_highlight()

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
                compound_name=self._current_compound,
            )
            dialog.exec()

        except Exception as e:
            logger.exception("Failed to show popup chart: %s", e)
