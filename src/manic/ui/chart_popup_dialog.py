from typing import List
import numpy as np

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSet,
    QChart,
    QChartView,
    QHorizontalBarSeries,
    QHorizontalStackedBarSeries,
    QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout

from manic.ui.colors import label_colors


class ChartPopupDialog(QDialog):
    """Modal dialog showing an enlarged version of toolbar charts with sample names visible."""
    
    def __init__(self, chart_type: str, title: str, data, sample_names: List[str], parent=None):
        super().__init__(parent)
        self.chart_type = chart_type
        self.data = data
        self.sample_names = sample_names
        
        self.setWindowTitle(f"MANIC - {title}")
        self.setModal(True)
        self.resize(800, 600)
        
        # Set window icon (same as main window)
        self._set_window_icon(parent)
        
        self._setup_ui(title)
        self._populate_chart()
    
    def _set_window_icon(self, parent_widget):
        """Set window icon by finding the main window."""
        # Walk up the parent hierarchy to find the main window
        widget = parent_widget
        while widget and widget.parent():
            widget = widget.parent()
            if hasattr(widget, '_get_logo_path'):
                logo_path = widget._get_logo_path()
                if logo_path:
                    from PySide6.QtGui import QIcon
                    self.setWindowIcon(QIcon(logo_path))
                break
    
    def _setup_ui(self, title: str):
        """Setup the dialog UI with chart and close button."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Create chart
        self.chart = QChart()
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        
        # Setup chart appearance
        self.chart.setBackgroundVisible(False)
        self.chart.setPlotAreaBackgroundVisible(True)
        self.chart.setPlotAreaBackgroundBrush(QColor(255, 255, 255))
        self.chart.legend().setVisible(False)
        self.chart.setTitle(title)
        self.chart.setTitleFont(QFont("Arial", 16, QFont.Bold))
        self.chart.setTitleBrush(QColor("black"))
        
        layout.addWidget(self.chart_view)
        
        # Add close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setMinimumWidth(100)
        # Apply red button styling directly
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #bb2d3b;
            }
            QPushButton:pressed {
                background-color: #b02a37;
            }
        """)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def _populate_chart(self):
        """Populate chart based on type and data."""
        if self.chart_type == "total_abundance":
            self._create_total_abundance_chart()
        elif self.chart_type == "isotopologue_ratios":
            self._create_isotopologue_chart()
    
    def _create_total_abundance_chart(self):
        """Create enlarged total abundance chart with sample names on Y-axis."""
        if self.data is None or len(self.data) == 0:
            return
            
        # Create horizontal bar series
        bar_series = QHorizontalBarSeries()
        bar_series.setBarWidth(0.8)
        
        # Create single bar set
        bar_set = QBarSet("Total Abundance")
        bar_set.setColor(QColor(0, 128, 128))  # Dark teal
        
        # Calculate scaling for display
        max_abundance = float(np.max(self.data)) if len(self.data) > 0 else 1.0
        scale_exp = int(np.floor(np.log10(max_abundance))) if max_abundance > 0 else 0
        scale_factor = 10**scale_exp if scale_exp != 0 else 1
        
        # Add scaled abundance values
        for abundance in self.data:
            scaled_abundance = abundance / scale_factor
            bar_set.append(scaled_abundance)
        
        bar_series.append(bar_set)
        self.chart.addSeries(bar_series)
        
        # Setup axes with sample names visible
        self._setup_total_abundance_axes(max_abundance, scale_exp, scale_factor)
        
        # Attach series to axes
        bar_series.attachAxis(self.chart.axes(Qt.Horizontal)[0])
        bar_series.attachAxis(self.chart.axes(Qt.Vertical)[0])
    
    def _create_isotopologue_chart(self):
        """Create enlarged isotopologue chart with sample names on Y-axis."""
        if self.data is None or len(self.data) == 0:
            return
            
        # Create horizontal stacked bar series
        stacked_series = QHorizontalStackedBarSeries()
        stacked_series.setBarWidth(0.8)
        
        # Get number of isotopologues
        num_isotopologues = self.data.shape[1] if len(self.data.shape) > 1 else 1
        
        # Create bar sets for each isotopologue
        for i in range(num_isotopologues):
            bar_set = QBarSet(f"M+{i}")
            
            # Set color from palette
            if i < len(label_colors):
                bar_set.setColor(QColor(label_colors[i]))
            
            # Add ratio values for this isotopologue across all samples
            for sample_idx in range(len(self.sample_names)):
                if len(self.data.shape) > 1:
                    ratio = self.data[sample_idx, i]
                else:
                    ratio = 1.0 if i == 0 else 0.0  # Single trace case
                bar_set.append(ratio)
            
            stacked_series.append(bar_set)
        
        self.chart.addSeries(stacked_series)
        
        # Setup axes
        self._setup_isotopologue_axes()
        
        # Show legend for isotopologues
        if num_isotopologues > 1:
            self.chart.legend().setVisible(True)
            self.chart.legend().setAlignment(Qt.AlignRight)
        
        # Attach series to axes
        stacked_series.attachAxis(self.chart.axes(Qt.Horizontal)[0])
        stacked_series.attachAxis(self.chart.axes(Qt.Vertical)[0])
    
    def _setup_total_abundance_axes(self, max_abundance: float, scale_exp: int, scale_factor: float):
        """Setup axes for total abundance chart."""
        # Remove existing axes
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)
        
        # X-axis (horizontal): Abundance values
        x_axis = QValueAxis()
        scaled_max = max_abundance / scale_factor
        x_axis.setRange(0, scaled_max * 1.05)  # Add 5% padding
        x_axis.setLabelFormat("%.1f")
        x_axis.setLabelsFont(QFont("Arial", 10))
        x_axis.setGridLineVisible(True)
        x_axis.setTickCount(6)
        
        # Set scaling factor as axis title
        if scale_exp != 0:
            def superscript(n):
                sup_map = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
                return str(n).translate(sup_map)
            x_axis.setTitleText(f"×10{superscript(scale_exp)}")
            x_axis.setTitleFont(QFont("Arial", 12))
        
        # Y-axis (vertical): Sample names - NOW VISIBLE
        y_axis = QBarCategoryAxis()
        # Add sample names in reverse order to match QtCharts bottom-to-top display
        reversed_names = list(reversed(self.sample_names))
        y_axis.append(reversed_names)
        y_axis.setLabelsFont(QFont("Arial", 10))
        y_axis.setGridLineVisible(False)
        y_axis.setLabelsVisible(True)  # Show sample names
        
        # Add axes to chart
        self.chart.addAxis(x_axis, Qt.AlignBottom)
        self.chart.addAxis(y_axis, Qt.AlignLeft)
    
    def _setup_isotopologue_axes(self):
        """Setup axes for isotopologue chart."""
        # Remove existing axes
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)
        
        # X-axis (horizontal): Ratio values (0-1)
        x_axis = QValueAxis()
        x_axis.setRange(0, 1.0)
        x_axis.setLabelFormat("%.1f")
        x_axis.setLabelsFont(QFont("Arial", 10))
        x_axis.setGridLineVisible(True)
        x_axis.setTickCount(6)
        x_axis.setTitleText("Isotopologue Ratio")
        x_axis.setTitleFont(QFont("Arial", 12))
        
        # Y-axis (vertical): Sample names - NOW VISIBLE
        y_axis = QBarCategoryAxis()
        y_axis.append(self.sample_names)
        y_axis.setLabelsFont(QFont("Arial", 10))
        y_axis.setGridLineVisible(False)
        y_axis.setLabelsVisible(True)  # Show sample names
        
        # Add axes to chart
        self.chart.addAxis(x_axis, Qt.AlignBottom)
        self.chart.addAxis(y_axis, Qt.AlignLeft)