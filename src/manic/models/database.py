import importlib.resources as pkg_resources
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from manic.utils.paths import resource_path

logger = logging.getLogger(__name__)

# adds hidden directory containing the db file to the user's home directory
DB_FILE = Path.home() / ".manic_app" / "manic.db"
# Path to schema.sql that works in both dev and frozen builds
SCHEMA_SQL_PATH = Path(resource_path('models', 'schema.sql'))


def init_db() -> None:
    """
    Create the SQLite file (if absent) and run schema.sql.
    Also handles database migrations.
    Idempotent: safe to call at every application start-up.
    """
    # Check the .manic_app directory exists
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    # open db file and sql schema in a single atomic context manager
    with sqlite3.connect(DB_FILE) as conn:
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        # Run migrations first
        _run_migrations(conn)
        # Apply base schema
        with SCHEMA_SQL_PATH.open("r", encoding="utf-8") as fh:
            conn.executescript(fh.read())

    logger.info("database ready at %s", DB_FILE)


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run database migrations to handle schema changes"""

    # Check if session_activity table exists and has retention_time column
    try:
        cursor = conn.execute("PRAGMA table_info(session_activity)")
        columns = [row[1] for row in cursor.fetchall()]  # row[1] is column name

        if "session_activity" in [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]:
            if "retention_time" not in columns:
                logger.info("Adding retention_time column to session_activity table")
                conn.execute(
                    "ALTER TABLE session_activity ADD COLUMN retention_time REAL"
                )
                conn.commit()

    except sqlite3.OperationalError as e:
        # Table doesn't exist yet, will be created by schema.sql
        logger.debug(f"Migration check: {e}")
        pass

    # Migration for TIC and MS data tables (v4.0.0)
    try:
        existing_tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]

        if "tic_data" not in existing_tables:
            logger.info("Creating tic_data table for v4.0.0")
            conn.execute("""
                CREATE TABLE tic_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_name TEXT NOT NULL,
                    time REAL NOT NULL,
                    intensity REAL NOT NULL,
                    deleted INTEGER DEFAULT 0,
                    FOREIGN KEY (sample_name) REFERENCES samples(sample_name),
                    UNIQUE(sample_name, time)
                )
            """)
            conn.execute(
                "CREATE INDEX idx_tic_sample_time ON tic_data(sample_name, time)"
            )
            conn.commit()

        if "ms_data" not in existing_tables:
            logger.info("Creating ms_data table for v4.0.0")
            conn.execute("""
                CREATE TABLE ms_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_name TEXT NOT NULL,
                    time REAL NOT NULL,
                    mz REAL NOT NULL,
                    intensity REAL NOT NULL,
                    deleted INTEGER DEFAULT 0,
                    FOREIGN KEY (sample_name) REFERENCES samples(sample_name),
                    UNIQUE(sample_name, time, mz)
                )
            """)
            conn.execute(
                "CREATE INDEX idx_ms_sample_time ON ms_data(sample_name, time)"
            )
            conn.commit()

    except sqlite3.OperationalError as e:
        logger.error(f"Migration error for TIC/MS tables: {e}")
        pass

    # Migration for formula and derivatization columns in compounds table
    try:
        cursor = conn.execute("PRAGMA table_info(compounds)")
        columns = [row[1] for row in cursor.fetchall()]  # row[1] is column name

        if "compounds" in [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]:
            # Add formula column if missing
            if "formula" not in columns:
                logger.info("Adding formula column to compounds table")
                conn.execute("ALTER TABLE compounds ADD COLUMN formula TEXT")
                conn.commit()

            # Add label_type column if missing
            if "label_type" not in columns:
                logger.info("Adding label_type column to compounds table")
                conn.execute(
                    "ALTER TABLE compounds ADD COLUMN label_type TEXT DEFAULT 'C'"
                )
                conn.commit()

            # Add derivatization columns if missing
            if "tbdms" not in columns:
                logger.info("Adding tbdms column to compounds table")
                conn.execute("ALTER TABLE compounds ADD COLUMN tbdms INTEGER DEFAULT 0")
                conn.commit()

            if "meox" not in columns:
                logger.info("Adding meox column to compounds table")
                conn.execute("ALTER TABLE compounds ADD COLUMN meox INTEGER DEFAULT 0")
                conn.commit()

            if "me" not in columns:
                logger.info("Adding me column to compounds table")
                conn.execute("ALTER TABLE compounds ADD COLUMN me INTEGER DEFAULT 0")
                conn.commit()

            # Add MRRF and MM file metadata columns if missing
            if "amount_in_std_mix" not in columns:
                logger.info("Adding amount_in_std_mix column to compounds table")
                conn.execute("ALTER TABLE compounds ADD COLUMN amount_in_std_mix REAL")
                conn.commit()

            if "int_std_amount" not in columns:
                logger.info("Adding int_std_amount column to compounds table")
                conn.execute("ALTER TABLE compounds ADD COLUMN int_std_amount REAL")
                conn.commit()

            if "mm_files" not in columns:
                logger.info("Adding mm_files column to compounds table")
                conn.execute("ALTER TABLE compounds ADD COLUMN mm_files TEXT")
                conn.commit()

    except sqlite3.OperationalError as e:
        logger.error(f"Migration error for compounds table: {e}")
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


def soft_delete_compound(compound_name: str) -> bool:
    """
    Soft delete a compound by setting deleted = 1.
    Returns True if compound was found and deleted.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE compounds SET deleted = 1 WHERE compound_name = ? AND deleted = 0",
            (compound_name,)
        )
        success = cursor.rowcount > 0
        if success:
            logger.info(f"Soft deleted compound: {compound_name}")
        # Don't log warning for compounds not found - they may already be deleted
        return success


def restore_compound(compound_name: str) -> bool:
    """
    Restore a soft-deleted compound by setting deleted = 0.
    Returns True if compound was found and restored.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE compounds SET deleted = 0 WHERE compound_name = ? AND deleted = 1",
            (compound_name,)
        )
        success = cursor.rowcount > 0
        if success:
            logger.info(f"Restored compound: {compound_name}")
        else:
            logger.warning(f"Deleted compound not found for restoration: {compound_name}")
        return success


def get_deleted_compounds():
    """
    Get list of soft-deleted compound names.
    Returns list of compound names.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT compound_name FROM compounds WHERE deleted = 1 ORDER BY compound_name"
        ).fetchall()
        return [row["compound_name"] for row in rows]


def restore_all_compounds() -> int:
    """
    Restore all soft-deleted compounds.
    Returns number of compounds restored.
    """
    with get_connection() as conn:
        cursor = conn.execute("UPDATE compounds SET deleted = 0 WHERE deleted = 1")
        count = cursor.rowcount
        logger.info(f"Restored {count} compounds")
        return count


def clear_database(progress_callback=None, fast_mode=True):
    """
    Clear all data from the database (keep schema) with optional progress tracking.
    
    Args:
        progress_callback: Optional function(current, total, operation) to track progress
        fast_mode: Use optimized clearing method (5-10x faster, default True)
    """
    if fast_mode:
        return _clear_database_fast(progress_callback)
    else:
        return _clear_database_detailed(progress_callback)


def _clear_database_fast(progress_callback=None):
    """
    OPTIMIZED: Fast database clearing using bulk operations and disabled constraints.
    
    Expected speedup: 5-10x faster than detailed mode
    - Disables foreign key constraints temporarily  
    - Uses single transaction for all operations
    - Eliminates individual row counting
    - Minimized progress callbacks
    """
    start_time = time.time()
    
    with get_connection() as conn:
        if progress_callback:
            progress_callback(0, 4, "Preparing fast database clear...")
        
        # OPTIMIZATION 1: Disable foreign key constraints for speed
        # This eliminates constraint checking overhead during bulk deletions
        conn.execute("PRAGMA foreign_keys = OFF")
        
        if progress_callback:
            progress_callback(1, 4, "Performing bulk data deletion...")
        
        # OPTIMIZATION 2: Single executescript with all deletions
        # This is much faster than individual DELETE statements
        clear_script = """
        DELETE FROM session_activity;
        DELETE FROM eic_corrected;
        DELETE FROM eic;
        DELETE FROM tic_data;  
        DELETE FROM ms_data;
        DELETE FROM samples;
        DELETE FROM compounds;
        """
        
        conn.executescript(clear_script)
        
        if progress_callback:
            progress_callback(2, 4, "Re-enabling database constraints...")
            
        # OPTIMIZATION 3: Re-enable foreign keys and verify integrity
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Verify database integrity (quick check)
        integrity_result = conn.execute("PRAGMA integrity_check(1)").fetchone()
        if integrity_result[0] != "ok":
            logger.warning(f"Database integrity check failed: {integrity_result[0]}")
        
        if progress_callback:
            progress_callback(4, 4, "Database clearing complete")
    
    elapsed_time = time.time() - start_time
    logger.info(f"Database cleared successfully (fast mode: {elapsed_time:.2f}s)")


def _clear_database_detailed(progress_callback=None):
    """
    DETAILED: Original database clearing with per-table progress and logging.
    
    Slower but provides detailed progress feedback and record counts.
    Use when detailed logging is needed or for debugging.
    """
    # Define clearing operations in dependency order
    clear_operations = [
        ("session_activity", "Clearing session overrides..."),
        ("eic_corrected", "Clearing corrected EIC data..."),
        ("eic", "Clearing raw EIC data..."),
        ("tic_data", "Clearing TIC chromatograms..."),
        ("ms_data", "Clearing mass spectra..."),
        ("samples", "Clearing sample records..."),
        ("compounds", "Clearing compound definitions...")
    ]
    
    total_operations = len(clear_operations)
    
    with get_connection() as conn:
        for i, (table, operation_desc) in enumerate(clear_operations):
            if progress_callback:
                progress_callback(i, total_operations, operation_desc)
            
            # Get count before deletion for logging
            count_result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            record_count = count_result[0] if count_result else 0
            
            # Perform deletion
            conn.execute(f"DELETE FROM {table}")
            
            if record_count > 0:
                logger.info(f"Cleared {record_count} records from {table}")
        
        # Final progress update
        if progress_callback:
            progress_callback(total_operations, total_operations, "Database clearing complete")
    
    logger.info("Database cleared successfully (detailed mode)")
