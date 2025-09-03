"""
Utility functions for plotting operations.

This module provides common utilities for color parsing, data validation,
and plot formatting used across the application.
"""

import re
import logging
from typing import Union, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)


def parse_color(color_str: str) -> Union[str, Tuple[float, float, float, float]]:
    """
    Parse color string to matplotlib-compatible format.
    
    Supports multiple color formats:
    - Hex colors: '#RRGGBB'
    - RGBA strings: 'rgba(r,g,b,a)'
    - Named colors: 'red', 'blue', etc.
    
    Args:
        color_str: Color specification string
        
    Returns:
        Either the original string (for hex/named colors) or 
        a tuple of (r, g, b, a) values normalized to 0-1 range
        
    Examples:
        >>> parse_color('#FF0000')
        '#FF0000'
        >>> parse_color('rgba(255,0,0,0.5)')
        (1.0, 0.0, 0.0, 0.5)
    """
    if color_str.startswith("rgba"):
        # Parse rgba(r,g,b,a) format
        match = re.match(r'rgba\((\d+),(\d+),(\d+),([\d.]+)\)', color_str)
        if match:
            r, g, b, a = match.groups()
            return (int(r)/255.0, int(g)/255.0, int(b)/255.0, float(a))
        else:
            logger.warning(f"Invalid RGBA color format: {color_str}")
            return color_str
    else:
        # Return as-is for hex colors and named colors
        return color_str


def validate_data_arrays(x_data: np.ndarray, y_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Validate and clean data arrays for plotting.
    
    Removes non-finite values and ensures arrays are properly formatted.
    
    Args:
        x_data: X-axis data array
        y_data: Y-axis data array
        
    Returns:
        Tuple of cleaned (x_data, y_data) arrays
        
    Raises:
        ValueError: If arrays have incompatible shapes or no valid data
    """
    # Convert to numpy arrays
    x_data = np.asarray(x_data, dtype=np.float64)
    y_data = np.asarray(y_data, dtype=np.float64)
    
    # Check array shapes
    if x_data.shape != y_data.shape:
        raise ValueError(f"Array shape mismatch: x={x_data.shape}, y={y_data.shape}")
    
    # Filter out non-finite values
    mask = np.isfinite(x_data) & np.isfinite(y_data)
    x_clean = x_data[mask]
    y_clean = y_data[mask]
    
    if len(x_clean) == 0:
        raise ValueError("No valid data points after filtering")
    
    return x_clean, y_clean


def format_scientific_notation(value: float, threshold: float = 10000) -> str:
    """
    Format number with appropriate scientific notation.
    
    Args:
        value: Numeric value to format
        threshold: Threshold above which to use scientific notation
        
    Returns:
        Formatted string representation
    """
    if abs(value) >= threshold or (value != 0 and abs(value) < 0.01):
        return f"{value:.2e}"
    elif value == int(value):
        return f"{int(value)}"
    else:
        return f"{value:.2f}"


def calculate_axis_limits(data: np.ndarray, padding: float = 0.05) -> Tuple[float, float]:
    """
    Calculate appropriate axis limits with padding.
    
    Args:
        data: Data array for axis
        padding: Fractional padding to add (0.05 = 5%)
        
    Returns:
        Tuple of (min_limit, max_limit)
    """
    if len(data) == 0:
        return (0, 1)
    
    data_min = np.min(data)
    data_max = np.max(data)
    
    if data_min == data_max:
        # Handle single value case
        if data_min == 0:
            return (-1, 1)
        else:
            return (data_min * 0.9, data_max * 1.1)
    
    data_range = data_max - data_min
    pad = data_range * padding
    
    return (data_min - pad, data_max + pad)


def decimate_data(x_data: np.ndarray, y_data: np.ndarray, 
                  max_points: int = 10000) -> Tuple[np.ndarray, np.ndarray]:
    """
    Decimate data for responsive plotting of large datasets.
    
    Uses intelligent decimation to preserve data features while reducing point count.
    
    Args:
        x_data: X-axis data
        y_data: Y-axis data  
        max_points: Maximum number of points to retain
        
    Returns:
        Tuple of decimated (x_data, y_data) arrays
    """
    n_points = len(x_data)
    
    if n_points <= max_points:
        return x_data, y_data
    
    # Calculate decimation factor
    factor = n_points // max_points
    
    # Use strided sampling to preserve data structure
    indices = np.arange(0, n_points, factor)
    
    # Always include the last point
    if indices[-1] != n_points - 1:
        indices = np.append(indices, n_points - 1)
    
    return x_data[indices], y_data[indices]


def get_line_style(style: str) -> str:
    """
    Convert style string to matplotlib line style.
    
    Args:
        style: Style name ('solid', 'dashed', 'dotted')
        
    Returns:
        Matplotlib style string ('-', '--', ':')
    """
    style_map = {
        'solid': '-',
        'dashed': '--',
        'dotted': ':',
        'dashdot': '-.'
    }
    return style_map.get(style, '-')