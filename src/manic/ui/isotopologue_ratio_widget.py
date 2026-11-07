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
from PySide6.QtCore import QMargins, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from manic.io.compound_reader import read_compound_with_session
from manic.io.eic_reader import EIC
from manic.processors.display_deconvolution import integrated_display_areas

from . import theme
from .chart_header import ChartHeader
from .chart_popup_dialog import PinnedAxis, missing_ratio_note, value_axis_ticks
from .chart_style import (
    BarRows,
    fit_category_names,
    fit_name_font,
    place_row_notes,
    style_axis,
    style_chart,
)
from .colors import label_colors
from .sidebar_widgets import SummaryChartArea
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

    sample_activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("isotopologueRatioWidget")

        self.use_corrected = False

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

        self.header = ChartHeader("Label incorporation")
        self.header.expand_button.clicked.connect(self._show_popup_chart)

        self.key = QLabel()
        self.key.setObjectName("isotopologueKey")
        self.key.setWordWrap(True)
        self.key.setTextFormat(Qt.RichText)
        self.key.setContentsMargins(8, 2, 8, 0)
        theme.style(self.key, "color: @text_secondary; font-size: 11px;")
        # Never taller than its wrapped lines, so spare height falls below the chart.
        self.key.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.key.hide()
        theme.notifier.changed.connect(self._refresh_key)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.key)
        # The value axis stays above the rows while they scroll, as in the popup.
        self.value_axis = PinnedAxis(self.chart_view)
        layout.addWidget(self.value_axis)
        self.chart_area = SummaryChartArea(self.chart_view, 4)
        layout.addWidget(self.chart_area)
        self.chart.plotAreaChanged.connect(self._fit_names)

        # The grid's selected samples, marked beside their bars.
        self._highlighted: set[str] = set()
        self._marks: list[QGraphicsRectItem] = []
        # "—" on each row with no ratio, which has no bar.
        self._dashes: list[QGraphicsSimpleTextItem] = []
        self.chart.plotAreaChanged.connect(self._place_dashes)
        theme.notifier.changed.connect(self._place_dashes)
        self.chart.plotAreaChanged.connect(self._paint_highlight)
        theme.notifier.changed.connect(self._paint_highlight)

        # No taller than its rows, so the panel stacks the next chart right under it.
        layout.setSizeConstraint(QVBoxLayout.SetMinAndMaxSize)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._current_eics: Optional[List[EIC]] = None
        self._current_compound: str = ""
        self._last_total_abundances: Optional[np.ndarray] = None
        self._last_eics: Optional[List[EIC]] = None
        self._current_ratios: Optional[np.ndarray] = None
        self._current_sample_names: Optional[List[str]] = None

    def update_ratios(self, compound_name: str, eics: List[EIC]) -> None:
        """Integrate ``eics`` and chart each sample's isotopologue ratios."""
        if not eics or not compound_name:
            self._clear_chart()
            return

        self._current_eics = eics
        self._current_compound = compound_name

        ratios, total_abundances = self._calculate_integrated_data(eics, compound_name)

        if ratios is None:
            self._clear_chart()
            return

        self._last_total_abundances = total_abundances
        self._last_eics = eics

        if eics[0].intensity.ndim == 1:
            # Single trace - don't show isotopologue chart (it would just be 100%)
            self._clear_chart()
            return

        # Reversed for horizontal bars, which QtCharts draws bottom to top. A reversed
        # copy: the caller still holds this list and the abundances shared with the
        # abundance chart follow its original order.
        ordered_eics = eics[::-1]
        ordered_ratios = np.flipud(ratios)

        self._current_ratios = ordered_ratios
        self._current_sample_names = [eic.sample_name for eic in ordered_eics]

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

    def _update_chart(self, ratios: np.ndarray, sample_names: List[str]) -> None:
        """One stacked bar per sample; ``ratios`` is (n_samples, n_isotopologues)."""
        self.chart.removeAllSeries()

        bar_series = QHorizontalStackedBarSeries()

        bar_series.setBarWidth(0.8)

        n_samples, n_isotopologues = ratios.shape

        bar_sets = []
        for i in range(n_isotopologues):
            bar_set = QBarSet(f"M+{i}")
            bar_set.setColor(label_colors[i % len(label_colors)])
            bar_set.setBorderColor(color("surface"))

            for j in range(n_samples):
                bar_set.append(ratios[j, i])

            bar_sets.append(bar_set)
            bar_series.append(bar_set)

        self.chart.addSeries(bar_series)
        self.chart_area.set_rows(len(sample_names))

        self._setup_axes(sample_names)

        bar_series.attachAxis(self.chart.axes(Qt.Horizontal)[0])
        bar_series.attachAxis(self.chart.axes(Qt.Vertical)[0])
        # New axes start with full names at the axis size; the plot area may not change to refit them.
        self._fit_names()
        self._refresh_key()
        self._paint_highlight()
        self._place_dashes()
        self._rows.refresh()

    def empty_rows(self) -> list[int]:
        """Bar rows (0 is the bottom bar) whose sample has no ratio."""
        if not self._has_data():
            return []
        return [i for i, row in enumerate(self._current_ratios) if not np.nansum(row) > 0]

    def _place_dashes(self, *_args) -> None:
        place_row_notes(self.chart, self._dashes, dict.fromkeys(self.empty_rows(), "—"))

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
        # An accent outline would vanish against the blue M+0 segment, and fading the
        # other rows muddies the cohort, so a selected row gets a soft band behind its
        # name and bar gaps, and an accent tick beside its bar.
        for mark in self._marks:
            if mark.scene() is not None:
                mark.scene().removeItem(mark)
        self._marks = []
        if not self._has_data() or not self.chart.series():
            return
        series = self.chart.series()[0]
        plot = self.chart.plotArea()
        for i, name in enumerate(self._current_sample_names):
            if name not in self._highlighted:
                continue
            top = self.chart.mapToPosition(QPointF(0, i + 0.5), series).y()
            bottom = self.chart.mapToPosition(QPointF(0, i - 0.5), series).y()
            half = series.barWidth() / 2
            bar_top = self.chart.mapToPosition(QPointF(0, i + half), series).y()
            bar_bottom = self.chart.mapToPosition(QPointF(0, i - half), series).y()
            # Above the plot fill (z 0), under the grid, axis text and bars.
            band = QGraphicsRectItem(QRectF(0, top, plot.right(), bottom - top).normalized(), self.chart)
            band.setPen(QPen(Qt.NoPen))
            band.setBrush(color("accent_soft"))
            band.setZValue(0.5)
            tick = QGraphicsRectItem(
                QRectF(plot.left() - 5, bar_top, 3, bar_bottom - bar_top).normalized(), self.chart
            )
            tick.setPen(QPen(Qt.NoPen))
            tick.setBrush(color("accent"))
            tick.setZValue(10)
            self._marks += [band, tick]

    def _refresh_key(self, *_args) -> None:
        count = 0 if self._current_ratios is None else self._current_ratios.shape[1]
        self.key.setText(isotopologue_key_html(count))
        self.key.setVisible(count > 1)

    def hover_text(self, index: int) -> str:
        """Sample name and every isotopologue share for one row, or why it has none."""
        if index in self.empty_rows():
            return missing_ratio_note(self._current_sample_names[index])
        lines = [self._current_sample_names[index]]
        lines += [
            f"M+{i}  {share * 100:.1f}%"
            for i, share in enumerate(self._current_ratios[index])
        ]
        return "\n".join(lines)

    def _setup_axes(self, sample_names: List[str]) -> None:
        """Setup chart axes for horizontal layout."""
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)

        x_axis = QValueAxis()
        x_axis.setRange(0, 1)
        x_axis.setLabelFormat("%.1f")
        style_axis(x_axis)
        x_axis.setLineVisible(False)
        x_axis.setLabelsVisible(False)
        x_axis.setTickCount(3)  # 0, 0.5, 1.0
        self.header.set_has_data(True)

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
        self.key.hide()
        self.value_axis.set_axis("", [])
        self.chart_area.set_rows(0)

        self._current_eics = None
        self._current_compound = ""
        self._last_total_abundances = None
        self._last_eics = None
        self._current_ratios = None
        self._current_sample_names = None
        self._paint_highlight()
        self._place_dashes()
        self._rows.refresh()

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
                title="Label incorporation",
                data=self._current_ratios,
                sample_names=self._current_sample_names,
                parent=self,
                compound_name=self._current_compound,
            )
            dialog.sample_activated.connect(self.sample_activated)
            dialog.exec()

        except Exception as e:
            logger.exception("Failed to show popup chart: %s", e)
