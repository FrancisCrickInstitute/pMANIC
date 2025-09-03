"""
Matplotlib-based plot widget for detailed view.

Provides interactive plots with proper scientific notation and zoom controls.
"""

import logging
import numpy as np
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QFrame
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

# Import matplotlib with Qt backend - optimize imports
import matplotlib
matplotlib.use('Qt5Agg')
# Set non-interactive backend options for speed
matplotlib.rcParams['figure.dpi'] = 80  # Lower DPI for faster rendering
matplotlib.rcParams['figure.autolayout'] = False  # Disable auto layout
matplotlib.rcParams['axes.unicode_minus'] = False  # Faster minus sign rendering

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)


class CompactNavigationToolbar(QWidget):
    """Compact, modern-looking navigation toolbar for matplotlib plots."""
    
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.toolbar = NavigationToolbar(canvas, self)
        self.toolbar.setVisible(False)  # Hide the original toolbar
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Create a compact toolbar with essential buttons."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Set white background for toolbar
        self.setStyleSheet("background-color: white;")
        
        # Create compact buttons
        button_style = """
            QToolButton {
                border: none;
                padding: 3px;
                margin: 1px;
                background-color: transparent;
                border-radius: 3px;
            }
            QToolButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
            QToolButton:pressed {
                background-color: rgba(0, 0, 0, 0.2);
            }
            QToolButton:checked {
                background-color: rgba(0, 120, 215, 0.2);
                border: 1px solid rgba(0, 120, 215, 0.5);
            }
        """
        
        # Home/Reset button with circular arrow
        self.home_btn = QToolButton()
        self.home_btn.setText("↻")  # Circular arrow for reset
        self.home_btn.setToolTip("Reset view")
        self.home_btn.clicked.connect(self.toolbar.home)
        self.home_btn.setStyleSheet(button_style)
        layout.addWidget(self.home_btn)
        
        # Drag button (formerly Pan)
        self.pan_btn = QToolButton()
        self.pan_btn.setText("✋")
        self.pan_btn.setToolTip("Drag")
        self.pan_btn.setCheckable(True)
        self.pan_btn.clicked.connect(self._on_pan)
        self.pan_btn.setStyleSheet(button_style)
        layout.addWidget(self.pan_btn)
        
        # Zoom button
        self.zoom_btn = QToolButton()
        self.zoom_btn.setText("🔍")
        self.zoom_btn.setToolTip("Zoom to rectangle")
        self.zoom_btn.setCheckable(True)
        self.zoom_btn.clicked.connect(self._on_zoom)
        self.zoom_btn.setStyleSheet(button_style)
        layout.addWidget(self.zoom_btn)
        
        layout.addStretch()
        
        # Set a maximum height for compactness
        self.setMaximumHeight(30)
        
    def _on_pan(self):
        """Toggle pan mode."""
        if self.pan_btn.isChecked():
            self.zoom_btn.setChecked(False)
            self.toolbar.pan()
        else:
            self.toolbar.pan()  # Toggle off
            
    def _on_zoom(self):
        """Toggle zoom mode."""
        if self.zoom_btn.isChecked():
            self.pan_btn.setChecked(False)
            self.toolbar.zoom()
        else:
            self.toolbar.zoom()  # Toggle off


class MatplotlibPlotWidget(QWidget):
    """
    Plot widget using matplotlib for better scientific plotting.
    
    Features:
    - Built-in navigation toolbar (zoom, pan, home, save)
    - Proper scientific notation
    - Precise line positioning
    """
    
    def __init__(self, title: str = "", x_label: str = "", y_label: str = "", parent=None):
        super().__init__(parent)
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        
        # Store data for retention time calculation
        self.data_lines = []
        
        # Set widget background to white
        self.setStyleSheet("background-color: white;")
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI with matplotlib figure."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create matplotlib figure with optimizations
        # Smaller figure size and no tight_layout for faster creation
        self.figure = Figure(figsize=(6, 3), dpi=80, tight_layout=False, facecolor='white')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color: white;")
        
        # Create subplot with adjusted margins for speed
        self.ax = self.figure.add_subplot(111, facecolor='white')
        self.figure.subplots_adjust(left=0.1, right=0.95, top=0.92, bottom=0.15)
        
        # Remove borders/spines
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['left'].set_linewidth(0.5)
        self.ax.spines['bottom'].set_linewidth(0.5)
        
        # Set initial labels and title
        self.ax.set_title(self.title, fontsize=10, pad=5)
        self.ax.set_xlabel(self.x_label, fontsize=9)
        self.ax.set_ylabel(self.y_label, fontsize=9)
        
        # Configure grid with minimal style
        self.ax.grid(True, alpha=0.2, linestyle='-', linewidth=0.5)
        self.ax.tick_params(labelsize=8)
        
        # Create and add compact toolbar
        self.toolbar = CompactNavigationToolbar(self.canvas, self)
        
        # Add widgets to layout
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        # Set minimum height
        self.setMinimumHeight(200)
        
    def clear_plot(self):
        """Clear all data from the plot."""
        self.ax.clear()
        self.data_lines = []
        self.ax.set_facecolor('white')
        self.ax.set_title(self.title, fontsize=10, pad=5)
        self.ax.set_xlabel(self.x_label, fontsize=9)
        self.ax.set_ylabel(self.y_label, fontsize=9)
        self.ax.grid(True, alpha=0.2, linestyle='-', linewidth=0.5)
        self.ax.tick_params(labelsize=8)
        
        # Re-apply spine settings after clear
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['left'].set_linewidth(0.5)
        self.ax.spines['bottom'].set_linewidth(0.5)
        # Don't draw yet - wait for data
        
    def plot_line(self, x_data: np.ndarray, y_data: np.ndarray, 
                  color: str = "blue", width: int = 2, name: str = ""):
        """
        Plot a line.
        
        Args:
            x_data: X coordinates
            y_data: Y coordinates
            color: Line color (matplotlib format)
            width: Line width
            name: Series name for legend
        """
        try:
            # Convert to numpy arrays
            x_data = np.asarray(x_data, dtype=np.float64)
            y_data = np.asarray(y_data, dtype=np.float64)
            
            # Filter out non-finite values
            mask = np.isfinite(x_data) & np.isfinite(y_data)
            x_data = x_data[mask]
            y_data = y_data[mask]
            
            if len(x_data) == 0:
                logger.warning(f"No valid data to plot for '{name}'")
                return
            
            # Store data for later reference
            self.data_lines.append((x_data, y_data))
            
            # Handle rgba colors
            if color.startswith("rgba"):
                import re
                match = re.match(r'rgba\((\d+),(\d+),(\d+),([\d.]+)\)', color)
                if match:
                    r, g, b, a = match.groups()
                    color = (int(r)/255, int(g)/255, int(b)/255, float(a))
            elif color.startswith("#"):
                # Convert hex to matplotlib format
                pass  # matplotlib handles hex colors natively
                
            # Plot the line
            line = self.ax.plot(x_data, y_data, color=color, linewidth=width, 
                               label=name if name else None)[0]
            
            # Update axes limits
            self.ax.relim()
            self.ax.autoscale_view()
            
            # Use scientific notation for large numbers
            if np.max(np.abs(y_data)) > 10000:
                self.ax.ticklabel_format(axis='y', style='scientific', scilimits=(0,0))
                self.ax.yaxis.get_offset_text().set_fontsize(8)
            
            # Don't draw yet - wait for finalize_plot()
            
        except Exception as e:
            logger.error(f"Failed to plot line: {e}")
            
    def plot_stems(self, x_data: np.ndarray, y_data: np.ndarray,
                   color: str = "darkblue", width: int = 1):
        """
        Plot vertical lines from zero (stem plot) for MS data.
        
        Args:
            x_data: X coordinates (m/z values)
            y_data: Y coordinates (intensities)
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
            
            # Use matplotlib stem plot
            markerline, stemlines, baseline = self.ax.stem(x_data, y_data, 
                                                           basefmt=' ')
            
            # Set colors and widths
            markerline.set_color(color)
            markerline.set_markersize(0)  # Hide markers
            stemlines.set_color(color)
            stemlines.set_linewidth(width)
            
            # Ensure Y axis starts at 0
            y_min, y_max = self.ax.get_ylim()
            self.ax.set_ylim(0, y_max * 1.1)
            
            # Use scientific notation for large numbers
            if y_max > 10000:
                self.ax.ticklabel_format(axis='y', style='scientific', scilimits=(0,0))
                self.ax.yaxis.get_offset_text().set_fontsize(8)
            
            # Don't draw yet - wait for finalize_plot()
            
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
            # Handle rgba colors
            if color.startswith("rgba"):
                import re
                match = re.match(r'rgba\((\d+),(\d+),(\d+),([\d.]+)\)', color)
                if match:
                    r, g, b, a = match.groups()
                    color = (int(r)/255, int(g)/255, int(b)/255, float(a))
            
            # Convert style to matplotlib format
            linestyle = '-'
            if style == "dashed":
                linestyle = '--'
            elif style == "dotted":
                linestyle = ':'
            
            # Add vertical line
            self.ax.axvline(x=x_position, color=color, linewidth=width, 
                           linestyle=linestyle, alpha=None if not isinstance(color, tuple) else color[3])
            
            # Don't draw yet - wait for finalize_plot()
            
        except Exception as e:
            logger.error(f"Failed to add vertical line: {e}")
            
    def set_title(self, title: str):
        """Update the plot title."""
        self.title = title
        self.ax.set_title(title, fontsize=10, pad=5)
        # Don't draw yet
        
    def finalize_plot(self):
        """Finalize plot after all data is added - single draw call for speed."""
        # Ensure grid is visible
        self.ax.grid(True, alpha=0.2, linestyle='-', linewidth=0.5)
        
        # For time axis, format nicely
        if "time" in self.x_label.lower() or "min" in self.x_label.lower():
            # Format x-axis to show clear decimal minutes
            from matplotlib.ticker import FormatStrFormatter
            self.ax.xaxis.set_major_formatter(FormatStrFormatter('%.2f'))
        
        # Single draw call for all updates - much faster
        self.canvas.draw()