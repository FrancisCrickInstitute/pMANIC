import numpy as np
from PySide6.QtWidgets import QWidget, QGridLayout,QGraphicsTextItem
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtGui import QPainter, QFont, QColor, QPen
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

    def extract_eic_data(self, cdf_object, compound_object, mass_tolerance=0.25):
        scan_index = np.array(cdf_object.scan_index)
        mass_values = np.array(cdf_object.mass_values)
        intensity_values = np.array(cdf_object.intensity_values)
        scan_acquisition_time = np.array(cdf_object.scan_acquisition_time)
        target_mass = compound_object.mass
        retention_time = compound_object.retention_time

        # Convert to minutes, and filter data within retention time window
        retention_time_window = 0.2  # 0.2 minutes on each side
        eic_time = scan_acquisition_time / 60.0  # Convert to minutes
        time_mask = (eic_time >= (retention_time - retention_time_window)) & \
                    (eic_time <= (retention_time + retention_time_window))

        # Apply time mask to filter out data outside the retention time window
        filtered_indices = np.where(time_mask)[0]
        if len(filtered_indices) == 0:
            raise ValueError("No data within the retention time window.")

        # Initializing eic_intensity to capture filtered data
        eic_intensity = np.zeros_like(eic_time[time_mask])


        # Process only filtered indices
        for i in range(len(filtered_indices) - 1):
            start_idx = scan_index[filtered_indices[i]]
            end_idx = scan_index[filtered_indices[i + 1]]
            scan_mass_values = mass_values[start_idx:end_idx]
            scan_intensity_values = intensity_values[start_idx:end_idx]

            mask = (scan_mass_values >= target_mass - mass_tolerance) & \
                   (scan_mass_values <= target_mass + mass_tolerance)
            eic_intensity[i] = np.sum(scan_intensity_values[mask])

        # Handle the last filtered scan
        start_idx = scan_index[filtered_indices[-1]]
        scan_mass_values = mass_values[start_idx:]
        scan_intensity_values = intensity_values[start_idx:]
        scan_time_values = scan_acquisition_time[start_idx:] / 60.0  # Convert to minutes

        # Apply the time filter to ensure we are only considering values within the retention time window
        time_filter = (scan_time_values >= (retention_time - retention_time_window)) & \
                      (scan_time_values <= (retention_time + retention_time_window))

        scan_mass_values = scan_mass_values[time_filter]
        scan_intensity_values = scan_intensity_values[time_filter]

        mask = (scan_mass_values >= target_mass - mass_tolerance) & \
               (scan_mass_values <= target_mass + mass_tolerance)
        eic_intensity[-1] = np.sum(scan_intensity_values[mask])

        eic_obj = EICData(
            file_name=cdf_object.file_name,
            compound_name=compound_object.name,
            eic_time=eic_time[time_mask],
            eic_intensity=eic_intensity,
            retention_time=retention_time,
            l_offset=compound_object.l_offset,
            r_offset=compound_object.r_offset,
            target_mass=target_mass
        )

        return eic_obj

    def create_eic_plot(self, eic_obj: EICData) -> QChart:
        """
        Creates a plot for the extracted ion chromatogram (EIC) data.

        Args:
            eic_obj (EICData): The EIC data object containing the data to be plotted.

        Returns:
            QChart: The created chart object.

        Raises:
            ValueError: If the EIC data is empty or invalid.
        """
        if eic_obj.eic_time.size == 0 or eic_obj.eic_intensity.size == 0:
            raise ValueError("EIC data is empty or invalid.")

        chart = QChart()
        chart.setBackgroundVisible(False)
        chart.legend().hide()
        chart.setPlotAreaBackgroundVisible(False)

        # Create series
        series = QLineSeries()
        for x, y in zip(eic_obj.eic_time, eic_obj.eic_intensity):
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
        x_min = max(eic_obj.retention_time - 0.2, np.min(eic_obj.eic_time))
        x_max = min(eic_obj.retention_time + 0.2, np.max(eic_obj.eic_time))
        x_axis.setRange(x_min, x_max)
        x_axis.setTickCount(5)
        x_axis.setLabelFormat("%.2f")

        # Customize y-axis
        y_max = np.max(eic_obj.eic_intensity)
        y_axis.setRange(0, y_max)
        y_axis.setTickCount(5)
        y_axis.setLabelFormat("%.0f")

        # Add vertical lines for lOffset, rOffset, and retention time
        rt_line = QLineSeries()
        rt_line.append(eic_obj.retention_time, 0)
        rt_line.append(eic_obj.retention_time, y_max)
        rt_line.setPen(QPen(Qt.black, 1))
        chart.addSeries(rt_line)
        rt_line.attachAxis(x_axis)
        rt_line.attachAxis(y_axis)

        loffset_line = QLineSeries()
        loffset_line.append(eic_obj.retention_time - eic_obj.l_offset, 0)
        loffset_line.append(eic_obj.retention_time - eic_obj.l_offset, y_max)
        loffset_line.setPen(QPen(QColor(255, 215, 0), 1, Qt.DashLine))  # Gold color
        chart.addSeries(loffset_line)
        loffset_line.attachAxis(x_axis)
        loffset_line.attachAxis(y_axis)

        roffset_line = QLineSeries()
        roffset_line.append(eic_obj.retention_time + eic_obj.r_offset, 0)
        roffset_line.append(eic_obj.retention_time + eic_obj.r_offset, y_max)
        roffset_line.setPen(QPen(QColor(138, 43, 226), 1, Qt.DashLine))  # Blue violet color
        chart.addSeries(roffset_line)
        roffset_line.attachAxis(x_axis)
        roffset_line.attachAxis(y_axis)

        # Add title as a small label in the background
        chart.setTitle(eic_obj.file_name)
        chart.setTitleFont(QFont("Arial", 8))
        chart.setTitleBrush(QColor(100, 100, 100, 100))
        chart.setMargins(QMargins(-15, -10, -15, -15))  # Adjusted top margin

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