"""Design tokens shared by the stylesheet and by widgets that paint themselves.

``style.qss`` refers to these as ``@name`` (for example ``@accent``);
``apply_app_stylesheet`` substitutes the values. Python code imports them.
"""

from PySide6.QtGui import QColor

COLORS: dict[str, str] = {
    "bg": "#F5F6F8",
    "surface": "#FFFFFF",
    "surface_alt": "#F0F2F5",
    "surface_hover": "#E9ECF0",
    "border": "#E1E4E8",
    "border_strong": "#C9CED6",
    "text": "#1B1F24",
    "text_secondary": "#5B6470",
    "text_tertiary": "#8A93A0",
    "accent": "#2F6FEB",
    "accent_hover": "#2560D4",
    "accent_pressed": "#1E50B3",
    "accent_soft": "#E7EFFD",
    "success": "#1E9E5A",
    "success_soft": "#E5F4EC",
    "warning": "#B7791F",
    "warning_soft": "#FCF2E0",
    "danger": "#D1394A",
    "danger_hover": "#B82F3F",
    "danger_soft": "#FCEBED",
    "grid_line": "#ECEEF1",
}

RADIUS_SMALL = 6
RADIUS = 8
FONT_SIZE = 13
FONT_SIZE_SMALL = 11
FONT_SIZE_TITLE = 16


def color(name: str) -> QColor:
    return QColor(COLORS[name])


def substitute_tokens(stylesheet: str) -> str:
    # Longest names first so @accent does not clobber @accent_hover.
    for name in sorted(COLORS, key=len, reverse=True):
        stylesheet = stylesheet.replace(f"@{name}", COLORS[name])
    return stylesheet
