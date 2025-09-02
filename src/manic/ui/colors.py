"""
Shared color definitions for consistent styling across UI components.
"""

from PySide6.QtGui import QColor

# Steel blue and dark red used in graphs
steel_blue_colour = QColor(70, 130, 180)
dark_red_colour = QColor(139, 0, 0)
selection_color = QColor(144, 238, 144, 50)  # Light green with transparency

# Colors for isotopologue labels (M+0, M+1, M+2, etc.)
# Used in both multi-trace plots and isotopologue ratio charts
label_colors = [
    QColor(31, 119, 180),    # blue - M+0
    QColor(255, 127, 14),    # orange - M+1  
    QColor(44, 160, 44),     # green - M+2
    QColor(214, 39, 40),     # red - M+3
    QColor(148, 103, 189),   # purple - M+4
    QColor(140, 86, 75),     # brown - M+5
    QColor(227, 119, 194),   # pink - M+6
    QColor(127, 127, 127),   # gray - M+7
    QColor(188, 189, 34),    # olive - M+8
    QColor(23, 190, 207),    # cyan - M+9
]