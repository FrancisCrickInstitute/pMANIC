"""
Session Activity Service

Manages session-specific compound data that overrides default compound parameters.
This allows users to temporarily modify integration parameters (loffset, roffset, mass0)
for specific compound-sample combinations without permanently altering the base compound data.

The session_activity table acts as an overlay on top of the compounds table,
providing sample-specific parameter overrides that persist during the current session.
"""

import logging
import sqlite3
from contextlib import nullcontext
from dataclasses import dataclass
from typing import List, Optional

from manic.models.database import get_connection

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SessionData:
    """Session-specific compound parameters for a sample"""
    compound_name: str
    sample_name: str
    retention_time: float
    loffset: float
    roffset: float
    sample_deleted: bool = False


@dataclass(frozen=True, slots=True)
class PendingRegeneration:
    compound_name: str
    retention_time: float | None
    loffset: float | None
    roffset: float | None
    sample_names: tuple[str, ...]
    regenerated_sample_names: tuple[str, ...]


class SessionActivityService:
    """
    Service for managing session activity data that overrides default compound parameters.

    This service provides CRUD operations for the session_activity table, allowing
    users to apply temporary modifications to compound parameters on a per-sample basis.
    Session data takes precedence over default compound data when present.
    """

    @staticmethod
    def update_session_data(
        compound_name: str,
        sample_names: List[str],
        retention_time: float | None,
        loffset: float | None,
        roffset: float | None,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        """
        Update session activity data for multiple samples in one transaction.

        A field passed as None keeps each sample's current value: its session
        override, else the compound default. The UI passes None for a field that
        still shows a range across several samples.

        Args:
            compound_name: Name of the compound
            sample_names: List of sample names to update
            retention_time: Retention time value, or None to keep each sample's
            loffset: Left offset value, or None to keep each sample's
            roffset: Right offset value, or None to keep each sample's

        Raises:
            sqlite3.Error: If database operation fails
            ValueError: If invalid parameters provided
        """
        if not compound_name or not isinstance(compound_name, str):
            raise ValueError("Compound name must be a non-empty string")

        if not sample_names or not isinstance(sample_names, list):
            raise ValueError("Sample names must be a non-empty list")

        if not all(isinstance(name, str) and name.strip() for name in sample_names):
            raise ValueError("All sample names must be non-empty strings")

        try:
            new_values = {
                field: None if value is None else float(value)
                for field, value in (
                    ("retention_time", retention_time),
                    ("loffset", loffset),
                    ("roffset", roffset),
                )
            }
        except (ValueError, TypeError) as e:
            raise ValueError(f"Retention time and offset values must be numeric: {e}")

        if new_values["retention_time"] is not None and new_values["retention_time"] <= 0:
            raise ValueError("Retention time must be positive")
        if new_values["loffset"] is not None and new_values["loffset"] < 0:
            raise ValueError("Left offset cannot be negative")
        if new_values["roffset"] is not None and new_values["roffset"] < 0:
            raise ValueError("Right offset cannot be negative")

        logger.info(
            f"Updating session data for compound '{compound_name}' "
            f"across {len(sample_names)} samples"
        )

        try:
            connection_context = (
                nullcontext(connection)
                if connection is not None
                else get_connection()
            )
            with connection_context as conn:
                base_row = conn.execute(
                    """
                    SELECT retention_time, loffset, roffset
                    FROM compounds
                    WHERE compound_name = ? AND deleted = 0
                    LIMIT 1
                    """,
                    (compound_name,),
                ).fetchone()

                placeholders = ",".join(["?"] * len(sample_names))
                current_by_sample = {
                    row["sample_name"]: row
                    for row in conn.execute(
                        f"""
                        SELECT sample_name, retention_time, loffset, roffset
                        FROM session_activity
                        WHERE compound_name = ?
                          AND sample_deleted = 0
                          AND sample_name IN ({placeholders})
                        """,
                        (compound_name, *sample_names),
                    ).fetchall()
                }

                insert_params = []
                for sample_name in sample_names:
                    current = current_by_sample.get(sample_name, base_row)
                    values = [
                        value if value is not None
                        else current[field] if current is not None
                        else None
                        for field, value in new_values.items()
                    ]
                    if None in values:
                        raise ValueError(
                            f"No current value to keep for {sample_name}"
                        )
                    insert_params.append(
                        (compound_name, sample_name, *map(float, values))
                    )

                conn.executemany(
                    """
                    DELETE FROM session_activity
                    WHERE compound_name = ? AND sample_name = ?
                    """,
                    [(compound_name, s) for s in sample_names],
                )
                conn.executemany(
                    """
                    INSERT INTO session_activity
                        (compound_name, sample_name, retention_time, loffset, roffset, sample_deleted)
                    VALUES (?, ?, ?, ?, ?, 0)
                    """,
                    insert_params,
                )

                logger.info(
                    f"Successfully updated session data for {len(sample_names)} samples "
                    f"of compound '{compound_name}'"
                )

        except Exception as e:
            logger.error(
                f"Failed to update session data for compound '{compound_name}': {e}"
            )
            raise

    @staticmethod
    def get_session_data(compound_name: str, sample_name: str) -> Optional[SessionData]:
        """
        Retrieve session activity data for a specific compound-sample combination.
        
        Args:
            compound_name: Name of the compound
            sample_name: Name of the sample
            
        Returns:
            SessionData object if found, None otherwise
            
        Raises:
            sqlite3.Error: If database query fails
        """
        if not compound_name or not sample_name:
            return None
        
        query_sql = """
            SELECT compound_name, sample_name, retention_time, loffset, roffset, sample_deleted
            FROM session_activity 
            WHERE compound_name = ? AND sample_name = ? AND sample_deleted = 0
            LIMIT 1
        """
        
        try:
            with get_connection() as conn:
                row = conn.execute(query_sql, (compound_name, sample_name)).fetchone()
                
                if row is None:
                    return None
                
                return SessionData(
                    compound_name=row["compound_name"],
                    sample_name=row["sample_name"],
                    retention_time=row["retention_time"],
                    loffset=row["loffset"],
                    roffset=row["roffset"],
                    sample_deleted=bool(row["sample_deleted"])
                )
                
        except Exception as e:
            logger.error(
                f"Failed to retrieve session data for '{compound_name}' "
                f"in sample '{sample_name}': {e}"
            )
            return None

    @staticmethod
    def has_session_data(compound_name: str, sample_name: str) -> bool:
        """
        Check if session activity data exists for a compound-sample combination.
        
        Args:
            compound_name: Name of the compound
            sample_name: Name of the sample
            
        Returns:
            True if session data exists, False otherwise
        """
        return SessionActivityService.get_session_data(compound_name, sample_name) is not None

    @staticmethod
    def get_samples_with_session_data(compound_name: str) -> List[str]:
        """
        Get list of sample names that have session data for a specific compound.
        
        Args:
            compound_name: Name of the compound
            
        Returns:
            List of sample names with session data
        """
        if not compound_name:
            return []
        
        query_sql = """
            SELECT DISTINCT sample_name
            FROM session_activity 
            WHERE compound_name = ? AND sample_deleted = 0
            ORDER BY sample_name
        """
        
        try:
            with get_connection() as conn:
                rows = conn.execute(query_sql, (compound_name,)).fetchall()
                return [row["sample_name"] for row in rows]
                
        except Exception as e:
            logger.error(
                f"Failed to retrieve samples with session data for '{compound_name}': {e}"
            )
            return []

    @staticmethod
    def clear_session_data(compound_name: Optional[str] = None) -> None:
        """
        Clear session activity data.
        
        Args:
            compound_name: If provided, clear data only for this compound.
                          If None, clear all session data.
        """
        if compound_name:
            delete_sql = "DELETE FROM session_activity WHERE compound_name = ?"
            params = (compound_name,)
            logger.info(f"Clearing session data for compound '{compound_name}'")
        else:
            delete_sql = "DELETE FROM session_activity"
            params = ()
            logger.info("Clearing all session data")
        
        try:
            with get_connection() as conn:
                result = conn.execute(delete_sql, params)
                deleted_count = result.rowcount
                
                logger.info(f"Cleared {deleted_count} session activity records")
                
        except Exception as e:
            logger.error(f"Failed to clear session data: {e}")
            raise

    @staticmethod
    def restore_samples_to_defaults(compound_name: str, sample_names: List[str]) -> None:
        """
        Restore specific samples back to their default compound values by removing session data.
        
        Args:
            compound_name: Name of the compound
            sample_names: List of sample names to restore to defaults
            
        Raises:
            sqlite3.Error: If database operation fails
            ValueError: If invalid parameters provided
        """
        # Input validation
        if not compound_name or not isinstance(compound_name, str):
            raise ValueError("Compound name must be a non-empty string")
        
        if not sample_names or not isinstance(sample_names, list):
            raise ValueError("Sample names must be a non-empty list")
        
        if not all(isinstance(name, str) and name.strip() for name in sample_names):
            raise ValueError("All sample names must be non-empty strings")
        
        logger.info(
            f"Restoring {len(sample_names)} samples to defaults for compound '{compound_name}'"
        )
        
        try:
            with get_connection() as conn:
                # Delete session data for specified samples
                delete_sql = """
                    DELETE FROM session_activity 
                    WHERE compound_name = ? AND sample_name = ?
                """
                
                deleted_count = 0
                for sample_name in sample_names:
                    result = conn.execute(delete_sql, (compound_name, sample_name))
                    deleted_count += result.rowcount
                
                logger.info(
                    f"Successfully restored {deleted_count} samples to defaults "
                    f"for compound '{compound_name}'"
                )
                
        except Exception as e:
            logger.error(
                f"Failed to restore samples to defaults for compound '{compound_name}': {e}"
            )
            raise

    @staticmethod
    def get_session_data_for_samples(
        compound_name: str, 
        sample_names: List[str]
    ) -> List[SessionData]:
        """
        Retrieve session data for multiple samples efficiently.
        
        Args:
            compound_name: Name of the compound
            sample_names: List of sample names to query
            
        Returns:
            List of SessionData objects (may be fewer than input if some don't exist)
        """
        if not compound_name or not sample_names:
            return []
        
        placeholders = ",".join("?" for _ in sample_names)
        query_sql = f"""
            SELECT compound_name, sample_name, retention_time, loffset, roffset, sample_deleted
            FROM session_activity 
            WHERE compound_name = ? AND sample_name IN ({placeholders}) AND sample_deleted = 0
        """
        with get_connection() as conn:
            params = [compound_name] + sample_names
            rows = conn.execute(query_sql, params).fetchall()

        return [
            SessionData(
                compound_name=row["compound_name"],
                sample_name=row["sample_name"],
                retention_time=row["retention_time"],
                loffset=row["loffset"],
                roffset=row["roffset"],
                sample_deleted=bool(row["sample_deleted"]),
            )
            for row in rows
        ]