import numpy as np
from PySide6.QtWidgets import QWidget, QGridLayout, QGraphicsTextItem
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtGui import QPainter, QFont, QColor, QPen
from PySide6.QtCore import Qt, QTimer, QPointF, QMargins


class GraphView(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("graphView")
        self.graph_layout = QGridLayout()
        self.graph_layout.setSpacing(0)  # Reduce spacing between charts
        self.graph_layout.setContentsMargins(0, 0, 0, 0)  # Add small margins
        self.setLayout(self.graph_layout)
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.update_graph_sizes)

    def create_eic_plot(
        self,
        eic_time: np.ndarray,
        eic_intensity: np.ndarray,
        retention_time: float,
        l_offset: float,
        r_offset: float,
        file_name: str,
    ) -> QChart:
        """
        Creates a plot for the extracted ion chromatogram (EIC) data.

        Args:
            eic_obj (EICData): The EIC data object containing the data to be plotted.

        Returns:
            QChart: The created chart object.

        Raises:
            ValueError: If the EIC data is empty or invalid.
        """
        if eic_time.size == 0 or eic_intensity.size == 0:
            raise ValueError("EIC data is empty or invalid.")

        chart = QChart()
        chart.setBackgroundVisible(False)
        chart.setPlotAreaBackgroundVisible(True)
        chart.setPlotAreaBackgroundBrush(
            QColor(255, 255, 255)
        )  # Set plot area to white
        chart.legend().hide()

        # Create series
        series = QLineSeries()
        for x, y in zip(eic_time, eic_intensity):
            series.append(x, y)
        series.setPen(QPen(QColor(139, 0, 0), 1))  # Dark red color
        chart.addSeries(series)

        # Create axes
        x_axis = QValueAxis()
        y_axis = QValueAxis()
        chart.addAxis(x_axis, Qt.AlignBottom)
        chart.addAxis(y_axis, Qt.AlignLeft)
        series.attachAxis(x_axis)
        series.attachAxis(y_axis)

        # Remove grid lines
        x_axis.setGridLineVisible(False)
        y_axis.setGridLineVisible(False)

        # Set smaller font for axis labels
        font = QFont("Arial", 8)
        x_axis.setLabelsFont(font)
        y_axis.setLabelsFont(font)

        # Customize x-axis
        x_min = max(retention_time - 0.2, np.min(eic_time))
        x_max = min(retention_time + 0.2, np.max(eic_time))
        x_axis.setRange(x_min, x_max)
        x_axis.setTickCount(5)
        x_axis.setLabelFormat("%.2f")
        x_axis.setLabelsColor(QColor(0, 0, 0))  # Set axis label color to black
        x_axis.setLinePenColor(QColor(0, 0, 0))

        # Customize y-axis
        y_max = np.max(eic_intensity)
        y_axis.setRange(0, y_max)
        y_axis.setTickCount(5)
        y_axis.setLabelFormat("%.0f")
        y_axis.setLabelsColor(QColor(0, 0, 0))  # Set axis label color to black
        y_axis.setLinePenColor(QColor(0, 0, 0))

        # Add vertical lines for lOffset, rOffset, and retention time
        rt_line = QLineSeries()
        rt_line.append(retention_time, 0)
        rt_line.append(retention_time, y_max)
        rt_line.setPen(QPen(Qt.black, 1))
        chart.addSeries(rt_line)
        rt_line.attachAxis(x_axis)
        rt_line.attachAxis(y_axis)

        loffset_line = QLineSeries()
        loffset_line.append(retention_time - l_offset, 0)
        loffset_line.append(retention_time - l_offset, y_max)
        loffset_line.setPen(
            QPen(QColor(255, 140, 0), 1, Qt.DashLine)
        )  # Dark orange color
        chart.addSeries(loffset_line)
        loffset_line.attachAxis(x_axis)
        loffset_line.attachAxis(y_axis)

        roffset_line = QLineSeries()
        roffset_line.append(retention_time + r_offset, 0)
        roffset_line.append(retention_time + r_offset, y_max)
        roffset_line.setPen(
            QPen(QColor(138, 43, 226), 1, Qt.DashLine)
        )  # Blue violet color
        chart.addSeries(roffset_line)
        roffset_line.attachAxis(x_axis)
        roffset_line.attachAxis(y_axis)

        # Add title as a small label in the background
        chart.setTitle(file_name)
        chart.setTitleFont(QFont("Arial", 8))
        chart.setTitleBrush(QColor(0, 0, 0))  # Set title color to black
        chart.setMargins(QMargins(-13, -10, -13, -15))  # Adjusted top margin

        return chart

    def refresh_plots(self, eic_data_list):
        """Refreshes the graph view with the provided EIC data."""
        # Clear existing charts
        for i in reversed(range(self.graph_layout.count())):
            widget = self.graph_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        # Determine the number of columns and rows to fit the screen
        num_charts = len(eic_data_list)
        if num_charts == 0:
            return

        num_columns = int(np.ceil(np.sqrt(num_charts)))
        num_rows = int(np.ceil(num_charts / num_columns))

        # Add new charts
        for i, eic_data in enumerate(eic_data_list):
            chart_view = QChartView(eic_data)
            chart_view.setRenderHint(QPainter.Antialiasing)
            chart_view.setContentsMargins(0, 0, 0, 0)
            chart_view.setObjectName("chartView")

            row = i // num_columns
            col = i % num_columns
            self.graph_layout.addWidget(chart_view, row, col)

        # Update the layout to fit the window
        self.update_graph_sizes()

    def update_graph_sizes(self):
        """Dynamically update the sizes of the graphs."""
        available_width = self.width() - self.graph_layout.spacing() * (
            self.graph_layout.columnCount() + 1
        )
        available_height = self.height() - self.graph_layout.spacing() * (
            self.graph_layout.rowCount() + 1
        )

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
