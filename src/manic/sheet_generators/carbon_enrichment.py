from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from manic.models.database import get_connection

logger = logging.getLogger(__name__)


def write(
    workbook,
    exporter,
    progress_callback,
    start_progress: int,
    end_progress: int,
    *,
    provider=None,
    validation_data=None,
) -> None:
    """
    Write the '% Carbons Labelled' sheet (Average Enrichment).
    Calculates the percentage of the total carbon pool that is labelled.

    Formula: 100 * Sum(i * Area_i) / (N * Sum(Area_total))
    where i is the isotopologue index (0 to N) and N is the number of labelable atoms.
    """
    worksheet = workbook.add_worksheet("% Carbons Labelled")
    invalid_format = workbook.add_format({"bg_color": "#FFCCCC"})

    # 1. Fetch Metadata
    if provider is None:
        with get_connection() as conn:
            # We specifically need label_atoms here for the denominator
            compounds_query = """
                SELECT compound_name, mass0, retention_time, label_atoms 
                FROM compounds 
                WHERE deleted=0 
                ORDER BY id
            """
            compounds = list(conn.execute(compounds_query))
            samples = [
                row["sample_name"]
                for row in conn.execute(
                    "SELECT sample_name FROM samples WHERE deleted=0 ORDER BY sample_name"
                )
            ]
    else:
        compounds = provider.get_all_compounds()
        samples = provider.get_all_samples()

    # 2. Build Headers
    compound_names = []
    masses = []
    retention_times = []

    for compound_row in compounds:
        compound_names.append(compound_row["compound_name"])
        # Handle both dict and sqlite3.Row access
        if isinstance(compound_row, dict):
            masses.append(compound_row.get("mass0") or 0)
            retention_times.append(compound_row.get("retention_time") or 0)
        else:
            masses.append(compound_row["mass0"] or 0)
            retention_times.append(compound_row["retention_time"] or 0)

    # Row 0-3 headers
    worksheet.write(0, 0, "Compound Name")
    worksheet.write(0, 1, None)  # Spacer column
    for col, name in enumerate(compound_names):
        worksheet.write(0, col + 2, name)

    worksheet.write(1, 0, "Mass")
    worksheet.write(1, 1, None)
    for col, mass in enumerate(masses):
        worksheet.write(1, col + 2, mass)

    worksheet.write(
        2, 0, "Isotope"
    )  # Or Label Atoms, but Isotope matches other sheets visually
    worksheet.write(2, 1, None)
    for col in range(len(compound_names)):
        worksheet.write(2, col + 2, 0)  # Placeholder row matching other sheets

    worksheet.write(3, 0, "tR")
    worksheet.write(3, 1, None)
    for col, rt in enumerate(retention_times):
        worksheet.write(3, col + 2, rt)

    # 3. Calculate and Write Data
    for sample_idx, sample_name in enumerate(samples):
        row = 4 + sample_idx
        worksheet.write(row, 0, None)
        worksheet.write(row, 1, sample_name)

        # Get Corrected Data (Natural Abundance Removed)
        # Note: We use the base NAC corrected data, NOT the MM-subtracted data used in Label Incorporation
        if provider is not None:
            sample_data = provider.get_sample_corrected_data(sample_name)
        else:
            sample_data = exporter._get_sample_corrected_data(sample_name)

        for col, compound_row in enumerate(compounds):
            if isinstance(compound_row, dict):
                compound_name = compound_row["compound_name"]
                label_atoms = int(compound_row.get("label_atoms") or 0)
            else:
                compound_name = compound_row["compound_name"]
                label_atoms = int(compound_row["label_atoms"] or 0)

            # Get list of areas [M+0, M+1, M+2...]
            isotopologue_data = sample_data.get(compound_name, [0.0])

            enrichment_percent = 0.0

            # Calculation only possible if compound is labelable and has signal
            total_signal = sum(isotopologue_data)

            if label_atoms > 0 and total_signal > 0:
                weighted_sum = 0.0

                # Iterate through M+0, M+1, M+2...
                # i is the number of labelled carbons in that isotopologue
                for i, area in enumerate(isotopologue_data):
                    # Safety: don't exceed theoretical label atoms
                    # Any signal at M+(>N) is treated as if it has N labels (or ignored? usually capped at N)
                    # Standard practice: cap the weight at N, or ignore indices > N.
                    # Let's cap the index at label_atoms to be safe against noise peaks
                    weight = min(i, label_atoms)
                    weighted_sum += weight * area

                # Formula: Sum(i * Area_i) / (N * Sum(Area_total))
                enrichment_ratio = weighted_sum / (label_atoms * total_signal)
                enrichment_percent = enrichment_ratio * 100.0

            # Write value with validation coloring
            if validation_data and sample_name in validation_data:
                is_valid = validation_data[sample_name].get(compound_name, True)
                if not is_valid:
                    worksheet.write(row, col + 2, enrichment_percent, invalid_format)
                else:
                    worksheet.write(row, col + 2, enrichment_percent)
            else:
                worksheet.write(row, col + 2, enrichment_percent)

        # Progress update
        if progress_callback and (sample_idx + 1) % 5 == 0:
            progress = start_progress + (sample_idx + 1) / len(samples) * (
                end_progress - start_progress
            )
            progress_callback(int(progress))

    logger.info("% Carbons Labelled sheet created")
