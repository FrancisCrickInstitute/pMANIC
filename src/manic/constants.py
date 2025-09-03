"""
Central constants and configuration values for MANIC application.

This module consolidates existing magic numbers and configuration
parameters used throughout the application.
"""

from PySide6.QtGui import QColor

# ============================================================================
# Plotting Constants  
# ============================================================================

# Scientific notation threshold for Y-axis
SCIENTIFIC_NOTATION_THRESHOLD = 10000

# Plot rendering parameters
PLOT_DPI = 80  # DPI for matplotlib figures
PLOT_GRID_ALPHA = 0.2  # Grid transparency  
PLOT_GRID_LINEWIDTH = 0.5  # Grid line width

# Plot dimensions
PLOT_FIGURE_WIDTH = 6  # Default figure width
PLOT_FIGURE_HEIGHT = 3  # Default figure height

# Plot margins (for subplot adjustment)
PLOT_MARGIN_LEFT = 0.1
PLOT_MARGIN_RIGHT = 0.95
PLOT_MARGIN_TOP = 0.92
PLOT_MARGIN_BOTTOM = 0.15

# Font sizes
PLOT_TITLE_FONTSIZE = 10
PLOT_LABEL_FONTSIZE = 9
PLOT_TICK_FONTSIZE = 8
PLOT_TITLE_PADDING = 5

# Line and stem widths
PLOT_LINE_WIDTH = 2
PLOT_STEM_WIDTH = 1
PLOT_GUIDELINE_WIDTH = 1
PLOT_AXIS_SPINE_WIDTH = 0.5

# ============================================================================
# Dialog Window Constants
# ============================================================================

# DetailedPlotDialog dimensions
DETAILED_DIALOG_WIDTH = 1400
DETAILED_DIALOG_HEIGHT = 1100
DETAILED_DIALOG_MIN_WIDTH = 800
DETAILED_DIALOG_MIN_HEIGHT = 600
DETAILED_DIALOG_SCREEN_RATIO = 0.95  # Maximum percentage of screen size

# Plot heights in detailed view
DETAILED_EIC_HEIGHT = 450
DETAILED_TIC_HEIGHT = 450
DETAILED_MS_HEIGHT = 350
DETAILED_EIC_MIN_HEIGHT = 250
DETAILED_TIC_MIN_HEIGHT = 250
DETAILED_MS_MIN_HEIGHT = 200

# ============================================================================
# UI Component Constants
# ============================================================================

# Toolbar dimensions
TOOLBAR_MAX_HEIGHT = 30
TOOLBAR_BUTTON_PADDING = 3
TOOLBAR_BUTTON_MARGIN = 1
TOOLBAR_SPACING = 2
TOOLBAR_MARGINS = 2

# Button hover/pressed opacity
BUTTON_HOVER_OPACITY = 0.1
BUTTON_PRESSED_OPACITY = 0.2
BUTTON_CHECKED_BORDER_OPACITY = 0.5

# ============================================================================
# Data Processing Constants
# ============================================================================

# Mass tolerance defaults
DEFAULT_MASS_TOLERANCE = 0.2  # Da
MS_TIME_TOLERANCE = 0.1  # minutes for MS extraction

# Time windows  
DEFAULT_RT_WINDOW = 0.2  # minutes (half-window)

# ============================================================================
# Performance Constants
# ============================================================================

# Plot rendering
PLOT_MIN_HEIGHT = 200  # Minimum height for plot widgets

# Transparency levels
GUIDELINE_ALPHA = 0.5  # Transparency for guide lines

# ============================================================================
# Application Constants
# ============================================================================

# Font family
FONT = "Verdana"

# Status indicator colors
RED = QColor(215, 50, 50, 128)
GREEN = QColor(102, 215, 102, 128)