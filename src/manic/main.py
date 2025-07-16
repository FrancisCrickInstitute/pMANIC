import logging
import sys
from pathlib import Path

from manic.models.database import clear_database, init_db


def configure_logging() -> None:
    log_dir = Path.home() / ".manic_app"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_dir / "manic.log", encoding="utf-8"),  # log file
            logging.StreamHandler(),  # console
        ],
    )


def main():
    from PySide6.QtWidgets import QApplication

    from manic.ui.main_window import MainWindow

    logger = logging.getLogger("manic_logger")

    configure_logging()
    init_db()
    clear_database()
    print("Database initialized")

    app = QApplication(sys.argv)
    manic = MainWindow()
    manic.showMaximized()
    logger.info("Application Running")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
