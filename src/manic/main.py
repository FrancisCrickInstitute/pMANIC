import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    log_dir = Path.home() / ".manic_app"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s:%(funcName)s(): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            RotatingFileHandler(
                log_dir / "manic.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=2,
                encoding="utf-8",
            ),
            logging.StreamHandler(),  # console
        ],
    )


def main():
    from PySide6.QtWidgets import QApplication

    from manic.ui.analysis_mode_dialog import choose_analysis_mode
    from manic.utils.utils import apply_app_stylesheet

    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("MANIC")
    app.setOrganizationName("Francis Crick Institute")
    # App-wide, not on MainWindow: the mode chooser below runs before any window exists.
    apply_app_stylesheet(app)

    selected_mode = choose_analysis_mode()
    if selected_mode is None:
        logger.info("Application start cancelled before analysis selection")
        return 0

    # Import MainWindow and database only after the user chooses a mode so the
    # first dialog appears without loading numpy, QtCharts, or heavy I/O modules.
    from manic.models.analysis import AnalysisContext
    from manic.models.database import reset_database
    from manic.ui.main_window import MainWindow

    reset_database()
    logger.info("Database initialized")

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
