from PySide6.QtWidgets import QApplication

from manic.utils.paths import resource_path


def load_stylesheet(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return file.read()


def apply_app_stylesheet(app: QApplication) -> None:
    """Style every window and dialog, parented or not, from one place."""
    stylesheet = load_stylesheet(resource_path("resources", "style.qss"))
    resources_dir = resource_path("resources").replace("\\", "/")
    app.setStyleSheet(stylesheet.replace("RESOURCES_DIR", resources_dir))
