import importlib.resources as pkg_resources
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

# adds hidden directory containing the db file to the user's home directory
DB_FILE = Path.home() / ".manic_app" / "manic.db"
# create a reference to the schema file regardless of app packaging (e.g. as a .exe )
SCHEMA_SQL = pkg_resources.files(__package__).joinpath("schema.sql")


def init_db() -> None:
    """
    Create the SQLite file (if absent) and run schema.sql.
    Also handles database migrations.
    Idempotent: safe to call at every application start-up.
    """
    # Check the .manic_app directory exists
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # open db file and sql schema in a single atomic context manager
    with (
        sqlite3.connect(DB_FILE) as conn,
        SCHEMA_SQL.open("r", encoding="utf-8") as fh,
    ):
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Run migrations first
        _run_migrations(conn)
        
        # read the sql script & send to sqlite in one call
        conn.executescript(fh.read())
        
    logger.info("database ready at %s", DB_FILE)


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run database migrations to handle schema changes"""
    
    # Check if session_activity table exists and has retention_time column
    try:
        cursor = conn.execute("PRAGMA table_info(session_activity)")
        columns = [row[1] for row in cursor.fetchall()]  # row[1] is column name
        
        if 'session_activity' in [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
            if 'retention_time' not in columns:
                logger.info("Adding retention_time column to session_activity table")
                conn.execute("ALTER TABLE session_activity ADD COLUMN retention_time REAL")
                conn.commit()
                
    except sqlite3.OperationalError as e:
        # Table doesn't exist yet, will be created by schema.sql
        logger.debug(f"Migration check: {e}")
        pass


@contextmanager
# work inside a managed transaction
def get_connection():
    """
    Yield a read-write connection with foreign-keys enforced.
    Commits on normal exit, rolls back on exception.

    Example usage:

        with get_connection() as conn:
            conn.execute("INSERT INTO compounds (...) VALUES (...)")

    """
    conn = None  #  ensure the name exists
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn  #  hand the connection to callers
        conn.commit()  #  normal exit ⇒ commit
    except Exception:
        if conn is not None:
            conn.rollback()  #  roll back only if we had a connection
        logger.exception("DB transaction rolled back")
        raise
    finally:
        if conn is not None:  #  close only if we actually opened it
            conn.close()


def clear_database():
    """Clear all data from the database (keep schema)."""
    with get_connection() as conn:
        # Clear in order respecting foreign key constraints
        # session_activity references both compounds and samples, so clear it first
        conn.execute("DELETE FROM session_activity")
        conn.execute("DELETE FROM eic")
        conn.execute("DELETE FROM samples")
        conn.execute("DELETE FROM compounds")
    logger.info("Database cleared")
