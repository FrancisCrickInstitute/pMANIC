"""
Session Activity Service

Manages session-specific compound data that overrides default compound parameters.
This allows users to temporarily modify integration parameters (loffset, roffset, mass0)
for specific compound-sample combinations without permanently altering the base compound data.

The session_activity table acts as an overlay on top of the compounds table,
providing sample-specific parameter overrides that persist during the current session.
"""

import logging
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


class SessionActivityService:
    """
    Service for managing session activity data that overrides default compound parameters.

    This service provides CRUD operations for the session_activity table, allowing
    users to apply temporary modifications to compound parameters on a per-sample basis.
    Session data takes precedence over default compound data when present.
    """

    @staticmethod
    def update_offsets_preserve_rt(
        compound_name: str,
        sample_names: List[str],
        loffset: float,
        roffset: float,
    ) -> None:
        """Update offsets for samples while preserving each sample's RT.

        Used when the UI displays a tR range across multiple samples.
        This performs the update in a single transaction for performance.
        """
        if not compound_name or not isinstance(compound_name, str):
            raise ValueError("Compound name must be a non-empty string")

        if not sample_names or not isinstance(sample_names, list):
            raise ValueError("Sample names must be a non-empty list")

        if not all(isinstance(name, str) and name.strip() for name in sample_names):
            raise ValueError("All sample names must be non-empty strings")

        try:
            loffset = float(loffset)
            roffset = float(roffset)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Offset values must be numeric: {e}")

        if loffset < 0:
            raise ValueError("Left offset cannot be negative")
        if roffset < 0:
            raise ValueError("Right offset cannot be negative")

        placeholders = ",".join(["?"] * len(sample_names))

        try:
            with get_connection() as conn:
                base_row = conn.execute(
                    """
                    SELECT retention_time
                    FROM compounds
                    WHERE compound_name = ? AND deleted = 0
                    LIMIT 1
                    """,
                    (compound_name,),
                ).fetchone()

                if base_row is None or base_row["retention_time"] is None:
                    raise ValueError(f"Compound not found: {compound_name}")

                base_rt = float(base_row["retention_time"])

                override_rows = conn.execute(
                    f"""
                    SELECT sample_name, retention_time
                    FROM session_activity
                    WHERE compound_name = ?
                      AND sample_deleted = 0
                      AND sample_name IN ({placeholders})
                    """,
                    (compound_name, *sample_names),
                ).fetchall()

                override_rt_by_sample = {
                    row["sample_name"]: float(row["retention_time"]) for row in override_rows
                }

                delete_sql = """
                    DELETE FROM session_activity
                    WHERE compound_name = ? AND sample_name = ?
                """

                insert_sql = """
                    INSERT INTO session_activity
                        (compound_name, sample_name, retention_time, loffset, roffset, sample_deleted)
                    VALUES (?, ?, ?, ?, ?, 0)
                """

                delete_params = [(compound_name, s) for s in sample_names]
                conn.executemany(delete_sql, delete_params)

                insert_params = []
                for sample_name in sample_names:
                    sample_rt = override_rt_by_sample.get(sample_name, base_rt)
                    insert_params.append(
                        (
                            compound_name,
                            sample_name,
                            float(sample_rt),
                            float(loffset),
                            float(roffset),
                        )
                    )

                conn.executemany(insert_sql, insert_params)

        except Exception as e:
            logger.error(
                f"Failed to update offsets (preserve RT) for compound '{compound_name}': {e}"
            )
            raise

    @staticmethod
    def update_session_data(
        compound_name: str, 
        sample_names: List[str], 
        retention_time: float,
        loffset: float, 
        roffset: float
    ) -> None:
        """
        Update session activity data for multiple samples with the same compound parameters.
        
        This method performs an atomic upsert operation, either inserting new session data
        or updating existing records for the given compound-sample combinations.
        
        Args:
            compound_name: Name of the compound
            sample_names: List of sample names to update
            retention_time: Retention time value
            loffset: Left offset value
            roffset: Right offset value
            
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
        
        # Numeric validation with proper error messages
        try:
            retention_time = float(retention_time)
            loffset = float(loffset)
            roffset = float(roffset)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Retention time and offset values must be numeric: {e}")
        
        # Range validation
        if retention_time <= 0:
            raise ValueError("Retention time must be positive")
        if loffset < 0:
            raise ValueError("Left offset cannot be negative")
        if roffset < 0:
            raise ValueError("Right offset cannot be negative")
        
        logger.info(
            f"Updating session data for compound '{compound_name}' "
            f"across {len(sample_names)} samples"
        )
        
        try:
            with get_connection() as conn:
                # First, delete existing records to avoid duplicates
                delete_sql = """
                    DELETE FROM session_activity 
                    WHERE compound_name = ? AND sample_name = ?
                """
                
                # Then insert new records
                insert_sql = """
                    INSERT INTO session_activity (compound_name, sample_name, retention_time, loffset, roffset, sample_deleted)
                    VALUES (?, ?, ?, ?, ?, 0)
                """
                
                # Process each sample
                for sample_name in sample_names:
                    # Delete existing record
                    conn.execute(delete_sql, (compound_name, sample_name))
                    
                    # Insert new record
                    conn.execute(insert_sql, (
                        compound_name, sample_name, float(retention_time), float(loffset), float(roffset)
                    ))
                
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
        
        # Create placeholders for IN clause
        placeholders = ",".join("?" for _ in sample_names)
        query_sql = f"""
            SELECT compound_name, sample_name, retention_time, loffset, roffset, sample_deleted
            FROM session_activity 
            WHERE compound_name = ? AND sample_name IN ({placeholders}) AND sample_deleted = 0
        """
        
        try:
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
                        sample_deleted=bool(row["sample_deleted"])
                    )
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(
                f"Failed to retrieve session data for compound '{compound_name}': {e}"
            )
            return []