from __future__ import annotations

import logging
from typing import Dict, List

from manic.models.database import get_connection

logger = logging.getLogger(__name__)


def calculate_enrichment(isotopologue_data: List[float], label_atoms: int) -> float:
    """
    Calculate Average Enrichment from corrected intensity data.

    Formula: 100 * Sum(i * Area_i) / (N * Sum(Area_total))
    where i is the isotopologue index and N is the number of labellable atoms.

    Args:
        isotopologue_data: List of areas [M+0, M+1, M+2, ...]
        label_atoms: Number of labelable atoms (N)

    Returns:
        Enrichment percentage (0-100)
    """
    total_signal = sum(isotopologue_data)
    if label_atoms <= 0 or total_signal <= 0:
        return 0.0

    weighted_sum = 0.0
    for i, area in enumerate(isotopologue_data):
        weight = min(i, label_atoms)
        weighted_sum += weight * area

    return (weighted_sum / (label_atoms * total_signal)) * 100.0


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
    Write the '% Carbons Labelled' sheet.

    Calculates the carbon enrichment relative to the Standard Mixture (MM) background.
    This represents the excess labelling above natural/background levels.
    """
    worksheet = workbook.add_worksheet("% Carbons Labelled")
    invalid_format = workbook.add_format({"bg_color": "#FFCCCC"})
    baseline_off_header_format = workbook.add_format({"bg_color": "#FFF2CC"})

    # 1. Fetch Metadata
    if provider is None:
        with get_connection() as conn:
            compounds_query = """
                SELECT compound_name, mass0, retention_time, label_atoms, mm_files, baseline_correction
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

    # 2. Pre-calculate Baseline Enrichment from MM Files
    baseline_enrichment: Dict[str, float] = {}

    if provider is not None:
        logger.info("Calculating baseline carbon enrichment from MM files...")

        for compound_row in compounds:
            if isinstance(compound_row, dict):
                name = compound_row["compound_name"]
                label_atoms = int(compound_row.get("label_atoms") or 0)
                mm_pattern = compound_row.get("mm_files")
            else:
                name = compound_row["compound_name"]
                label_atoms = int(compound_row["label_atoms"] or 0)
                mm_pattern = compound_row["mm_files"]

            mm_samples = provider.resolve_mm_samples(mm_pattern)

            if not mm_samples or label_atoms == 0:
                baseline_enrichment[name] = 0.0
                continue

            total_mm_enrichment = 0.0
            valid_mm_count = 0

            for mm_sample in mm_samples:
                mm_data = provider.get_sample_corrected_data(mm_sample).get(name, [0.0])
                enrichment = calculate_enrichment(mm_data, label_atoms)

                if sum(mm_data) > 0:
                    total_mm_enrichment += enrichment
                    valid_mm_count += 1

            if valid_mm_count > 0:
                baseline_enrichment[name] = total_mm_enrichment / valid_mm_count
            else:
                baseline_enrichment[name] = 0.0
    else:
        logger.warning(
            "No provider available - APE background subtraction not applied. "
            "Reporting absolute enrichment instead."
        )

    # 3. Build Headers
    compound_names = []
    masses = []
    retention_times = []

    for compound_row in compounds:
        compound_names.append(compound_row["compound_name"])
        if isinstance(compound_row, dict):
            masses.append(compound_row.get("mass0") or 0)
            retention_times.append(compound_row.get("retention_time") or 0)
        else:
            masses.append(compound_row["mass0"] or 0)
            retention_times.append(compound_row["retention_time"] or 0)

    worksheet.write(0, 0, "Compound Name")
    worksheet.write(0, 1, None)
    for col, compound_row in enumerate(compounds):
        if isinstance(compound_row, dict):
            name = compound_row["compound_name"]
            baseline_flag = bool(compound_row.get("baseline_correction"))
        else:
            name = compound_row["compound_name"]
            baseline_flag = bool(compound_row["baseline_correction"])

        header_fmt = None if baseline_flag else baseline_off_header_format
        worksheet.write(0, col + 2, name, header_fmt)

    worksheet.write(1, 0, "Mass")
    worksheet.write(1, 1, None)
    for col, mass in enumerate(masses):
        worksheet.write(1, col + 2, mass)

    worksheet.write(2, 0, "Isotope")
    worksheet.write(2, 1, None)
    for col in range(len(compound_names)):
        worksheet.write(2, col + 2, 0)

    worksheet.write(3, 0, "tR")
    worksheet.write(3, 1, None)
    for col, rt in enumerate(retention_times):
        worksheet.write(3, col + 2, rt)

    # 4. Calculate and Write Data
    for sample_idx, sample_name in enumerate(samples):
        row = 4 + sample_idx
        worksheet.write(row, 0, None)
        worksheet.write(row, 1, sample_name)

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

            isotopologue_data = sample_data.get(compound_name, [0.0])

            # A. Calculate Absolute Enrichment
            abs_enrichment = calculate_enrichment(isotopologue_data, label_atoms)

            # B. Subtract Baseline (Calculation)
            baseline = baseline_enrichment.get(compound_name, 0.0)
            ape_value = abs_enrichment - baseline

            # C. Clamp to 0 (no negative enrichment)
            final_value = max(0.0, ape_value)

            if validation_data and sample_name in validation_data:
                is_valid = validation_data[sample_name].get(compound_name, True)
                if not is_valid:
                    worksheet.write(row, col + 2, final_value, invalid_format)
                else:
                    worksheet.write(row, col + 2, final_value)
            else:
                worksheet.write(row, col + 2, final_value)

        if progress_callback and (sample_idx + 1) % 5 == 0:
            progress = start_progress + (sample_idx + 1) / len(samples) * (
                end_progress - start_progress
            )
            progress_callback(int(progress))

    logger.info("% Carbons Labelled (APE) sheet created")
