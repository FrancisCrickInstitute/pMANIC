import random
from PySide6.QtWidgets import QWidget, QGridLayout
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt


class GraphView(QWidget):
    def __init__(self):
        super().__init__()
        self.chart_views = []
        self.setup_ui()

    def setup_ui(self):
        # Create the chart view layout
        chart_layout = QGridLayout()

        # Create and add the chart views
        num_charts = 20
        self.chart_views = self.setup_charts(num_charts)
        for i, chart_view in enumerate(self.chart_views):
            row = i // 5
            col = i % 5
            chart_layout.addWidget(chart_view, row, col)

        # Set the chart view layout
        self.setLayout(chart_layout)

    def setup_charts(self, num_charts):
        chart_views = []
        for _ in range(num_charts):
            chart = QChart()
            chart.setTitle("Dynamic Line Plot")
            chart.setBackgroundVisible(False)  # Set background visibility to False

            series = QLineSeries()
            series.append(0, 0)
            series.append(1, 1)
            series.append(2, 4)
            series.append(3, 9)

            chart.addSeries(series)

            x_axis = QValueAxis()
            y_axis = QValueAxis()
            chart.addAxis(x_axis, Qt.AlignBottom)
            chart.addAxis(y_axis, Qt.AlignLeft)
            series.attachAxis(x_axis)
            series.attachAxis(y_axis)

            chart_view = QChartView(chart)
            chart_view.setRenderHint(QPainter.Antialiasing)
            chart_views.append(chart_view)

        return chart_views

    def generate_random_data(self, num_points):
        x_data = list(range(num_points))
        y_data = [random.randint(0, 100) for _ in range(num_points)]
        return x_data, y_data

    def update_chart(self):
        num_points = 2000
        for chart_view in self.chart_views:
            x_data, y_data = self.generate_random_data(num_points)
            self.update_chart_data(chart_view, x_data, y_data)

    def update_chart_data(self, chart_view, x_data, y_data):
        series = chart_view.chart().series()[0]
        series.clear()
        for x, y in zip(x_data, y_data):
            series.append(x, y)
        chart_view.chart().axisX().setRange(min(x_data), max(x_data))
        chart_view.chart().axisY().setRange(min(y_data), max(y_data))