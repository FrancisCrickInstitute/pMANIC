import random
import numpy as np
from PySide6.QtWidgets import QWidget, QGridLayout
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt
from src.manic.data.eic_data_object import EICData


class GraphView(QWidget):
    def __init__(self, num_graphs):
        super().__init__()
        self.num_graphs = num_graphs
        self.graph_views = []
        self.setup_ui()

    def setup_ui(self):
        # Create the graph view layout
        graph_layout = QGridLayout()

        # Create and add the graph views
        self.graph_views = self.setup_graphs(self.num_graphs)
        for i, graph_view in enumerate(self.graph_views):
            row = i // 5
            col = i % 5
            graph_layout.addWidget(graph_view, row, col)

        # Set the graph view layout
        self.setLayout(graph_layout)

    def setup_graphs(self, num_graphs):
        graph_views = []
        for _ in range(num_graphs):
            graph = QChart()
            graph.setTitle("Dynamic Line Plot")
            graph.setBackgroundVisible(False)  # Set background visibility to False

            series = QLineSeries()
            series.append(0, 0)
            series.append(1, 1)
            series.append(2, 4)
            series.append(3, 9)

            graph.addSeries(series)

            x_axis = QValueAxis()
            y_axis = QValueAxis()
            graph.addAxis(x_axis, Qt.AlignBottom)
            graph.addAxis(y_axis, Qt.AlignLeft)
            series.attachAxis(x_axis)
            series.attachAxis(y_axis)

            graph_view = QChartView(graph)
            graph_view.setRenderHint(QPainter.Antialiasing)
            graph_views.append(graph_view)

        return graph_views

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
            eic_intensity=eic_intensity
        )

        return eic_obj

    def plot_EIC(self, eic_obj):

        pass
