import logging
import os
import sys
from logging.handlers import RotatingFileHandler
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


def _run_smoke_test(app) -> int:
    """Verify bundled imports, SVG icons, QtWebEngine docs, Rust fitter, and export."""
    database = None
    original_db = None
    main_window_cls = None
    original_update_check = None
    window = None
    try:
        import tempfile
        import zlib

        import netCDF4  # noqa: F401
        import numpy as np
        import xlsxwriter  # noqa: F401
        from PySide6.QtCore import QCoreApplication, QEvent, QSize
        from PySide6.QtGui import QIcon, QImageReader

        from manic.io import cdf_reader, compounds_import  # noqa: F401
        from manic.io.data_exporter import DataExporter
        from manic.models import database as db_module
        from manic.models.analysis import AnalysisContext, AnalysisMode
        from manic.processors import rust_fitter
        from manic.ui.main_window import MainWindow
        from manic.utils.paths import resource_path
        from manic.utils.utils import apply_color_scheme

        database = db_module
        original_db = database.DB_FILE
        main_window_cls = MainWindow
        original_update_check = MainWindow._check_for_updates
        # Avoid network I/O and any modal update prompt during headless smoke runs.
        MainWindow._check_for_updates = lambda self: None

        formats = {bytes(fmt).lower() for fmt in QImageReader.supportedImageFormats()}
        assert b"svg" in formats, f"Qt SVG image plugin missing (formats={sorted(formats)})"
        gear = QIcon(resource_path("resources", "settings_gear.svg")).pixmap(QSize(40, 40))
        assert not gear.isNull(), "SVG resource icon failed to render"

        if getattr(sys, "frozen", False):
            assert rust_fitter.is_available(), "Bundled Rust peak fitter failed to load"

        with tempfile.TemporaryDirectory(
            prefix="manic-smoke-", ignore_cleanup_errors=True
        ) as tmp_dir:
            try:
                tmp = Path(tmp_dir)
                database.DB_FILE = tmp / "manic.db"
                database.reset_database()

                window = MainWindow(AnalysisContext(AnalysisMode.LABELLED))
                window.open_documentation_window()
                assert window.documentation_window is not None
                assert window.documentation_window.current_file is not None, (
                    "Documentation viewer loaded no page"
                )
                app.processEvents()

                apply_color_scheme(app, dark=True)
                apply_color_scheme(app, dark=False)

                time = np.linspace(4.5, 5.5, 81, dtype=np.float64)
                peak = 1000.0 * np.exp(-0.5 * ((time - 5.0) / 0.04) ** 2)
                y = np.vstack([peak, 0.2 * peak, 0.05 * peak]).astype(np.float64)
                with database.get_connection() as conn:
                    conn.execute("INSERT INTO samples (sample_name) VALUES ('S1')")
                    conn.execute(
                        """
                        INSERT INTO compounds (
                            compound_name, retention_time, loffset, roffset, mass0,
                            label_atoms, formula, deconvolution_level, baseline_correction
                        ) VALUES ('Alanine', 5.0, 0.15, 0.15, 116.1, 2, 'C3H7NO2', '4', 1)
                        """
                    )
                    conn.execute(
                        "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
                        "VALUES ('S1', 'Alanine', ?, ?, 0.5)",
                        (zlib.compress(time.tobytes()), zlib.compress(y.tobytes())),
                    )

                out_xlsx = tmp / "smoke.xlsx"
                exporter = DataExporter(AnalysisMode.LABELLED)
                assert exporter.export_to_excel(str(out_xlsx)), "Smoke export returned False"
                assert out_xlsx.is_file(), "Smoke export workbook missing"
                changelogs = list(tmp.glob("changelog_*.md"))
                assert changelogs, "Smoke export changelog missing"
                changelog_text = changelogs[0].read_text(encoding="utf-8")
                expected_backend = rust_fitter.backend_name()
                assert f"- **Peak Fitter Backend:** {expected_backend}" in changelog_text

                # Verify reset_database() succeeds while a cached connection is open.
                database.reset_database()
            finally:
                if window is not None:
                    if window.documentation_window is not None:
                        window.documentation_window.close()
                        window.documentation_window.deleteLater()
                    window.close()
                    window.deleteLater()
                    window = None
                    app.processEvents()
                    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                database._close_cached_connection()

        logger.info("Smoke test passed (backend=%s)", rust_fitter.backend_name())
        return 0
    except Exception:
        logger.exception("Smoke test failed")
        return 1
    finally:
        if main_window_cls is not None and original_update_check is not None:
            main_window_cls._check_for_updates = original_update_check
        if database is not None:
            database._close_cached_connection()
            if original_db is not None:
                database.DB_FILE = original_db


def main(argv: list[str] | None = None):
    args = sys.argv[1:] if argv is None else argv
    smoke_test = "--smoke-test" in args
    if smoke_test:
        # CI runners often run as Administrator/root where Chromium's sandbox fails.
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    from PySide6.QtWidgets import QApplication

    from manic.ui.analysis_mode_dialog import choose_analysis_mode
    from manic.utils.utils import apply_app_stylesheet

    configure_logging()
    app = QApplication([sys.argv[0], *args])
    app.setApplicationName("MANIC")
    app.setOrganizationName("Francis Crick Institute")
    # App-wide, not on MainWindow: the mode chooser below runs before any window exists.
    apply_app_stylesheet(app)

    if smoke_test:
        return _run_smoke_test(app)

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
