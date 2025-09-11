from __future__ import annotations

import logging
from typing import List

from manic.models.database import get_connection

logger = logging.getLogger(__name__)


def write(workbook, exporter, progress_callback, start_progress: int, end_progress: int, *, provider=None) -> None:
    """
    Write the 'Corrected Values' sheet.

    Extracted from DataExporter._export_corrected_values_sheet without changes in behavior.
    """
    worksheet = workbook.add_worksheet('Corrected Values')

    if provider is None:
        with get_connection() as conn:
            compounds_query = """
                SELECT compound_name, label_atoms, mass0, retention_time, mm_files
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

    # Build column structure - same as Raw Values
    compound_names = []
    masses = []
    isotopes = []
    retention_times = []

    for compound_row in compounds:
        compound_name = compound_row['compound_name']
        label_atoms = compound_row['label_atoms'] or 0
        mass0 = compound_row['mass0'] or 0
        rt = compound_row['retention_time'] or 0

        num_isotopologues = label_atoms + 1

        for isotope_idx in range(num_isotopologues):
            compound_names.append(compound_name)
            masses.append(mass0)
            isotopes.append(isotope_idx)
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
    for col, isotope in enumerate(isotopes):
        worksheet.write(2, col + 2, isotope)

    worksheet.write(3, 0, 'tR')
    worksheet.write(3, 1, None)
    for col, rt in enumerate(retention_times):
        worksheet.write(3, col + 2, rt)

    # Rows 5+: None | [Sample names] | [Corrected data values]
    for sample_idx, sample_name in enumerate(samples):
        row = 4 + sample_idx
        worksheet.write(row, 0, None)
        worksheet.write(row, 1, sample_name)

        # Get all corrected data for this sample
        sample_data = (provider.get_sample_corrected_data(sample_name) if provider is not None
                       else exporter._get_sample_corrected_data(sample_name))

        # Write data values in column order
        col = 2
        for compound_row in compounds:
            compound_name = compound_row['compound_name']
            label_atoms = compound_row['label_atoms'] or 0
            num_isotopologues = label_atoms + 1

            isotopologue_data = sample_data.get(compound_name, [0.0] * num_isotopologues)

            for isotope_idx in range(num_isotopologues):
                area_value = isotopologue_data[isotope_idx] if isotope_idx < len(isotopologue_data) else 0.0
                worksheet.write(row, col, area_value)
                col += 1

        if progress_callback and (sample_idx + 1) % 5 == 0:
            progress = start_progress + (sample_idx + 1) / len(samples) * (end_progress - start_progress)
            progress_callback(int(progress))
