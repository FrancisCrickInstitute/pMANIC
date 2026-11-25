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


def read_eics_batch(samples: List[str], compound: Compound) -> List[EIC]:
    """Batch read raw EIC data for multiple samples and a single compound."""
    if not samples:
        return []

    compound_name = compound.compound_name
    placeholders = ",".join(["?"] * len(samples))
    sql = f"""
        SELECT sample_name, x_axis, y_axis
        FROM eic
        WHERE compound_name=? AND sample_name IN ({placeholders}) AND deleted=0
    """
    params = [compound_name] + samples

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    if not rows:
        raise LookupError(
            f"No EIC data found for {compound_name} in any of the requested samples"
        )

    channel_count = compound.channel_count
    results_by_sample = {}
    for row in rows:
        time = np.frombuffer(zlib.decompress(row["x_axis"]), dtype=np.float64)
        inten = np.frombuffer(zlib.decompress(row["y_axis"]), dtype=np.float64)
        if channel_count > 1:
            inten = inten.reshape((channel_count, len(inten) // channel_count))
        results_by_sample[row["sample_name"]] = EIC(
            row["sample_name"], compound_name, time, inten
        )

    return [
        results_by_sample[sample_name]
        for sample_name in samples
        if sample_name in results_by_sample
    ]


def read_eic(sample: str, compound: Compound) -> EIC:
    """Read raw EIC data for one sample and compound."""
    compound_name = compound.compound_name
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

    channel_count = compound.channel_count
    time = np.frombuffer(zlib.decompress(row["x_axis"]), dtype=np.float64)
    inten = np.frombuffer(zlib.decompress(row["y_axis"]), dtype=np.float64)
    if channel_count > 1:
        inten = inten.reshape(
            (
                channel_count,
                len(inten) // channel_count,
            )
        )
    return EIC(sample, compound_name, time, inten)
