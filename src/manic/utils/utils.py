from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from manic.ui.theme import FONT_SIZE, substitute_tokens
from manic.utils.paths import resource_path


def load_stylesheet(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return file.read()


def apply_app_stylesheet(app: QApplication) -> None:
    """Style every window and dialog, parented or not, from one place."""
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    font.setPixelSize(FONT_SIZE)
    app.setFont(font)
    stylesheet = load_stylesheet(resource_path("resources", "style.qss"))
    resources_dir = resource_path("resources").replace("\\", "/")
    stylesheet = substitute_tokens(stylesheet.replace("RESOURCES_DIR", resources_dir))
    app.setStyleSheet(stylesheet)
