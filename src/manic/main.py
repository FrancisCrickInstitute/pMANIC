import logging
import sys
from pathlib import Path

from manic.models.database import clear_database, init_db


def configure_logging() -> None:
    log_dir = Path.home() / ".manic_app"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s:%(funcName)s(): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_dir / "manic.log", encoding="utf-8"),  # log file
            logging.StreamHandler(),  # console
        ],
    )


def main():
    from PySide6.QtWidgets import QApplication

    from manic.models.analysis import AnalysisContext
    from manic.ui.analysis_mode_dialog import choose_analysis_mode
    from manic.ui.main_window import MainWindow

    logger = logging.getLogger(__name__)

    configure_logging()
    app = QApplication(sys.argv)

    selected_mode = choose_analysis_mode()
    if selected_mode is None:
        logger.info("Application start cancelled before analysis selection")
        return 0

    init_db()
    clear_database()
    print("Database initialized")

    manic = MainWindow(AnalysisContext(selected_mode))
    manic.showMaximized()
    logger.info("Application Running")
    return app.exec()


if __name__ == "__main__":
    # Required for the frozen (PyInstaller) build: worker processes started with
    # the spawn method re-run the entry module, and freeze_support() stops that
    # from relaunching the whole app. Harmless when running from source.
    import multiprocessing

    multiprocessing.freeze_support()
    sys.exit(main())
