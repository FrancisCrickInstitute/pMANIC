"""
Matplotlib-based plot widget for enhanced data visualization.

This module provides a high-performance plotting widget using matplotlib
with optimized rendering and professional scientific notation support.
Key features include custom zoom controls, responsive layouts, and
efficient batch rendering for improved performance.
"""

import logging
import numpy as np
from typing import Optional
from contextlib import contextmanager

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QFrame
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPalette, QColor

# Configure matplotlib for Qt5 integration with performance optimizations
import matplotlib
matplotlib.use('Qt5Agg')
# Configure matplotlib rendering parameters for optimal performance
matplotlib.rcParams['figure.dpi'] = 80  # Optimized DPI for responsive rendering
matplotlib.rcParams['figure.autolayout'] = False  # Manual layout control for performance
matplotlib.rcParams['axes.unicode_minus'] = False  # Simplified minus sign rendering

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


@contextmanager
def matplotlib_cleanup():
    """Context manager to ensure matplotlib resources are properly cleaned up."""
    try:
        yield
    finally:
        # Force garbage collection of matplotlib objects
        import gc
        gc.collect()
        # Close any lingering figures
        plt.close('all')


class CompactNavigationToolbar(QWidget):
    """Streamlined navigation toolbar with essential plot controls.
    
    Provides a minimal, aesthetically pleasing interface for plot interaction
    with zoom, pan, and reset functionality.
    """
    
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
        
        # Configure toolbar with clean white background
        self.setStyleSheet("background-color: white;")
        
        # Define consistent button styling with hover and toggle states
        button_style = """
            QToolButton {
                border: none;
                padding: 3px;
                margin: 1px;
                background-color: transparent;
                border-radius: 3px;
                color: black;
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
        
        # Reset button: returns plot to original view state
        self.home_btn = QToolButton()
        self.home_btn.setText("↻")  # Circular arrow for reset
        self.home_btn.setToolTip("Reset view")
        self.home_btn.clicked.connect(self.toolbar.home)
        self.home_btn.setStyleSheet(button_style)
        layout.addWidget(self.home_btn)
        
        # Drag button: enables plot panning functionality
        self.pan_btn = QToolButton()
        self.pan_btn.setText("✋")
        self.pan_btn.setToolTip("Drag")
        self.pan_btn.setCheckable(True)
        self.pan_btn.clicked.connect(self._on_pan)
        self.pan_btn.setStyleSheet(button_style)
        layout.addWidget(self.pan_btn)
        
        # Zoom button: activates rectangular zoom selection
        self.zoom_btn = QToolButton()
        self.zoom_btn.setText("🔍")
        self.zoom_btn.setToolTip("Zoom to rectangle")
        self.zoom_btn.setCheckable(True)
        self.zoom_btn.clicked.connect(self._on_zoom)
        self.zoom_btn.setStyleSheet(button_style)
        layout.addWidget(self.zoom_btn)
        
        layout.addStretch()
        
        # Constrain toolbar height for space efficiency
        self.setMaximumHeight(30)
        
    def _on_pan(self):
        """Toggle plot panning mode with exclusive button state management."""
        if self.pan_btn.isChecked():
            self.zoom_btn.setChecked(False)
            self.toolbar.pan()
        else:
            self.toolbar.pan()  # Toggle off
            
    def _on_zoom(self):
        """Toggle rectangular zoom mode with exclusive button state management."""
        if self.zoom_btn.isChecked():
            self.pan_btn.setChecked(False)
            self.toolbar.zoom()
        else:
            self.toolbar.zoom()  # Toggle off
    
    def cleanup(self):
        """Cleanup toolbar resources."""
        if hasattr(self, 'toolbar') and self.toolbar:
            self.toolbar = None


class MatplotlibPlotWidget(QWidget):
    """
    Advanced scientific plotting widget with matplotlib backend.
    
    Provides professional-grade visualization capabilities including:
    - Integrated navigation controls for interactive exploration
    - Automatic scientific notation for large numerical ranges
    - High-precision line and marker positioning
    - Optimized batch rendering for performance
    - Responsive layout adaptation
    """
    
    def __init__(self, title: str = "", x_label: str = "", y_label: str = "", parent=None):
        super().__init__(parent)
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        
        # Initialize data storage for plot management
        self.data_lines = []
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI with matplotlib figure."""
        # Apply consistent white background styling
        self.setStyleSheet("background-color: white;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Initialize matplotlib figure with performance-optimized parameters
        self.figure = Figure(figsize=(6, 3), dpi=80, tight_layout=False, facecolor='white', edgecolor='white')
        self.canvas = FigureCanvas(self.figure)
        # Ensure canvas maintains consistent white background
        self.canvas.setStyleSheet("background-color: white; border: none;")
        
        # Configure subplot with optimized margin parameters
        self.ax = self.figure.add_subplot(111, facecolor='white')
        self.figure.subplots_adjust(left=0.1, right=0.95, top=0.92, bottom=0.15)
        
        # Configure minimal axis styling for clean appearance
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['left'].set_linewidth(0.5)
        self.ax.spines['bottom'].set_linewidth(0.5)
        
        # Initialize plot labels and title
        self.ax.set_title(self.title, fontsize=10, pad=5)
        self.ax.set_xlabel(self.x_label, fontsize=9)
        self.ax.set_ylabel(self.y_label, fontsize=9)
        
        # Apply subtle grid styling for reference
        self.ax.grid(True, alpha=0.2, linestyle='-', linewidth=0.5)
        self.ax.tick_params(labelsize=8)
        
        # Integrate custom navigation toolbar
        self.toolbar = CompactNavigationToolbar(self.canvas, self)
        
        # Add widgets to layout
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        # Define minimum widget dimensions
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
        
        # Restore axis styling configuration
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['left'].set_linewidth(0.5)
        self.ax.spines['bottom'].set_linewidth(0.5)
        # Defer rendering until data is loaded
        
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
            # Ensure data is in numpy array format
            x_data = np.asarray(x_data, dtype=np.float64)
            y_data = np.asarray(y_data, dtype=np.float64)
            
            # Remove invalid data points
            mask = np.isfinite(x_data) & np.isfinite(y_data)
            x_data = x_data[mask]
            y_data = y_data[mask]
            
            if len(x_data) == 0:
                logger.warning(f"No valid data to plot for '{name}'")
                return
            
            # Store data for later reference
            self.data_lines.append((x_data, y_data))
            
            # Parse RGBA color format if provided
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
            
            # Defer canvas update for batch rendering
            
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
            # Ensure data is in numpy array format
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
            
            # Defer canvas update for batch rendering
            
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
            # Parse RGBA color format if provided
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
            
            # Defer canvas update for batch rendering
            
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
    
    def cleanup(self):
        """Properly cleanup matplotlib resources to prevent memory leaks."""
        try:
            # Clear the axes
            if hasattr(self, 'ax') and self.ax:
                self.ax.clear()
                self.ax = None
            
            # Clear and close the figure
            if hasattr(self, 'figure') and self.figure:
                self.figure.clear()
                plt.close(self.figure)
                self.figure = None
            
            # Clear canvas reference
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas = None
            
            # Clear toolbar reference
            if hasattr(self, 'toolbar') and self.toolbar:
                if hasattr(self.toolbar, 'cleanup'):
                    self.toolbar.cleanup()
                self.toolbar = None
            
            # Clear data storage
            if hasattr(self, 'data_lines'):
                self.data_lines = []
            
            logger.debug("Matplotlib resources cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during matplotlib cleanup: {e}")
    
    def closeEvent(self, event):
        """Handle widget close event."""
        self.cleanup()
        super().closeEvent(event)
    
    def __del__(self):
        """Destructor to ensure cleanup on deletion."""
        self.cleanup()