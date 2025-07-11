import logging
import sqlite3
import sys

from PySide6.QtWidgets import QApplication

from manic.views.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("manic_logger")


def main():
    # Connect to (or create) the database file
    conn = sqlite3.connect("manic_db.db")
    cur = conn.cursor()

    # Create compounds table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS compounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compound_name TEXT UNIQUE NOT NULL,
        retention_time REAL,
        Mass0 REAL,
        loffset REAL,
        roffset REAL,
        deleted BOOLEAN DEFAULT 0
    )
    """)

    # Create sample table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sample (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT,
        sample_name TEXT UNIQUE NOT NULL,
        deleted BOOLEAN DEFAULT 0
    )
    """)

    # Create eic table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS eic (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sample_name TEXT NOT NULL,
        compound_name TEXT NOT NULL,
        x_axis BLOB,
        y_axis BLOB,
        retention_time_window REAL,
        corrected BOOLEAN DEFAULT 0,
        deleted BOOLEAN DEFAULT 0,
        spectrum_position INTEGER,
        chromatogram_position INTEGER,
        FOREIGN KEY (sample_name) REFERENCES sample(sample_name),
        FOREIGN KEY (compound_name) REFERENCES compounds(compound_name)
    )
    """)

    conn.commit()
    conn.close()

    app = QApplication(sys.argv)
    manic = MainWindow()
    manic.showMaximized()
    logger.info("Application Running")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
