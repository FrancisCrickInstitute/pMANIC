"""
Central constants and configuration values for MANIC application.

This module consolidates existing magic numbers and configuration
parameters used throughout the application.
"""

import sys
from PySide6.QtGui import QColor, QFont

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
DETAILED_DIALOG_HEIGHT = 1300  # Further increased default height for Windows
DETAILED_DIALOG_MIN_WIDTH = 800
DETAILED_DIALOG_MIN_HEIGHT = 800  # Further increased minimum height for Windows
DETAILED_DIALOG_SCREEN_RATIO = 0.9  # Reduced to leave more space for taskbars/menus

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

# RT window buffer for auto-reload feature
# Added to max(loffset, roffset) when calculating minimum RT window
# This provides margin to prevent frequent reloads on minor adjustments
DEFAULT_RT_WINDOW_BUFFER = 0.1  # minutes

# Peak height validation
DEFAULT_MIN_PEAK_HEIGHT_RATIO = 0.05  # Fraction of internal standard height for minimum peak validation

# Integration method options
DEFAULT_USE_LEGACY_INTEGRATION = False  # Time-based by default (scientifically accurate)

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
# ============================================================================
# Cross-Platform Font Configuration
# ============================================================================

def get_system_font():
    """
    Get the appropriate system font for cross-platform consistency.
    
    Returns the optimal font family for the current platform with consistent sizing.
    No size multipliers are applied to maintain identical appearance across platforms.
    """
    if sys.platform == "win32":
        # Windows: Use Arial with smaller scaling for better density
        return "Arial", 0.85  # family, size_multiplier (15% smaller)
    elif sys.platform == "darwin":
        # macOS: Use Helvetica as it's always available on macOS
        return "Helvetica", 1.0
    else:
        # Linux: Use DejaVu Sans or system default
        return "DejaVu Sans", 1.0

def create_font(base_size: int, weight: QFont.Weight = QFont.Weight.Normal, family: str = None) -> QFont:
    """
    Create a QFont with cross-platform compatibility.
    
    Args:
        base_size: Base font size (will be adjusted per platform)
        weight: Font weight (Normal, Bold, etc.)
        family: Optional specific font family override
        
    Returns:
        QFont configured for the current platform
    """
    if family is None:
        font_family, size_multiplier = get_system_font()
    else:
        font_family = family
        _, size_multiplier = get_system_font()
    
    # Adjust size for platform
    adjusted_size = int(base_size * size_multiplier)
    
    font = QFont(font_family, adjusted_size)
    font.setWeight(weight)
    
    # Platform-specific rendering hints
    if sys.platform == "win32":
        font.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
    elif sys.platform == "darwin":
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    
    return font

# Legacy font constant for backward compatibility
FONT_FAMILY, FONT_SIZE_MULTIPLIER = get_system_font()
FONT = FONT_FAMILY

# Status indicator colors
RED = QColor(215, 50, 50, 128)
GREEN = QColor(102, 215, 102, 128)