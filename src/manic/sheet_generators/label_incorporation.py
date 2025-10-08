from __future__ import annotations

import logging
from typing import List

from manic.models.database import get_connection

logger = logging.getLogger(__name__)


def write(workbook, exporter, progress_callback, start_progress: int, end_progress: int, *, provider=None) -> None:
    """
    Write the '% Label Incorporation' sheet.

    Extracted from DataExporter._export_label_incorporation_sheet.
    """
    worksheet = workbook.add_worksheet('% Label Incorporation')

    if provider is None:
        with get_connection() as conn:
            compounds_query = """
                SELECT compound_name, mass0, retention_time, label_atoms, amount_in_std_mix, int_std_amount, mm_files
                FROM compounds 
                WHERE deleted=0 
                ORDER BY id
            """
            compounds = list(conn.execute(compounds_query))
            samples: List[str] = [row['sample_name'] for row in 
                      conn.execute("SELECT sample_name FROM samples WHERE deleted=0 ORDER BY sample_name")]
    else:
        compounds = provider.get_all_compounds()
        samples = provider.get_all_samples()

    # Build column structure - only compounds with labeling (M+0 base)
    compound_names = []
    masses = []
    retention_times = []

    for compound_row in compounds:
        compound_name = compound_row['compound_name']
        mass0 = compound_row['mass0'] or 0
        rt = compound_row['retention_time'] or 0

        compound_names.append(compound_name)
        masses.append(mass0)
        retention_times.append(rt)

    # Headers
    worksheet.write(0, 0, 'Compound Name')
    worksheet.write(0, 1, None)
    for col, compound_name in enumerate(compound_names):
        worksheet.write(0, col + 2, compound_name)

    worksheet.write(1, 0, 'Mass')
    worksheet.write(1, 1, None)
    for col, mass in enumerate(masses):
        worksheet.write(1, col + 2, mass)

    worksheet.write(2, 0, 'Isotope')
    worksheet.write(2, 1, None)
    for col in range(len(compound_names)):
        worksheet.write(2, col + 2, 0)

    worksheet.write(3, 0, 'tR')
    worksheet.write(3, 1, None)
    for col, rt in enumerate(retention_times):
        worksheet.write(3, col + 2, rt)

    # Background ratios from MM files
    logger.info("Calculating background ratios from MM files for % label incorporation...")
    background_ratios = (provider.get_background_ratios(compounds) if provider is not None
                         else exporter._calculate_background_ratios(compounds))

    # Rows 5+: values per sample
    for sample_idx, sample_name in enumerate(samples):
        row = 4 + sample_idx
        worksheet.write(row, 0, None)
        worksheet.write(row, 1, sample_name)

        sample_data = (provider.get_sample_corrected_data(sample_name) if provider is not None
                       else exporter._get_sample_corrected_data(sample_name))

        for col, compound_row in enumerate(compounds):
            try:
                compound_name = compound_row['compound_name']
            except (KeyError, IndexError) as e:
                logger.error(f"Error accessing compound_name for compound {col}: {e}")
                continue

            isotopologue_data = sample_data.get(compound_name, [0.0])

            if len(isotopologue_data) > 1:
                m0_signal = isotopologue_data[0]
                raw_labeled_signal = sum(isotopologue_data[1:])

                background_ratio = background_ratios.get(compound_name, 0.0)
                corrected_labeled_signal = raw_labeled_signal - (background_ratio * m0_signal)
                corrected_labeled_signal = max(0.0, corrected_labeled_signal)

                # MATLAB uses the ORIGINAL total signal (allSum) in denominator (processIntegrals.m line 56)
                # tmp = (correctedCounts ./ allSum) .* 100
                # NOT the corrected total (m0 + corrected_labeled)
                total_signal = sum(isotopologue_data)  # Original uncorrected total
                label_percentage = (corrected_labeled_signal / total_signal) * 100 if total_signal > 0 else 0.0
            else:
                label_percentage = 0.0

            worksheet.write(row, col + 2, label_percentage)

        if progress_callback and (sample_idx + 1) % 5 == 0:
            progress = start_progress + (sample_idx + 1) / len(samples) * (end_progress - start_progress)
            progress_callback(int(progress))

    logger.info("% Label Incorporation sheet created with background correction applied")
