import sys
from PySide6.QtWidgets import QApplication
from manic.views.main_window import MainWindow
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("manic_logger")


def main():
    app = QApplication(sys.argv)
    manic = MainWindow()
    manic.showMaximized()
    logger.info("Application Running")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
