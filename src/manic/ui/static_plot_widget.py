"""
Static plot widget using QChart for detailed view.

Simple, non-interactive plots using the same library as the main EIC graphs.
"""

import logging
import numpy as np
from typing import Optional, Tuple

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPen, QFont, QColor, QPainter, QMouseEvent

logger = logging.getLogger(__name__)


class ZoomableChartView(QChartView):
    """Chart view with zoom controls."""
    
    def __init__(self, chart, parent=None):
        super().__init__(chart, parent)
        self.setRubberBand(QChartView.RectangleRubberBand)
        self._initial_ranges = None
        
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release for zoom reset."""
        if event.button() == Qt.RightButton:
            # Right-click resets zoom to initial state
            if self._initial_ranges:
                x_axis = self.chart().axes(Qt.Horizontal)[0] if self.chart().axes(Qt.Horizontal) else None
                y_axis = self.chart().axes(Qt.Vertical)[0] if self.chart().axes(Qt.Vertical) else None
                if x_axis and y_axis:
                    x_axis.setRange(self._initial_ranges['x_min'], self._initial_ranges['x_max'])
                    y_axis.setRange(self._initial_ranges['y_min'], self._initial_ranges['y_max'])
        super().mouseReleaseEvent(event)
    
    def save_initial_ranges(self):
        """Save the initial axis ranges for reset."""
        x_axis = self.chart().axes(Qt.Horizontal)[0] if self.chart().axes(Qt.Horizontal) else None
        y_axis = self.chart().axes(Qt.Vertical)[0] if self.chart().axes(Qt.Vertical) else None
        if x_axis and y_axis:
            self._initial_ranges = {
                'x_min': x_axis.min(),
                'x_max': x_axis.max(),
                'y_min': y_axis.min(),
                'y_max': y_axis.max()
            }


class StaticPlotWidget(QWidget):
    """
    Plot widget using QChart with zoom functionality.
    
    Features:
    - Drag to zoom in (rubber band selection)
    - Mouse wheel to zoom in/out
    - Right-click to reset zoom
    """
    
    def __init__(self, title: str = "", x_label: str = "", y_label: str = "", parent=None):
        super().__init__(parent)
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI with QChart."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create chart
        self.chart = QChart()
        self.chart.setTitle(self.title)
        self.chart.legend().setVisible(False)
        
        # Create zoomable chart view
        self.chart_view = ZoomableChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        layout.addWidget(self.chart_view)
        
        # Add zoom control buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(5, 0, 5, 2)
        button_layout.setSpacing(2)
        
        # Zoom in button (smaller)
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_in_btn.setMaximumWidth(25)
        self.zoom_in_btn.setMaximumHeight(20)
        self.zoom_in_btn.setToolTip("Zoom In")
        button_layout.addWidget(self.zoom_in_btn)
        
        # Zoom out button (smaller)
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_out_btn.setMaximumWidth(25)
        self.zoom_out_btn.setMaximumHeight(20)
        self.zoom_out_btn.setToolTip("Zoom Out")
        button_layout.addWidget(self.zoom_out_btn)
        
        # Reset button (smaller)
        self.reset_btn = QPushButton("R")
        self.reset_btn.clicked.connect(self.reset_zoom)
        self.reset_btn.setMaximumWidth(25)
        self.reset_btn.setMaximumHeight(20)
        self.reset_btn.setToolTip("Reset Zoom")
        button_layout.addWidget(self.reset_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Create axes (will be configured when plotting)
        self.x_axis = None
        self.y_axis = None
        
        # Set minimum height for better visibility
        self.setMinimumHeight(300)
        
    def clear_plot(self):
        """Clear all data from the plot."""
        self.chart.removeAllSeries()
        if self.x_axis:
            self.chart.removeAxis(self.x_axis)
            self.x_axis = None
        if self.y_axis:
            self.chart.removeAxis(self.y_axis)
            self.y_axis = None
            
    def plot_line(self, x_data: np.ndarray, y_data: np.ndarray, 
                  color: str = "blue", width: int = 2, name: str = ""):
        """
        Plot a simple line.
        
        Args:
            x_data: X coordinates
            y_data: Y coordinates
            color: Line color
            width: Line width
            name: Series name (not shown since legend is hidden)
        """
        try:
            # Convert to numpy arrays and ensure finite values
            x_data = np.asarray(x_data, dtype=np.float64)
            y_data = np.asarray(y_data, dtype=np.float64)
            
            # Filter out non-finite values
            mask = np.isfinite(x_data) & np.isfinite(y_data)
            x_data = x_data[mask]
            y_data = y_data[mask]
            
            if len(x_data) == 0:
                logger.warning(f"No valid data to plot for '{name}'")
                return
                
            # Create line series
            series = QLineSeries()
            series.setName(name)
            
            # Set pen
            pen = QPen(QColor(color))
            pen.setWidth(width)
            series.setPen(pen)
            
            # Add points
            for x, y in zip(x_data, y_data):
                series.append(QPointF(float(x), float(y)))
                
            # Add to chart
            self.chart.addSeries(series)
            
            # Update axes if needed
            self._update_axes()
            
        except Exception as e:
            logger.error(f"Failed to plot line: {e}")
            
    def plot_stems(self, x_data: np.ndarray, y_data: np.ndarray,
                   color: str = "darkblue", width: int = 1):
        """
        Plot vertical lines from zero (stem plot).
        
        Args:
            x_data: X coordinates
            y_data: Y coordinates  
            color: Line color
            width: Line width
        """
        try:
            # Convert to numpy arrays
            x_data = np.asarray(x_data, dtype=np.float64)
            y_data = np.asarray(y_data, dtype=np.float64)
            
            # Filter out non-positive values
            mask = (y_data > 0) & np.isfinite(x_data) & np.isfinite(y_data)
            x_data = x_data[mask]
            y_data = y_data[mask]
            
            if len(x_data) == 0:
                logger.warning("No valid MS data to plot")
                return
                
            # Set pen for all stems
            pen = QPen(QColor(color))
            pen.setWidth(width)
            
            # Create separate series for each stem to avoid connecting lines
            for x, y in zip(x_data, y_data):
                series = QLineSeries()
                series.setPen(pen)
                
                # Add base point and peak point
                series.append(QPointF(float(x), 0.0))
                series.append(QPointF(float(x), float(y)))
                
                # Add to chart
                self.chart.addSeries(series)
            
            # Update axes
            self._update_axes()
            
        except Exception as e:
            logger.error(f"Failed to plot stems: {e}")
            
    def add_vertical_line(self, x_position: float, color: str = "red", 
                         width: int = 1, style: str = "solid"):
        """
        Add a vertical line at specified position.
        
        Args:
            x_position: X coordinate for line
            color: Line color
            width: Line width
            style: Line style (solid, dashed, dotted)
        """
        try:
            # Create line series with a very large Y range
            # The actual range will be clipped by the chart's axes
            series = QLineSeries()
            series.append(QPointF(float(x_position), -1e10))
            series.append(QPointF(float(x_position), 1e10))
            
            # Set pen style (handle rgba colors)
            if color.startswith("rgba"):
                # Parse rgba(r,g,b,a) format
                import re
                match = re.match(r'rgba\((\d+),(\d+),(\d+),([\d.]+)\)', color)
                if match:
                    r, g, b, a = match.groups()
                    qcolor = QColor(int(r), int(g), int(b))
                    qcolor.setAlphaF(float(a))
                    pen = QPen(qcolor)
                else:
                    pen = QPen(QColor(color))
            else:
                pen = QPen(QColor(color))
            pen.setWidth(width)
            
            if style == "dashed":
                pen.setStyle(Qt.DashLine)
            elif style == "dotted":
                pen.setStyle(Qt.DotLine)
            else:
                pen.setStyle(Qt.SolidLine)
                
            series.setPen(pen)
            
            # Add to chart
            self.chart.addSeries(series)
            
            # Attach to axes if they exist
            if self.x_axis and self.y_axis:
                series.attachAxis(self.x_axis)
                series.attachAxis(self.y_axis)
                
        except Exception as e:
            logger.error(f"Failed to add vertical line: {e}")
            
    def _update_axes(self):
        """Update or create axes based on current data."""
        try:
            # Remove old axes if they exist
            if self.x_axis:
                self.chart.removeAxis(self.x_axis)
            if self.y_axis:
                self.chart.removeAxis(self.y_axis)
                
            # Create new axes
            self.x_axis = QValueAxis()
            # Make it clear these are decimal minutes, not min:sec
            if "time" in self.x_label.lower() or "min" in self.x_label.lower():
                self.x_axis.setTitleText(self.x_label + " (decimal)")
            else:
                self.x_axis.setTitleText(self.x_label)
            # Use 2 decimal places for better precision on time axis
            self.x_axis.setLabelFormat("%.2f")
            
            self.y_axis = QValueAxis()
            self.y_axis.setTitleText(self.y_label)
            # Use regular number format - we'll handle scientific notation differently
            self.y_axis.setLabelFormat("%.0f")
            
            # Add axes to chart
            self.chart.addAxis(self.x_axis, Qt.AlignBottom)
            self.chart.addAxis(self.y_axis, Qt.AlignLeft)
            
            # Calculate ranges from all series (excluding vertical lines)
            x_min, x_max = float('inf'), float('-inf')
            y_min, y_max = float('inf'), float('-inf')
            
            for series in self.chart.series():
                points = series.points()
                # Skip vertical lines (they have exactly 2 points with extreme Y values)
                if len(points) == 2 and abs(points[1].y() - points[0].y()) > 1e9:
                    continue
                    
                for point in points:
                    x = point.x()
                    y = point.y()
                    x_min = min(x_min, x)
                    x_max = max(x_max, x)
                    y_min = min(y_min, y)
                    y_max = max(y_max, y)
                    
            # Set ranges with some padding
            if x_min < x_max:
                x_padding = (x_max - x_min) * 0.05
                self.x_axis.setRange(x_min - x_padding, x_max + x_padding)
            else:
                self.x_axis.setRange(0, 1)
                
            if y_min < y_max:
                y_padding = (y_max - y_min) * 0.1
                y_min_padded = max(0, y_min - y_padding)
                y_max_padded = y_max + y_padding
                self.y_axis.setRange(y_min_padded, y_max_padded)
                
                # Choose appropriate format based on value range
                if y_max_padded > 10000 or y_max_padded < 0.01:
                    # For large or very small numbers, we'll use scientific notation
                    # Qt doesn't support ×10^n format directly, so we use e notation
                    # The display will show as 1.0e+6 etc.
                    self.y_axis.setLabelFormat("%.1e")
                else:
                    # For normal range
                    self.y_axis.setLabelFormat("%.0f")
            else:
                self.y_axis.setRange(0, 1)
                
            # Attach all series to axes
            for series in self.chart.series():
                series.attachAxis(self.x_axis)
                series.attachAxis(self.y_axis)
            
            # Save initial ranges for zoom reset
            self.chart_view.save_initial_ranges()
                
        except Exception as e:
            logger.error(f"Failed to update axes: {e}")
            
    def set_title(self, title: str):
        """Update the plot title."""
        self.title = title
        self.chart.setTitle(title)
    
    def zoom_in(self):
        """Zoom in by 25%."""
        if self.x_axis and self.y_axis:
            # Get current ranges
            x_min, x_max = self.x_axis.min(), self.x_axis.max()
            y_min, y_max = self.y_axis.min(), self.y_axis.max()
            
            # Calculate new ranges (zoom in by 25%)
            x_center = (x_min + x_max) / 2
            x_range = (x_max - x_min) * 0.75 / 2
            
            y_center = (y_min + y_max) / 2
            y_range = (y_max - y_min) * 0.75 / 2
            
            # Set new ranges (ensure Y doesn't go below 0)
            self.x_axis.setRange(x_center - x_range, x_center + x_range)
            self.y_axis.setRange(max(0, y_center - y_range), y_center + y_range)
    
    def zoom_out(self):
        """Zoom out by 25%."""
        if self.x_axis and self.y_axis and self.chart_view._initial_ranges:
            # Get current and initial ranges
            x_min, x_max = self.x_axis.min(), self.x_axis.max()
            y_min, y_max = self.y_axis.min(), self.y_axis.max()
            
            initial_x_min = self.chart_view._initial_ranges['x_min']
            initial_x_max = self.chart_view._initial_ranges['x_max']
            initial_y_min = self.chart_view._initial_ranges['y_min']
            initial_y_max = self.chart_view._initial_ranges['y_max']
            
            # Calculate new ranges (zoom out by 25%, but don't exceed initial)
            x_center = (x_min + x_max) / 2
            x_range = (x_max - x_min) * 1.25 / 2
            new_x_min = max(initial_x_min, x_center - x_range)
            new_x_max = min(initial_x_max, x_center + x_range)
            
            y_center = (y_min + y_max) / 2
            y_range = (y_max - y_min) * 1.25 / 2
            new_y_min = max(initial_y_min, y_center - y_range)
            new_y_max = min(initial_y_max, y_center + y_range)
            
            # Set new ranges (ensure Y doesn't go below 0)
            self.x_axis.setRange(new_x_min, new_x_max)
            self.y_axis.setRange(max(0, new_y_min), new_y_max)
    
    def reset_zoom(self):
        """Reset zoom to initial view."""
        if self.chart_view._initial_ranges and self.x_axis and self.y_axis:
            self.x_axis.setRange(
                self.chart_view._initial_ranges['x_min'],
                self.chart_view._initial_ranges['x_max']
            )
            self.y_axis.setRange(
                max(0, self.chart_view._initial_ranges['y_min']), 
                self.chart_view._initial_ranges['y_max']
            )