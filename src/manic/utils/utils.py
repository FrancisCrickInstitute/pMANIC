from PySide6.QtCharts import QChartView
from PySide6.QtCore import QSettings, Qt
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
    hints = app.styleHints()
    # Before the first window exists, so nothing paints in the wrong scheme.
    hints.setColorScheme(APPEARANCES[appearance()])
    apply_color_scheme(app, _wants_dark(hints.colorScheme()))
    if not app.property("manicFollowsColorScheme"):
        app.setProperty("manicFollowsColorScheme", True)
        hints.colorSchemeChanged.connect(
            lambda scheme: apply_color_scheme(app, _wants_dark(scheme))
        )


APPEARANCE_SETTING = "appearance"
# System clears the app's override, so the OS scheme and its live switch show through.
APPEARANCES = {
    "system": Qt.ColorScheme.Unknown,
    "light": Qt.ColorScheme.Light,
    "dark": Qt.ColorScheme.Dark,
}


def appearance() -> str:
    saved = str(QSettings().value(APPEARANCE_SETTING, "system"))
    return saved if saved in APPEARANCES else "system"


def set_appearance(app: QApplication, name: str) -> None:
    QSettings().setValue(APPEARANCE_SETTING, name)
    hints = app.styleHints()
    hints.setColorScheme(APPEARANCES[name])
    dark = _wants_dark(hints.colorScheme())
    # Where the platform has no app-level override (offscreen) no change is emitted.
    if theme.is_dark() != dark:
        apply_color_scheme(app, dark)


def _wants_dark(os_scheme: Qt.ColorScheme) -> bool:
    forced = APPEARANCES[appearance()]
    return (os_scheme if forced == Qt.ColorScheme.Unknown else forced) == Qt.ColorScheme.Dark


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
