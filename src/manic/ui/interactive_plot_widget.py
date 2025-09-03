"""
Interactive plot widget for detailed view plots.

Provides zooming, panning, and crosshair functionality for EIC, TIC, and MS plots.
"""

import logging
from typing import Optional, List, Tuple
import numpy as np

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    pg = None

logger = logging.getLogger(__name__)


class InteractivePlotWidget(QWidget):
    """
    Interactive plot widget with zoom, pan, and crosshair capabilities.
    
    Signals:
        point_clicked: Emitted when user clicks on plot (x, y)
        crosshair_moved: Emitted when crosshair moves (x, y)
    """
    
    point_clicked = Signal(float, float)
    crosshair_moved = Signal(float, float)
    
    def __init__(self, title: str, x_label: str = "X", y_label: str = "Y", parent=None):
        super().__init__(parent)
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        
        # Plot data storage
        self._plot_data = []  # List of (x_data, y_data, pen, name) tuples
        self._vertical_lines = []  # List of vertical line positions
        self._current_data = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the plot widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        # Title label
        title_label = QLabel(self.title)
        title_label.setFont(QFont("Arial", 11, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Create plot widget
        self.plot_widget = self._create_plot_widget()
        layout.addWidget(self.plot_widget)
        
        # Set size policy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(200)
        
    def __del__(self):
        """Cleanup when widget is destroyed"""
        self._cleanup_connections()
        
    def _cleanup_connections(self):
        """Clean up signal connections to prevent crashes"""
        try:
            if PYQTGRAPH_AVAILABLE and hasattr(self, 'plot_widget') and self.plot_widget:
                scene = self.plot_widget.scene()
                if scene and hasattr(self, '_mouse_moved_connection'):
                    scene.sigMouseMoved.disconnect(self._mouse_moved_connection)
                if scene and hasattr(self, '_mouse_clicked_connection'):
                    scene.sigMouseClicked.disconnect(self._mouse_clicked_connection)
        except Exception as e:
            logger.debug(f"Error cleaning up connections: {e}")
        
    def _create_plot_widget(self):
        """Create the actual plot widget based on available libraries."""
        if PYQTGRAPH_AVAILABLE:
            return self._create_pyqtgraph_widget()
        else:
            logger.warning("PyQtGraph not available, using basic plot widget")
            return self._create_basic_widget()
    
    def _create_pyqtgraph_widget(self):
        """Create PyQtGraph-based interactive plot."""
        plot_widget = pg.PlotWidget()
        
        # Configure plot appearance
        plot_widget.setLabel('left', self.y_label)
        plot_widget.setLabel('bottom', self.x_label)
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        plot_widget.setBackground('w')  # White background
        
        # Enable mouse interaction
        plot_widget.getViewBox().setMouseMode(pg.ViewBox.RectMode)  # Rectangle zoom by default
        
        # Add crosshair
        self._setup_crosshair(plot_widget)
        
        return plot_widget
    
    def _create_basic_widget(self):
        """Create basic fallback plot widget."""
        # Fallback to a simple label if PyQtGraph not available
        label = QLabel("Plot widget (PyQtGraph not available)")
        label.setStyleSheet("border: 1px solid gray; background: white;")
        label.setAlignment(Qt.AlignCenter)
        return label
    
    def _setup_crosshair(self, plot_widget):
        """Setup crosshair for PyQtGraph plot."""
        if not PYQTGRAPH_AVAILABLE:
            return
        
        try:
            # Disconnect any existing signals to prevent multiple connections
            if hasattr(self, '_mouse_moved_connection'):
                plot_widget.scene().sigMouseMoved.disconnect(self._mouse_moved_connection)
            if hasattr(self, '_mouse_clicked_connection'):
                plot_widget.scene().sigMouseClicked.disconnect(self._mouse_clicked_connection)
                
            # Create new crosshair lines
            self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('r', width=1, style=Qt.DashLine))
            self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('r', width=1, style=Qt.DashLine))
            
            # Add to plot with error checking
            if plot_widget and plot_widget.getViewBox():
                plot_widget.addItem(self.v_line, ignoreBounds=True)
                plot_widget.addItem(self.h_line, ignoreBounds=True)
                
                # Connect mouse movement to crosshair - store connections for cleanup
                self._mouse_moved_connection = plot_widget.scene().sigMouseMoved.connect(self._update_crosshair)
                self._mouse_clicked_connection = plot_widget.scene().sigMouseClicked.connect(self._on_mouse_click)
            
        except Exception as e:
            logger.debug(f"Failed to setup crosshair: {e}")
            self.v_line = None
            self.h_line = None
    
    def _update_crosshair(self, pos):
        """Update crosshair position."""
        if not PYQTGRAPH_AVAILABLE or not hasattr(self, 'v_line') or not hasattr(self, 'h_line'):
            return
        
        # Check if crosshair lines are still valid
        if not self.v_line or not self.h_line:
            return
            
        try:
            # Check if plot widget is still valid
            if not hasattr(self, 'plot_widget') or not self.plot_widget:
                return
                
            view_box = self.plot_widget.getViewBox()
            if not view_box:
                return
                
            # Convert scene position to plot coordinates
            mouse_point = view_box.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()
            
            # Update crosshair lines
            self.v_line.setPos(x)
            self.h_line.setPos(y)
            
            # Emit signal
            self.crosshair_moved.emit(x, y)
            
        except Exception as e:
            logger.debug(f"Crosshair update error: {e}")
    
    def _on_mouse_click(self, event):
        """Handle mouse click events."""
        if not PYQTGRAPH_AVAILABLE:
            return
            
        try:
            if event.button() == Qt.LeftButton:
                # Check if plot widget is still valid
                if not hasattr(self, 'plot_widget') or not self.plot_widget:
                    return
                    
                view_box = self.plot_widget.getViewBox()
                if not view_box:
                    return
                    
                pos = event.scenePos()
                mouse_point = view_box.mapSceneToView(pos)
                x, y = mouse_point.x(), mouse_point.y()
                self.point_clicked.emit(x, y)
        except Exception as e:
            logger.debug(f"Mouse click error: {e}")
    
    def clear_plot(self):
        """Clear all plot data."""
        try:
            # Clean up existing connections first
            self._cleanup_connections()
            
            if PYQTGRAPH_AVAILABLE and hasattr(self, 'plot_widget') and self.plot_widget:
                # Clear the plot
                self.plot_widget.clear()
                
                # Recreate crosshair with fresh connections
                self._setup_crosshair(self.plot_widget)
            
            # Clear internal data
            self._plot_data.clear()
            self._vertical_lines.clear()
            
        except Exception as e:
            logger.debug(f"Error clearing plot: {e}")
    
    def plot_line(self, x_data: np.ndarray, y_data: np.ndarray, 
                  pen_color: str = 'blue', line_width: int = 2, name: str = ""):
        """
        Plot a line on the widget.
        
        Args:
            x_data: X coordinates
            y_data: Y coordinates  
            pen_color: Line color
            line_width: Line width
            name: Name for the plot item
        """
        if not PYQTGRAPH_AVAILABLE:
            return
            
        try:
            # Convert to numpy arrays
            x_data = np.asarray(x_data, dtype=np.float64)
            y_data = np.asarray(y_data, dtype=np.float64)
            
            # Check for empty data
            if len(x_data) == 0 or len(y_data) == 0:
                logger.warning(f"Empty data for plot '{name}'")
                return None
            
            # Create pen
            pen = pg.mkPen(color=pen_color, width=line_width)
            
            # Plot the line (PyQtGraph handles NaN values for line breaks)
            plot_item = self.plot_widget.plot(x_data, y_data, pen=pen, name=name, connect='finite')
            
            # Store data for reference
            self._plot_data.append((x_data, y_data, pen, name))
            
            return plot_item
            
        except Exception as e:
            logger.error(f"Failed to plot line: {e}")
            return None
    
    def plot_scatter(self, x_data: np.ndarray, y_data: np.ndarray,
                     symbol: str = 'o', symbol_size: int = 5, pen_color: str = 'blue',
                     brush_color: str = 'blue', name: str = ""):
        """
        Plot scatter points on the widget.
        
        Args:
            x_data: X coordinates
            y_data: Y coordinates
            symbol: Point symbol ('o', 's', 't', etc.)
            symbol_size: Size of symbols
            pen_color: Outline color
            brush_color: Fill color
            name: Name for the plot item
        """
        if not PYQTGRAPH_AVAILABLE:
            return
            
        try:
            # Convert to numpy arrays
            x_data = np.asarray(x_data)
            y_data = np.asarray(y_data)
            
            # Plot the scatter
            plot_item = self.plot_widget.plot(
                x_data, y_data,
                pen=None,
                symbol=symbol,
                symbolSize=symbol_size,
                symbolPen=pen_color,
                symbolBrush=brush_color,
                name=name
            )
            
            # Store data for reference
            self._plot_data.append((x_data, y_data, None, name))
            
            return plot_item
            
        except Exception as e:
            logger.error(f"Failed to plot scatter: {e}")
            return None
    
    def add_vertical_line(self, x_position: float, pen_color: str = 'red', 
                         line_width: int = 2, line_style=Qt.SolidLine):
        """
        Add a vertical line to the plot.
        
        Args:
            x_position: X coordinate for the vertical line
            pen_color: Line color
            line_width: Line width
            line_style: Line style (Qt.SolidLine, Qt.DashLine, etc.)
        """
        if not PYQTGRAPH_AVAILABLE:
            return
            
        try:
            pen = pg.mkPen(color=pen_color, width=line_width, style=line_style)
            v_line = pg.InfiniteLine(pos=x_position, angle=90, pen=pen)
            self.plot_widget.addItem(v_line)
            self._vertical_lines.append((x_position, v_line))
            return v_line
            
        except Exception as e:
            logger.error(f"Failed to add vertical line: {e}")
            return None
    
    def set_x_range(self, x_min: float, x_max: float):
        """Set the X-axis range."""
        if PYQTGRAPH_AVAILABLE:
            self.plot_widget.setXRange(x_min, x_max)
    
    def set_y_range(self, y_min: float, y_max: float):
        """Set the Y-axis range."""
        if PYQTGRAPH_AVAILABLE:
            self.plot_widget.setYRange(y_min, y_max)
    
    def auto_range(self):
        """Auto-range both axes to fit data."""
        try:
            if PYQTGRAPH_AVAILABLE and hasattr(self, 'plot_widget') and self.plot_widget:
                self.plot_widget.autoRange()
        except Exception as e:
            logger.debug(f"Error auto-ranging plot: {e}")
    
    def set_title(self, title: str):
        """Update the plot title."""
        self.title = title
        # Find and update the title label
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if isinstance(widget, QLabel) and widget.font().bold():
                widget.setText(title)
                break
    
    def get_plot_data(self) -> List[Tuple[np.ndarray, np.ndarray, str]]:
        """Get all plotted data as (x_data, y_data, name) tuples."""
        return [(x, y, name) for x, y, pen, name in self._plot_data]