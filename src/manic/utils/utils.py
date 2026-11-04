from PySide6.QtCharts import QChartView
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from manic.ui import colors, theme
from manic.ui.chart_style import remap_chart_colors
from manic.ui.theme import FONT_SIZE
from manic.utils.paths import resource_path


def load_stylesheet(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return file.read()


def apply_app_stylesheet(app: QApplication) -> None:
    """Style every window and dialog from one place, following the OS light/dark scheme."""
    # Fusion draws every control the same way on macOS and Windows and takes its
    # colours from the token palette; native styles ignore part of the stylesheet
    # and, on Windows, the dark palette.
    app.setStyle("Fusion")
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    font.setPixelSize(FONT_SIZE)
    app.setFont(font)
    apply_color_scheme(app, app.styleHints().colorScheme() == Qt.ColorScheme.Dark)
    if not app.property("manicFollowsColorScheme"):
        app.setProperty("manicFollowsColorScheme", True)
        app.styleHints().colorSchemeChanged.connect(
            lambda scheme: apply_color_scheme(app, scheme == Qt.ColorScheme.Dark)
        )


def apply_color_scheme(app: QApplication, dark: bool) -> None:
    remap = theme.set_dark(dark)
    remap |= colors.set_dark(dark, theme.color("surface"))
    app.setPalette(theme.palette())
    stylesheet = load_stylesheet(resource_path("resources", "style.qss"))
    resources_dir = resource_path("resources").replace("\\", "/")
    app.setStyleSheet(theme.substitute_tokens(stylesheet.replace("RESOURCES_DIR", resources_dir)))
    if all(old == new for old, new in remap.items()):
        return
    widgets = app.allWidgets()
    theme.restyle_inline(widgets)
    for widget in widgets:
        if isinstance(widget, QChartView):
            remap_chart_colors(widget.chart(), remap)
    theme.notifier.changed.emit(remap)
