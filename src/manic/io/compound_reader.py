from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from manic.models.analysis import (
    IonChannel,
    IonRole,
    labelled_channels,
    validate_unlabelled_channels,
)
from manic.models.database import get_connection


@dataclass(slots=True)
class Compound:
    compound_name: str
    retention_time: float
    loffset: float
    roffset: float
    label_atoms: int
    mass0: float
    rt_tolerance: Optional[float] = None
    formula: Optional[str] = None
    label_type: str = 'C'
    tbdms: int = 0
    meox: int = 0
    me: int = 0
    baseline_correction: int = 1
    deconvolution_level: str = "4"
    deconvolution_fit_type: str = "auto"
    deconvolution_noise_gate: str = "balanced"
    channels: tuple[IonChannel, ...] = ()

    @property
    def analysis_channels(self) -> tuple[IonChannel, ...]:
        if self.channels:
            return self.channels
        return labelled_channels(self.mass0, self.label_atoms)

    @property
    def channel_count(self) -> int:
        return len(self.analysis_channels)

    @property
    def is_unlabelled_target(self) -> bool:
        return bool(self.channels)


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
        SELECT compound_name, retention_time, loffset, roffset, label_atoms, mass0, rt_tolerance,
               formula, label_type, tbdms, meox, me, baseline_correction,
               deconvolution_level, deconvolution_fit_type, deconvolution_noise_gate
        FROM   compounds
        WHERE  compound_name=? AND deleted=0
        LIMIT  1
    """
    with get_connection() as conn:
        row = conn.execute(sql, (compound_name,)).fetchone()
        if row is None:
            raise LookupError(f"Compound not found for {compound_name}")
        ion_rows = conn.execute(
            """
            SELECT role, ordinal, mz, expected_ratio, ratio_tolerance
            FROM compound_ions
            WHERE compound_name = ?
            ORDER BY CASE role WHEN 'quantifier' THEN 0 ELSE 1 END, ordinal
            """,
            (compound_name,),
        ).fetchall()

    channels: tuple[IonChannel, ...] = ()
    if ion_rows:
        channels = validate_unlabelled_channels(
            IonChannel(
                mz=float(ion_row["mz"]),
                role=IonRole(ion_row["role"]),
                ordinal=int(ion_row["ordinal"]),
                expected_ratio=ion_row["expected_ratio"],
                ratio_tolerance=ion_row["ratio_tolerance"],
            )
            for ion_row in ion_rows
        )
    
    return Compound(
        compound_name=row["compound_name"],
        retention_time=row["retention_time"],
        loffset=row["loffset"],
        roffset=row["roffset"],
        label_atoms=int(row["label_atoms"]) if row["label_atoms"] else 0,
        mass0=row["mass0"],
        rt_tolerance=row["rt_tolerance"],
        formula=row["formula"],
        label_type=row["label_type"] or 'C',
        tbdms=int(row["tbdms"]) if row["tbdms"] else 0,
        meox=int(row["meox"]) if row["meox"] else 0,
        me=int(row["me"]) if row["me"] else 0,
        baseline_correction=int(row["baseline_correction"]) if row["baseline_correction"] is not None else 1,
        deconvolution_level=row["deconvolution_level"] or "4",
        deconvolution_fit_type=row["deconvolution_fit_type"] or "auto",
        deconvolution_noise_gate=row["deconvolution_noise_gate"] or "balanced",
        channels=channels,
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
            return base_compound
        
        # Create compound with session data overrides
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Using session data for {compound_name} / {sample_name}: RT={session_row['retention_time']:.3f}")
        
        return Compound(
            compound_name=base_compound.compound_name,
            retention_time=session_row["retention_time"],  # Override with session data
            loffset=session_row["loffset"],  # Override with session data
            roffset=session_row["roffset"],  # Override with session data  
            label_atoms=base_compound.label_atoms,  # Always from base compound
            mass0=base_compound.mass0,  # Always from base compound
            rt_tolerance=base_compound.rt_tolerance,
            formula=base_compound.formula,  # Always from base compound
            label_type=base_compound.label_type,  # Always from base compound
            tbdms=base_compound.tbdms,  # Always from base compound
            meox=base_compound.meox,  # Always from base compound
            me=base_compound.me,  # Always from base compound
            baseline_correction=base_compound.baseline_correction,  # Always from base compound
            deconvolution_level=base_compound.deconvolution_level,  # Always from base compound
            deconvolution_fit_type=base_compound.deconvolution_fit_type,  # Always from base compound
            deconvolution_noise_gate=base_compound.deconvolution_noise_gate,  # Always from base compound
            channels=base_compound.channels,
        )
