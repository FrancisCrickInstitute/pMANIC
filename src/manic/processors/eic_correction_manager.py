"""
Natural abundance correction helpers for display preview and export validation.
"""

import logging
import zlib
from typing import Optional

import numpy as np

from manic.io.compound_reader import Compound, read_compound
from manic.models.database import get_connection
from manic.processors.natural_abundance_correction import (
    NaturalAbundanceCorrectionError,
    NaturalAbundanceCorrector,
)

logger = logging.getLogger(__name__)


def make_time_series_corrector(compound: Compound):
    """Return a time-series corrector for chromatogram preview, or None if unlabelled/no formula."""
    if not compound.formula or (compound.label_atoms or 0) <= 0:
        return None
    corrector = NaturalAbundanceCorrector()

    def apply(values: np.ndarray) -> np.ndarray:
        raw = np.asarray(values, dtype=np.float64)
        try:
            return corrector.correct_time_series(
                raw,
                compound.formula,
                compound.label_type,
                compound.label_atoms,
                compound.tbdms,
                compound.meox,
                compound.me,
            )
        except NaturalAbundanceCorrectionError:
            logger.warning(
                "Display correction failed for %s; using raw trace",
                compound.compound_name,
            )
            return raw

    return apply


def make_area_corrector(compound: Compound):
    """Return an area corrector for a labelled compound, or None if unlabelled/no formula."""
    if not compound.formula or (compound.label_atoms or 0) <= 0:
        return None
    corrector = NaturalAbundanceCorrector()

    def apply(values: np.ndarray) -> np.ndarray:
        raw = np.asarray(values, dtype=np.float64)
        return corrector.correct_areas(
            raw,
            compound.formula,
            compound.label_type,
            compound.label_atoms,
            compound.tbdms,
            compound.meox,
            compound.me,
        )

    return apply


def uncorrectable_reason(compound: Compound) -> Optional[str]:
    """Why a labelled compound gets no corrected areas, or None when correction can run."""
    if (compound.label_atoms or 0) <= 0:
        return None
    if not compound.formula:
        return "no formula"
    try:
        NaturalAbundanceCorrector()._get_cached_correction_matrix(
            compound.formula,
            compound.label_type,
            compound.label_atoms,
            compound.tbdms,
            compound.meox,
            compound.me,
        )
    except NaturalAbundanceCorrectionError as exc:
        return str(exc)
    return None


def ensure_corrections_for_export() -> None:
    """Refuse export if any active labelled compound with EICs cannot be corrected."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT c.compound_name
            FROM eic e
            JOIN compounds c ON e.compound_name = c.compound_name
            WHERE e.deleted = 0
              AND c.deleted = 0
              AND c.label_atoms > 0
            ORDER BY c.compound_name
            """
        ).fetchall()
        if not rows:
            return

        failed: list[str] = []
        for row in rows:
            name = row["compound_name"]
            compound = read_compound(name)
            reason = uncorrectable_reason(compound)
            if reason is not None:
                failed.append(f"{name} ({reason})")
                continue

            expected_channels = (compound.label_atoms or 0) + 1
            eic_rows = conn.execute(
                "SELECT x_axis, y_axis FROM eic "
                "WHERE compound_name = ? AND deleted = 0",
                (name,),
            ).fetchall()
            for eic_row in eic_rows:
                n_times = len(zlib.decompress(eic_row["x_axis"])) // 8
                n_vals = len(zlib.decompress(eic_row["y_axis"])) // 8
                if n_vals != expected_channels * n_times:
                    failed.append(name)
                    break

    if failed:
        raise RuntimeError(
            "Natural abundance correction failed for: "
            + ", ".join(failed)
            + ". Fix the formula or label_atoms for these compounds, "
            "or delete them, then export again."
        )
