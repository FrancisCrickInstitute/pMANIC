from __future__ import annotations

import zlib
from dataclasses import dataclass

import numpy as np

from manic.io.compound_reader import read_compound
from manic.models.database import get_connection


@dataclass(slots=True)
class EIC:
    sample_name: str
    compound_name: str
    time: np.ndarray  # minutes
    intensity: np.ndarray


def read_eic(sample: str, compound: str) -> EIC:
    sql = """
        SELECT x_axis, y_axis, rt_window
        FROM   eic
        WHERE  sample_name=? AND compound_name=? AND deleted=0
        LIMIT  1
    """
    with get_connection() as conn:
        row = conn.execute(sql, (sample, compound)).fetchone()
        if row is None:
            raise LookupError(f"EIC not found for {compound} in {sample}")

    comp = read_compound(compound)
    label_atoms = comp.label_atoms

    time = np.frombuffer(zlib.decompress(row["x_axis"]), dtype=np.float64)
    inten = np.frombuffer(zlib.decompress(row["y_axis"]), dtype=np.float64)
    if label_atoms > 0:
        inten = inten.reshape(
            (
                label_atoms,
                len(inten) // label_atoms + 1,
            )  # floor division works as embedded arrays are same length
        )
    return EIC(sample, compound, time, inten)
