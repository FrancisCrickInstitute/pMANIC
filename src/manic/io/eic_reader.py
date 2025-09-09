from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import List

import numpy as np

from manic.io.compound_reader import Compound
from manic.models.database import get_connection


@dataclass(slots=True)
class EIC:
    sample_name: str
    compound_name: str
    time: np.ndarray  # minutes
    intensity: np.ndarray


def read_eics_batch(samples: List[str], compound: Compound, use_corrected: bool = True) -> List[EIC]:
    """
    Batch read EIC data for multiple samples and a single compound.
    
    Performs a single database query with an IN clause to fetch all requested EICs,
    significantly reducing database overhead compared to individual queries per sample.
    Automatically falls back to uncorrected data if corrected data is not available.
    
    Args:
        samples: List of sample names to retrieve EICs for
        compound: Compound object containing metadata and label information
        use_corrected: When True, attempts to read corrected data first, falls back to raw
        
    Returns:
        List of EIC objects with decompressed time and intensity data
        
    Raises:
        LookupError: If no EIC data is found for the compound in any sample
    """
    if not samples:
        return []
    
    compound_name = compound.compound_name
    
    # Create parameterized query with IN clause for batch fetching
    placeholders = ','.join(['?'] * len(samples))
    
    if use_corrected:
        # Attempt to read corrected data first
        sql = f"""
            SELECT sample_name, x_axis, y_axis_corrected as y_axis
            FROM eic_corrected 
            WHERE compound_name=? AND sample_name IN ({placeholders}) AND deleted=0
        """
        params = [compound_name] + samples
        
        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        
        # If no corrected data found, fall back to uncorrected for all samples
        if not rows:
            return read_eics_batch(samples, compound, use_corrected=False)
    else:
        sql = f"""
            SELECT sample_name, x_axis, y_axis
            FROM eic 
            WHERE compound_name=? AND sample_name IN ({placeholders}) AND deleted=0
        """
        params = [compound_name] + samples
        
        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        
        if not rows:
            raise LookupError(f"No EIC data found for {compound_name} in any of the requested samples")
    
    # Process batch results into EIC objects, preserving original sample order
    # Create a dictionary for fast lookup of database results by sample name
    results_by_sample = {}
    for row in rows:
        # Decompress time and intensity data from database blobs
        time = np.frombuffer(zlib.decompress(row["x_axis"]), dtype=np.float64)
        inten = np.frombuffer(zlib.decompress(row["y_axis"]), dtype=np.float64)
        
        # Reshape intensity data for isotopologue compounds (multi-label)
        label_atoms = compound.label_atoms
        if label_atoms > 0:
            num_labels = label_atoms + 1
            inten = inten.reshape((num_labels, len(inten) // num_labels))
        
        results_by_sample[row["sample_name"]] = EIC(row["sample_name"], compound_name, time, inten)
    
    # Return EICs in the same order as requested samples to preserve UI ordering
    eics = []
    for sample_name in samples:
        if sample_name in results_by_sample:
            eics.append(results_by_sample[sample_name])
    
    return eics


def read_eic(sample: str, compound: Compound, use_corrected: bool = True) -> EIC:
    """Read EIC data from either corrected or raw table.
    
    Natural abundance correction is enabled by default to provide the most accurate
    isotopologue data for metabolic flux analysis. Raw uncorrected data can be 
    accessed by setting use_corrected=False.
    
    Args:
        sample: Sample name
        compound: Compound object
        use_corrected: If True (default), read corrected data; False for raw data
    """
    compound_name = compound.compound_name
    
    if use_corrected:
        # Try to read from corrected table first
        sql = """
            SELECT x_axis, y_axis_corrected as y_axis
            FROM   eic_corrected
            WHERE  sample_name=? AND compound_name=? AND deleted=0
            LIMIT  1
        """
        with get_connection() as conn:
            row = conn.execute(sql, (sample, compound_name)).fetchone()
            
        # Fall back to uncorrected if no corrected data exists
        if row is None:
            return read_eic(sample, compound, use_corrected=False)
    else:
        sql = """
            SELECT x_axis, y_axis, rt_window
            FROM   eic
            WHERE  sample_name=? AND compound_name=? AND deleted=0
            LIMIT  1
        """
        with get_connection() as conn:
            row = conn.execute(sql, (sample, compound_name)).fetchone()
            
        if row is None:
            raise LookupError(f"EIC not found for {compound_name} in {sample}")

    label_atoms = compound.label_atoms
    num_labels = label_atoms + 1

    time = np.frombuffer(zlib.decompress(row["x_axis"]), dtype=np.float64)
    inten = np.frombuffer(zlib.decompress(row["y_axis"]), dtype=np.float64)
    if label_atoms > 0:
        inten = inten.reshape(
            (
                num_labels,
                len(inten) // num_labels,
            )  # floor division works as embedded arrays are same length
        )
    return EIC(sample, compound_name, time, inten)
