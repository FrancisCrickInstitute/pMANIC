"""
Integration module for natural abundance correction in EIC processing.

This module provides functions to apply natural abundance correction
to EIC data and store the corrected results in the database.
"""

import logging
import time
import zlib
from typing import Optional

import numpy as np

from manic.io.compound_reader import read_compound
from manic.io.eic_reader import read_eic
from manic.models.database import get_connection
from manic.processors.natural_abundance_correction import NaturalAbundanceCorrector

logger = logging.getLogger(__name__)


def apply_correction_to_eic(sample_name: str, compound_name: str) -> bool:
    """
    Apply natural abundance correction to an EIC and store in database.

    Args:
        sample_name: Sample to correct
        compound_name: Compound to correct

    Returns:
        True if correction was successful, False otherwise
    """
    try:
        # Read compound information (just use basic read_compound, don't need session overrides for correction)
        from manic.io.compound_reader import read_compound

        compound = read_compound(compound_name)

        # Check if formula is available
        if not compound.formula:
            logger.warning(f"No formula for {compound_name}, skipping correction")
            return False

        # Check if this is multi-isotopologue data
        if compound.label_atoms == 0:
            logger.info(f"No labeled atoms for {compound_name}, skipping correction")
            return False

        # Read EIC data
        eic = read_eic(sample_name, compound)

        # Check if we have isotopologue data
        if eic.intensity.ndim == 1:
            logger.warning(f"No isotopologue data for {compound_name} in {sample_name}")
            return False

        # Log correction attempt (only at debug level)
        logger.debug(
            f"Correcting {compound_name} in {sample_name}: "
            f"{compound.formula}, {compound.label_atoms} {compound.label_type}"
        )

        # Apply correction
        corrector = NaturalAbundanceCorrector()
        corrected_intensity = corrector.correct_time_series(
            eic.intensity,
            compound.formula,
            compound.label_type,
            compound.label_atoms,
            compound.tbdms,
            compound.meox,
            compound.me,
        )

        # Calculate correction impact (for logging)
        n_isotopologues = eic.intensity.shape[0]
        original_ratios = np.zeros(n_isotopologues)
        corrected_ratios = np.zeros(n_isotopologues)

        # Find peak region for ratio comparison
        rt_idx = np.argmax(np.sum(eic.intensity, axis=0))
        if rt_idx > 0:
            original_sum = np.sum(eic.intensity[:, rt_idx])
            corrected_sum = np.sum(corrected_intensity[:, rt_idx])
            if original_sum > 0:
                original_ratios = eic.intensity[:, rt_idx] / original_sum
            if corrected_sum > 0:
                corrected_ratios = corrected_intensity[:, rt_idx] / corrected_sum

        # Store corrected data
        store_corrected_eic(sample_name, compound_name, eic.time, corrected_intensity)

        # Log success (minimal)
        logger.debug(
            f"Corrected {compound_name} in {sample_name}"
        )

        return True

    except Exception as e:
        logger.error(f"Correction failed for {compound_name} in {sample_name}: {e}")
        return False


def store_corrected_eic(
    sample_name: str,
    compound_name: str,
    time_array: np.ndarray,
    corrected_intensity: np.ndarray,
) -> None:
    """
    Store corrected EIC data in the database.

    Args:
        sample_name: Sample name
        compound_name: Compound name
        time_array: Time points (same as original)
        corrected_intensity: Corrected intensity array
    """
    # Compress arrays for storage
    time_blob = zlib.compress(time_array.tobytes())
    intensity_blob = zlib.compress(corrected_intensity.tobytes())

    sql = """
        INSERT OR REPLACE INTO eic_corrected
        (sample_name, compound_name, x_axis, y_axis_corrected,
         correction_applied, timestamp, deleted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    with get_connection() as conn:
        conn.execute(
            sql,
            (
                sample_name,
                compound_name,
                time_blob,
                intensity_blob,
                1,  # correction_applied
                time.time(),
                0,  # deleted
            ),
        )


def read_corrected_eic(sample_name: str, compound_name: str) -> Optional[np.ndarray]:
    """
    Read corrected EIC data from database.

    Args:
        sample_name: Sample name
        compound_name: Compound name

    Returns:
        Corrected intensity array or None if not found
    """
    sql = """
        SELECT y_axis_corrected
        FROM eic_corrected
        WHERE sample_name = ? AND compound_name = ? AND deleted = 0
        LIMIT 1
    """

    with get_connection() as conn:
        row = conn.execute(sql, (sample_name, compound_name)).fetchone()

        if not row or not row["y_axis_corrected"]:
            return None

        # Decompress and reshape
        intensity_bytes = zlib.decompress(row["y_axis_corrected"])
        intensity_array = np.frombuffer(intensity_bytes, dtype=np.float64)

        # Need to know the shape - get from original EIC
        compound = read_compound(compound_name)
        eic = read_eic(sample_name, compound)
        if eic.intensity.ndim == 2:
            n_isotopologues = eic.intensity.shape[0]
            n_timepoints = len(eic.time)
            intensity_array = intensity_array.reshape(n_isotopologues, n_timepoints)

        return intensity_array


def process_all_corrections(progress_cb=None) -> int:
    """
    Process natural abundance corrections for all eligible samples.
    Optimized to batch process by compound for better performance.

    Returns:
        Number of corrections applied
    """
    import time
    start_time = time.time()
    
    # Get all compounds that need correction
    compound_sql = """
        SELECT DISTINCT c.compound_name, c.formula, c.label_type, c.label_atoms,
                        c.tbdms, c.meox, c.me
        FROM compounds c
        WHERE c.deleted = 0
        AND c.formula IS NOT NULL
        AND c.label_atoms > 0
        AND EXISTS (
            SELECT 1 FROM eic e
            WHERE e.compound_name = c.compound_name
            AND e.deleted = 0
        )
    """
    
    count = 0
    failed_count = 0
    corrector = NaturalAbundanceCorrector()  # Reuse single instance
    
    with get_connection() as conn:
        compounds = conn.execute(compound_sql).fetchall()
        
        if not compounds:
            logger.info("No compounds requiring correction")
            return 0
        
        # Silent processing - no logging during corrections
        
        for compound_idx, compound_row in enumerate(compounds):
            compound_name = compound_row["compound_name"]
            
            # Get all samples for this compound that need correction
            sample_sql = """
                SELECT e.sample_name
                FROM eic e
                WHERE e.compound_name = ?
                AND e.deleted = 0
                AND NOT EXISTS (
                    SELECT 1 FROM eic_corrected ec
                    WHERE ec.sample_name = e.sample_name
                    AND ec.compound_name = e.compound_name
                    AND ec.deleted = 0
                )
            """
            samples = conn.execute(sample_sql, (compound_name,)).fetchall()
            
            for sample_row in samples:
                try:
                    # Apply correction using cached compound data
                    if apply_correction_batch(
                        sample_row["sample_name"],
                        compound_name,
                        compound_row,
                        corrector
                    ):
                        count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.debug(f"Failed to correct {compound_name} in {sample_row['sample_name']}: {e}")
                    failed_count += 1
            
            if progress_cb:
                progress_cb(compound_idx + 1, len(compounds))
    
    # Only log if there were corrections to do
    if count > 0 or failed_count > 0:
        elapsed = time.time() - start_time
        logger.info(f"Natural abundance corrections: {count} successful ({elapsed:.1f}s)")
    
    return count


def apply_correction_batch(sample_name: str, compound_name: str, compound_row: dict, corrector: NaturalAbundanceCorrector) -> bool:
    """
    Apply correction using pre-fetched compound data for better performance.
    """
    try:
        # Read EIC data (still need to fetch this per sample)
        from manic.io.compound_reader import Compound
        compound = Compound(
            compound_name=compound_name,
            retention_time=0,  # Not needed for correction
            loffset=0,
            roffset=0, 
            label_atoms=compound_row["label_atoms"],
            mass0=0,  # Not needed
            formula=compound_row["formula"],
            label_type=compound_row["label_type"],
            tbdms=compound_row["tbdms"],
            meox=compound_row["meox"],
            me=compound_row["me"]
        )
        
        eic = read_eic(sample_name, compound)
        
        # Check if we have isotopologue data
        if eic.intensity.ndim == 1:
            return False
        
        # Apply correction
        corrected_intensity = corrector.correct_time_series(
            eic.intensity,
            compound_row["formula"],
            compound_row["label_type"],
            compound_row["label_atoms"],
            compound_row["tbdms"],
            compound_row["meox"],
            compound_row["me"],
        )
        
        # Store corrected data
        store_corrected_eic(sample_name, compound_name, eic.time, corrected_intensity)
        return True
        
    except Exception as e:
        logger.debug(f"Correction failed for {compound_name} in {sample_name}: {e}")
        return False


def has_correction(sample_name: str, compound_name: str) -> bool:
    """
    Check if corrected data exists for a sample/compound pair.

    Args:
        sample_name: Sample name
        compound_name: Compound name

    Returns:
        True if corrected data exists
    """
    sql = """
        SELECT COUNT(*) as count
        FROM eic_corrected
        WHERE sample_name = ? AND compound_name = ?
        AND deleted = 0 AND correction_applied = 1
    """

    with get_connection() as conn:
        row = conn.execute(sql, (sample_name, compound_name)).fetchone()
        return row["count"] > 0 if row else False
