import logging
import math
from typing import List

import numpy as np
import pyqtgraph as pg
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QMargins, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QSizePolicy, QWidget

from manic.io.compound_reader import read_compound
from manic.processors.eic_processing import get_eics_for_compound
from manic.utils.timer import measure_time

logger = logging.getLogger(__name__)

# colours
steel_blue_colour = QColor(70, 130, 180)
dark_red_colour = QColor(139, 0, 0)

label_colors = [
    QColor(31, 119, 180),  # blue
    QColor(255, 127, 14),  # orange
    QColor(44, 160, 44),  # green
    QColor(214, 39, 40),  # red
    QColor(148, 103, 189),  # purple
    QColor(140, 86, 75),  # brown
    QColor(227, 119, 194),  # pink
    QColor(127, 127, 127),  # gray
    QColor(188, 189, 34),  # olive
    QColor(23, 190, 207),  # cyan
]


class GraphView(QWidget):
    """
    Re-implements the old grid-of-charts look with pyqtgraph,
    but fetches data via the new processors/io stack.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QGridLayout(self)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)

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
            # Build all plots first
            plot_widgets = [self._build_plot(eic) for eic in eics]

            # Add to layout in one go
            for i, widget in enumerate(plot_widgets):
                row = i // cols
                col = i % cols
                self._layout.addWidget(widget, row, col)

        # ensure the added widgets are correctly sized with stretch factors
        self._update_graph_sizes()

    #  internal functions
    def _build_plot(self, eic) -> pg.PlotWidget:
        """Create a QChartView with EIC data and guide lines."""
        compound = read_compound(eic.compound_name)

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
        # Using smart range where the data starts at first recorded
        # point within the window rather than the actual minumum
        # time point in the range for which there might not be a recording
        rt = compound.retention_time
        x_min = max(rt - 0.2, np.min(eic.time))
        x_max = min(rt + 0.2, np.max(eic.time))
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
        self._add_guide_line(
            chart,
            x_axis,
            y_axis,
            rt - compound.loffset,
            0,
            scaled_y_max,
            steel_blue_colour,
            dashed=True,
        )  # Left offset
        self._add_guide_line(
            chart,
            x_axis,
            y_axis,
            rt + compound.roffset,
            0,
            scaled_y_max,
            steel_blue_colour,
            dashed=True,
        )  # Right offset

        # helper function get superscript num
        def superscript(n):
            sup_map = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
            return str(n).translate(sup_map)

        # Set title
        chart.setTitle(f"{eic.sample_name} (×10{superscript(scale_exp)})")
        chart.setTitleFont(QFont("Arial", 9))
        chart.setTitleBrush(QColor(0, 0, 0))
        chart.setMargins(QMargins(-13, -10, -13, -15))

        # Create chart view
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setContentsMargins(0, 0, 0, 0)

        # Add size policy to make charts expandable
        chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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
