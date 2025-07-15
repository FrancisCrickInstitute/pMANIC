import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QMargins, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QWidget

from manic.io.compound_reader import read_compound
from manic.io.sample_reader import list_active_samples
from manic.processors.eic_processing import get_eics_for_compound

# colours
steel_blue_colour = QColor(70, 130, 180)
dark_red_colour = QColor(139, 0, 0)


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
    def plot_compound(self, compound_name: str) -> None:
        """
        Build one mini-plot per active sample for the selected *compound*.
        """
        self._clear_layout()

        samples = list_active_samples()
        print(samples)
        if not samples:
            return

        eics = get_eics_for_compound(compound_name, samples)  # new pipeline
        num = len(eics)
        cols = math.ceil(math.sqrt(num))

        for i, eic in enumerate(eics):
            plot_widget = self._build_plot(eic)
            self._layout.addWidget(plot_widget, i // cols, i % cols)

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

        # scale the data to make more space for graphs
        y_max = float(np.max(eic.intensity))
        scale_exp = int(np.floor(np.log10(y_max)))
        scale_factor = 10**scale_exp
        scaled_intensity = eic.intensity / scale_factor

        # Create EIC series
        series = QLineSeries()
        for x, y in zip(eic.time, scaled_intensity):
            series.append(x, y)
        series.setPen(QPen(dark_red_colour, 1.2))  # Dark red
        chart.addSeries(series)

        # Create axes
        x_axis = QValueAxis()
        y_axis = QValueAxis()
        chart.addAxis(x_axis, Qt.AlignBottom)
        chart.addAxis(y_axis, Qt.AlignLeft)
        series.attachAxis(x_axis)
        series.attachAxis(y_axis)

        # Set up axes
        x_axis.setGridLineVisible(False)
        y_axis.setGridLineVisible(False)
        font = QFont("Arial", 8)
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

        y_max = np.max(scaled_intensity)
        y_axis.setRange(0, y_max)
        y_axis.setLabelFormat("%.2g")

        # Set tick count (number of major ticks/labels)
        x_axis.setTickCount(5)
        y_axis.setTickCount(5)

        # Add guide lines
        self._add_guide_line(
            chart, x_axis, y_axis, rt, 0, y_max, QColor(0, 0, 0)
        )  # RT line
        self._add_guide_line(
            chart,
            x_axis,
            y_axis,
            rt - compound.loffset,
            0,
            y_max,
            steel_blue_colour,
            dashed=True,
        )  # Left offset
        self._add_guide_line(
            chart,
            x_axis,
            y_axis,
            rt + compound.roffset,
            0,
            y_max,
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
        """
        Resize every PlotWidget so the grid fills the parent without scrollbars.
        """
        if self._layout.count() == 0:
            return

        cols = self._layout.columnCount() or 1
        rows = self._layout.rowCount() or 1

        avail_w = self.width() - (cols + 1) * self._layout.spacing()
        avail_h = self.height() - (rows + 1) * self._layout.spacing()

        w = avail_w // cols
        h = avail_h // rows

        for i in range(self._layout.count()):
            widget = self._layout.itemAt(i).widget()
            widget.setFixedSize(w, h)

    def _clear_layout(self) -> None:
        while self._layout.count():
            w = self._layout.takeAt(0).widget()
            if w:
                w.setParent(None)

    # throttle rapid resize events
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._resize_timer.start(100)
