from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from manic.models.database import get_connection


@dataclass(slots=True)
class Compound:
    compound_name: str
    retention_time: float
    loffset: float
    roffset: float
    label_atoms: int
    mass0: float


def read_compound(compound_name: str) -> Compound:
    """
    Read compound data from the database.
    
    Args:
        compound_name: Name of the compound to read
        
    Returns:
        Compound object with default parameters from compounds table
        
    Raises:
        LookupError: If compound not found
    """
    sql = """
        SELECT compound_name, retention_time, loffset, roffset, label_atoms, mass0
        FROM   compounds
        WHERE  compound_name=? AND deleted=0
        LIMIT  1
    """
    with get_connection() as conn:
        row = conn.execute(sql, (compound_name,)).fetchone()
        if row is None:
            raise LookupError(f"Compound not found for {compound_name}")

    return Compound(
        compound_name=row["compound_name"],
        retention_time=row["retention_time"],
        loffset=row["loffset"],
        roffset=row["roffset"],
        label_atoms=int(row["label_atoms"]),
        mass0=row["mass0"],
    )


def read_compound_with_session(compound_name: str, sample_name: Optional[str] = None) -> Compound:
    """
    Read compound data with optional session activity override.
    
    This function first checks for session-specific parameter overrides in the
    session_activity table. If found, those parameters take precedence over
    the default compound parameters. If no session data exists or no sample
    is specified, returns default compound data.
    
    Args:
        compound_name: Name of the compound to read
        sample_name: Optional sample name for session data lookup
        
    Returns:
        Compound object with session data overrides applied if available
        
    Raises:
        LookupError: If compound not found
    """
    # Get base compound data first
    base_compound = read_compound(compound_name)
    
    # If no sample specified, return base compound
    if not sample_name:
        return base_compound
    
    # Check for session activity override
    session_sql = """
        SELECT retention_time, loffset, roffset
        FROM session_activity
        WHERE compound_name = ? AND sample_name = ? AND sample_deleted = 0
        LIMIT 1
    """
    
    with get_connection() as conn:
        session_row = conn.execute(session_sql, (compound_name, sample_name)).fetchone()
        
        if session_row is None:
            # No session data, return base compound
            return base_compound
        
        # Create compound with session data overrides
        return Compound(
            compound_name=base_compound.compound_name,
            retention_time=session_row["retention_time"],  # Override with session data
            loffset=session_row["loffset"],  # Override with session data
            roffset=session_row["roffset"],  # Override with session data  
            label_atoms=base_compound.label_atoms,  # Always from base compound
            mass0=base_compound.mass0,  # Always from base compound
        )
