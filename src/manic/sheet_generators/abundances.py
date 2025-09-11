from __future__ import annotations

import logging
from typing import List, Dict

from manic.models.database import get_connection

logger = logging.getLogger(__name__)


def write(workbook, exporter, progress_callback, start_progress: int, end_progress: int) -> None:
    """
    Write the 'Abundances' sheet.

    Extracted from DataExporter._export_abundances_sheet without behavior changes.
    """
    worksheet = workbook.add_worksheet('Abundances')

    # Get all compounds and their metadata in order
    with get_connection() as conn:
        compounds_query = """
            SELECT compound_name, mass0, retention_time, amount_in_std_mix, int_std_amount, mm_files
            FROM compounds 
            WHERE deleted=0 
            ORDER BY id
        """
        compounds = list(conn.execute(compounds_query))

        samples: List[str] = [row['sample_name'] for row in 
                  conn.execute("SELECT sample_name FROM samples WHERE deleted=0 ORDER BY sample_name")]

    # Build column structure - only M+0 for each compound (total abundance)
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

    # Headers (5 rows)
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

    worksheet.write(4, 0, 'Units')
    worksheet.write(4, 1, None)
    for col in range(len(compound_names)):
        worksheet.write(4, col + 2, 'nmol')

    # Pre-calculate MRRF values using MM files and internal standard
    if not exporter.internal_standard_compound:
        logger.warning("No internal standard selected - using raw abundance values")
        mrrf_values: Dict[str, float] = {}
        internal_std_amount = 1.0
    else:
        logger.info(
            f"Calculating MRRF values using internal standard: {exporter.internal_standard_compound}"
        )
        mrrf_values = exporter._calculate_mrrf_values(compounds, exporter.internal_standard_compound)

        # Get internal standard amount from compound metadata
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT int_std_amount FROM compounds WHERE compound_name = ? AND deleted = 0",
                (exporter.internal_standard_compound,),
            )
            row = cursor.fetchone()
            try:
                internal_std_amount = (
                    row['int_std_amount'] if row and row['int_std_amount'] is not None else 1.0
                )
            except (KeyError, TypeError):
                internal_std_amount = 1.0
                logger.debug(
                    f"int_std_amount not found for {exporter.internal_standard_compound}, using default 1.0"
                )

    # Rows 6+: values per sample
    for sample_idx, sample_name in enumerate(samples):
        row = 5 + sample_idx
        worksheet.write(row, 0, None)
        worksheet.write(row, 1, sample_name)

        sample_data = exporter._get_sample_corrected_data(sample_name)

        if exporter.internal_standard_compound:
            internal_std_data = sample_data.get(exporter.internal_standard_compound, [0.0])
            internal_std_signal = sum(internal_std_data) if internal_std_data else 0.0
        else:
            internal_std_signal = 1.0

        for col, compound_row in enumerate(compounds):
            compound_name = compound_row['compound_name']

            iso_data = sample_data.get(compound_name, [0.0])
            total_signal = sum(iso_data)

            if exporter.internal_standard_compound and compound_name != exporter.internal_standard_compound:
                mrrf = mrrf_values.get(compound_name, 1.0)
                if internal_std_signal > 0 and mrrf > 0:
                    calibrated_abundance = (
                        total_signal * (internal_std_amount / internal_std_signal) * (1 / mrrf)
                    )
                    logger.debug(
                        f"Abundance for {compound_name}: total_signal={total_signal:.1f}, "
                        f"int_std_amount={internal_std_amount}, int_std_signal={internal_std_signal:.1f}, "
                        f"mrrf={mrrf:.3f}, result={calibrated_abundance:.3f} nmol"
                    )
                else:
                    calibrated_abundance = 0.0
                    logger.debug(
                        f"No valid calibration for {compound_name} (int_std_signal={internal_std_signal:.3f}, mrrf={mrrf:.3f})"
                    )
            elif exporter.internal_standard_compound and compound_name == exporter.internal_standard_compound:
                calibrated_abundance = internal_std_amount if internal_std_amount > 0 else 0.0
                logger.debug(
                    f"Internal standard {compound_name} abundance: {calibrated_abundance} nmol (known amount)"
                )
            else:
                calibrated_abundance = 0.0
                logger.debug(
                    f"No internal standard calibration available for {compound_name}"
                )

            worksheet.write(row, col + 2, calibrated_abundance)

        if progress_callback and (sample_idx + 1) % 5 == 0:
            progress = start_progress + (sample_idx + 1) / len(samples) * (end_progress - start_progress)
            progress_callback(int(progress))

    if exporter.internal_standard_compound:
        logger.info("Abundances sheet created with MRRF calibration applied")
    else:
        logger.info("Abundances sheet created with raw abundance values (no internal standard)")

