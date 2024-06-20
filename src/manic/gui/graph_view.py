import numpy as np
from PySide6.QtWidgets import QWidget, QGridLayout
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtGui import QPainter, QFont, QColor
from PySide6.QtCore import Qt, QTimer, QPointF, QMargins
from src.manic.data.eic_data_object import EICData

class GraphView(QWidget):
    def __init__(self):
        super().__init__()
        self.graph_layout = QGridLayout()
        self.graph_layout.setSpacing(0)  # Reduce spacing between charts
        self.graph_layout.setContentsMargins(0, 0, 0, 0)  # Add small margins
        self.setLayout(self.graph_layout)
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.update_graph_sizes)

    def extract_eic_data(self, cdf_object, compound_object):
        """Extracts EIC data for a compound from a CDF object."""
        scan_index = np.array(cdf_object.scan_index)
        mass_values = np.array(cdf_object.mass_values)
        intensity_values = np.array(cdf_object.intensity_values)
        scan_acquisition_time = np.array(cdf_object.scan_acquisition_time)
        target_mass = compound_object.mass

        eic_time = scan_acquisition_time / 60.0  # Convert to minutes
        eic_intensity = np.zeros_like(eic_time)

        for i in range(len(scan_index) - 1):
            start_idx = scan_index[i]
            end_idx = scan_index[i + 1]
            scan_mass_values = mass_values[start_idx:end_idx]
            scan_intensity_values = intensity_values[start_idx:end_idx]

            # Filter intensities for the exact target mass
            mask = scan_mass_values == target_mass
            eic_intensity[i] = np.sum(scan_intensity_values[mask])

        # Handle the last scan
        start_idx = scan_index[-1]
        scan_mass_values = mass_values[start_idx:]
        scan_intensity_values = intensity_values[start_idx:]

        mask = scan_mass_values == target_mass
        eic_intensity[-1] = np.sum(scan_intensity_values[mask])
        eic_obj = EICData(
            file_name=cdf_object.file_name,
            compound_name=compound_object.name,
            eic_time=eic_time,
            eic_intensity=eic_intensity,
            retention_time=compound_object.retention_time,
            l_offset=compound_object.l_offset,
            r_offset=compound_object.r_offset,
            target_mass=target_mass
        )

        return eic_obj

    def create_eic_plot(self, eic_obj):
        """Creates a plot for the extracted EIC data."""
        chart = QChart()
        chart.setBackgroundVisible(False)  # Set background visibility to False
        chart.legend().hide()  # Hide the legend

        # Create series
        series = QLineSeries()
        for x, y in zip(eic_obj.eic_time, eic_obj.eic_intensity):
            series.append(x, y)
        chart.addSeries(series)

        # Create axes
        x_axis = QValueAxis()
        y_axis = QValueAxis()
        chart.addAxis(x_axis, Qt.AlignBottom)
        chart.addAxis(y_axis, Qt.AlignLeft)
        series.attachAxis(x_axis)
        series.attachAxis(y_axis)

        # Add vertical lines for lOffset, rOffset, and retention time
        rt_line = QLineSeries()
        rt_line.append(eic_obj.retention_time, 0)
        rt_line.append(eic_obj.retention_time, max(eic_obj.eic_intensity) * 1.1)
        chart.addSeries(rt_line)
        rt_line.attachAxis(x_axis)
        rt_line.attachAxis(y_axis)

        loffset_line = QLineSeries()
        loffset_line.append(eic_obj.retention_time - eic_obj.l_offset, 0)
        loffset_line.append(eic_obj.retention_time - eic_obj.l_offset, max(eic_obj.eic_intensity) * 1.1)
        chart.addSeries(loffset_line)
        loffset_line.attachAxis(x_axis)
        loffset_line.attachAxis(y_axis)

        roffset_line = QLineSeries()
        roffset_line.append(eic_obj.retention_time + eic_obj.r_offset, 0)
        roffset_line.append(eic_obj.retention_time + eic_obj.r_offset, max(eic_obj.eic_intensity) * 1.1)
        chart.addSeries(roffset_line)
        roffset_line.attachAxis(x_axis)
        roffset_line.attachAxis(y_axis)

        # Adjust the x-axis range to be only double the size of the offset window
        x_axis.setRange(eic_obj.retention_time - 0.5, eic_obj.retention_time + 0.5)
        y_axis.setRange(0, max(eic_obj.eic_intensity) * 1.1)

        # Add title as a small label in the background
        chart.setTitle(eic_obj.file_name)
        chart.setTitleFont(QFont("Arial", 8))
        chart.setTitleBrush(QColor(100, 100, 100, 100))  # Semi-transparent gray
        chart.setMargins(QMargins(0, 0, 0, 0))

        return chart

    def refresh_plots(self, charts):
        """Refreshes the graph view with the provided charts."""
        # Clear existing charts
        for i in reversed(range(self.graph_layout.count())):
            widget = self.graph_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        # Determine the number of columns and rows to fit the screen
        num_charts = len(charts)
        if num_charts == 0:
            return

        num_columns = int(np.ceil(np.sqrt(num_charts)))
        num_rows = int(np.ceil(num_charts / num_columns))

        # Add new charts
        for i, chart in enumerate(charts):
            chart_view = QChartView(chart)
            chart_view.setRenderHint(QPainter.Antialiasing)
            chart_view.setContentsMargins(0, 0, 0, 0)
            row = i // num_columns
            col = i % num_columns
            self.graph_layout.addWidget(chart_view, row, col)

        # Update the layout to fit the window
        self.update_graph_sizes()

    def update_graph_sizes(self):
        """Dynamically update the sizes of the graphs."""
        available_width = self.width() - self.graph_layout.spacing() * (self.graph_layout.columnCount() + 1)
        available_height = self.height() - self.graph_layout.spacing() * (self.graph_layout.rowCount() + 1)

        num_charts = self.graph_layout.count()
        if num_charts == 0:
            return

        num_columns = int(np.ceil(np.sqrt(num_charts)))
        num_rows = int(np.ceil(num_charts / num_columns))

        graph_width = available_width // num_columns
        graph_height = available_height // num_rows

        for i in range(self.graph_layout.count()):
            widget = self.graph_layout.itemAt(i).widget()
            if widget is not None:
                widget.setFixedSize(graph_width, graph_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_timer.start(100)  # Delay update for 100ms