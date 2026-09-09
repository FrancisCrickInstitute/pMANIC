from PySide6.QtWidgets import QApplication

from manic.utils.paths import resource_path


def load_stylesheet(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return file.read()


def apply_app_stylesheet(app: QApplication) -> None:
    """Style every window and dialog, parented or not, from one place."""
    app.setStyleSheet(load_stylesheet(resource_path("resources", "style.qss")))
