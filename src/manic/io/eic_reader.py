from __future__ import annotations

import zlib
from dataclasses import dataclass

import numpy as np

from manic.io.compound_reader import Compound
from manic.models.database import get_connection


@dataclass(slots=True)
class EIC:
    sample_name: str
    compound_name: str
    time: np.ndarray  # minutes
    intensity: np.ndarray


def read_eic(sample: str, compound: Compound, use_corrected: bool = False) -> EIC:
    """Read EIC data from either raw or corrected table.
    
    Args:
        sample: Sample name
        compound: Compound object
        use_corrected: If True, read from eic_corrected table, otherwise from eic table
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
