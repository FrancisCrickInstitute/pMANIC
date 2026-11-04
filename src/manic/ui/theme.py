"""Design tokens shared by the stylesheet and by widgets that paint themselves.

``style.qss`` refers to these as ``@name`` (for example ``@accent``);
``apply_app_stylesheet`` substitutes the values. Python code reads them through
``color()`` or ``COLORS`` at paint or build time, never at import time, because
``COLORS`` holds whichever scheme (light or dark) is active and changes live
when the OS appearance does. Inline stylesheets go through ``style()`` so they
are re-resolved on a switch.
"""

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QWidget

LIGHT: dict[str, str] = {
    "bg": "#F5F6F8",
    "surface": "#FFFFFF",
    "surface_alt": "#F0F2F5",
    "surface_hover": "#E9ECF0",
    "border": "#E1E4E8",
    "border_strong": "#C9CED6",
    "text": "#1B1F24",
    "text_secondary": "#5B6470",
    "text_tertiary": "#8A93A0",
    # Not #FFFFFF: values stay unique within a set so a scheme remap is unambiguous.
    "on_accent": "#FFFFFE",
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

DARK: dict[str, str] = {
    "bg": "#1C1E22",
    "surface": "#232529",
    "surface_alt": "#2B2E33",
    "surface_hover": "#33373D",
    "border": "#34373D",
    "border_strong": "#4A4F57",
    "text": "#E6E8EB",
    "text_secondary": "#A3AAB4",
    "text_tertiary": "#7D8590",
    "on_accent": "#FFFFFF",
    "accent": "#3B7EEE",
    "accent_hover": "#5590F2",
    "accent_pressed": "#2D6AD6",
    "accent_soft": "#24344F",
    "success": "#3FB97A",
    "success_soft": "#1D3328",
    "warning": "#E2A23B",
    "warning_soft": "#3A2F1C",
    "danger": "#E5534B",
    "danger_hover": "#EC6B64",
    "danger_soft": "#41242A",
    "grid_line": "#2D3035",
}

# The active set, updated in place so ``from theme import COLORS`` stays live.
COLORS: dict[str, str] = dict(LIGHT)

RADIUS_SMALL = 6
RADIUS = 8
FONT_SIZE = 13
FONT_SIZE_SMALL = 11
FONT_SIZE_TITLE = 16

_STYLE_PROPERTY = "themeStyle"


class _Notifier(QObject):
    changed = Signal(dict)


# Emitted after a scheme switch with the old -> new hex map, once the stylesheet,
# palette and QtCharts are restyled. Widgets holding colours elsewhere connect.
notifier = _Notifier()


def is_dark() -> bool:
    return COLORS["bg"] == DARK["bg"]


def set_dark(dark: bool) -> dict[str, str]:
    """Activate a token set; return old -> new hex (lower case) for every token."""
    new = DARK if dark else LIGHT
    remap = {COLORS[name].lower(): new[name].lower() for name in COLORS}
    COLORS.update(new)
    return remap


def color(name: str) -> QColor:
    return QColor(COLORS[name])


def contrast(a: QColor, b: QColor) -> float:
    """WCAG contrast ratio between two colours."""

    def luminance(c: QColor) -> float:
        def channel(v: float) -> float:
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        return 0.2126 * channel(c.redF()) + 0.7152 * channel(c.greenF()) + 0.0722 * channel(c.blueF())

    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def remap_color(c: QColor, remap: dict[str, str]) -> QColor:
    """``c`` in the new scheme if it came from a token or data colour, else ``c``."""
    new = remap.get(c.name())
    if new is None:
        return c
    out = QColor(new)
    out.setAlpha(c.alpha())
    return out


def substitute_tokens(stylesheet: str) -> str:
    # Longest names first so @accent does not clobber @accent_hover.
    for name in sorted(COLORS, key=len, reverse=True):
        stylesheet = stylesheet.replace(f"@{name}", COLORS[name])
    return stylesheet


def style(widget: QWidget, template: str) -> None:
    """Set an inline stylesheet written with ``@tokens``; it follows scheme switches."""
    widget.setProperty(_STYLE_PROPERTY, template)
    widget.setStyleSheet(substitute_tokens(template))


def restyle_inline(widgets) -> None:
    for widget in widgets:
        template = widget.property(_STYLE_PROPERTY)
        if template:
            widget.setStyleSheet(substitute_tokens(template))


def palette() -> QPalette:
    """Native-widget palette (menus, popups, cursors, Fusion bevels) from the tokens."""
    pal = QPalette()
    roles = {
        QPalette.Window: "bg",
        QPalette.WindowText: "text",
        QPalette.Base: "surface",
        QPalette.AlternateBase: "surface_alt",
        QPalette.Text: "text",
        QPalette.Button: "surface",
        QPalette.ButtonText: "text",
        QPalette.BrightText: "on_accent",
        QPalette.Highlight: "accent",
        QPalette.HighlightedText: "on_accent",
        QPalette.ToolTipBase: "surface",
        QPalette.ToolTipText: "text",
        QPalette.PlaceholderText: "text_tertiary",
        QPalette.Link: "accent",
        QPalette.LinkVisited: "accent_pressed",
        QPalette.Light: "surface_hover",
        QPalette.Midlight: "border",
        QPalette.Mid: "border_strong",
        QPalette.Dark: "border_strong",
        QPalette.Shadow: "bg",
    }
    for role, name in roles.items():
        pal.setColor(role, color(name))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, color("text_tertiary"))
    pal.setColor(QPalette.Disabled, QPalette.Base, color("surface_alt"))
    pal.setColor(QPalette.Disabled, QPalette.Button, color("surface_alt"))
    return pal


def set_style_property(widget, name: str, value) -> None:
    """Set a property the stylesheet selects on and re-polish so it shows."""
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)

