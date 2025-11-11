from __future__ import annotations

import logging
from typing import Dict, List

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
    Write the 'Abundances' sheet.

    Extracted from DataExporter._export_abundances_sheet without behavior changes.
    """
    worksheet = workbook.add_worksheet("Abundances")
    invalid_format = workbook.add_format({"bg_color": "#FFCCCC"})

    if provider is None:
        with get_connection() as conn:
            compounds_query = """
                SELECT compound_name, mass0, retention_time, amount_in_std_mix, int_std_amount, mm_files
                FROM compounds 
                WHERE deleted=0 
                ORDER BY id
            """
            compounds = list(conn.execute(compounds_query))
            samples: List[str] = [
                row["sample_name"]
                for row in conn.execute(
                    "SELECT sample_name FROM samples WHERE deleted=0 ORDER BY sample_name"
                )
            ]
    else:
        compounds = provider.get_all_compounds()
        samples = provider.get_all_samples()

    # Build column structure - only M+0 for each compound (total abundance)
    compound_names = []
    masses = []
    retention_times = []

    for compound_row in compounds:
        compound_name = compound_row["compound_name"]
        mass0 = compound_row["mass0"] or 0
        rt = compound_row["retention_time"] or 0

        compound_names.append(compound_name)
        masses.append(mass0)
        retention_times.append(rt)

    # Headers (5 rows)
    worksheet.write(0, 0, "Compound Name")
    worksheet.write(0, 1, None)
    for col, compound_name in enumerate(compound_names):
        worksheet.write(0, col + 2, compound_name)

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

    worksheet.write(4, 0, "Units")
    worksheet.write(4, 1, None)
    for col in range(len(compound_names)):
        worksheet.write(4, col + 2, "nmol")

    # Pre-calculate MRRF values using MM files and internal standard
    if not getattr(exporter, "internal_standard_compound", None):
        raise ValueError(
            "Internal standard must be set before generating Abundances sheet"
        )

    logger.info(
        f"Calculating MRRF values using internal standard: {exporter.internal_standard_compound}"
    )
    mrrf_values = (
        provider.get_mrrf_values(compounds, exporter.internal_standard_compound)
        if provider is not None
        else exporter._calculate_mrrf_values(
            compounds, exporter.internal_standard_compound
        )
    )

    # Get internal standard amount from compound metadata
    def _row_get(row, key):
        try:
            return row[key]
        except Exception:
            try:
                return row.get(key)
            except Exception:
                return None

    intstd_rows = [
        c
        for c in compounds
        if _row_get(c, "compound_name") == exporter.internal_standard_compound
    ]
    if not intstd_rows:
        raise ValueError(
            f"Internal standard '{exporter.internal_standard_compound}' not found in compound list"
        )

    def _resolve_mm_samples(mm_field):
        resolver = None
        if provider is not None and hasattr(provider, "resolve_mm_samples"):
            resolver = getattr(provider, "resolve_mm_samples")
        elif hasattr(exporter, "_resolve_mm_samples"):
            resolver = getattr(exporter, "_resolve_mm_samples")

        if not resolver or not mm_field:
            return set()

        try:
            return set(resolver(mm_field))
        except Exception as exc:
            logger.warning(
                "Failed to resolve MM samples for internal standard %s: %s",
                exporter.internal_standard_compound,
                exc,
            )
            return set()

    intstd_row = intstd_rows[0]
    int_std_amount_val = _row_get(intstd_row, "int_std_amount")
    if int_std_amount_val is None:
        raise ValueError(
            f"Internal standard '{exporter.internal_standard_compound}' is missing 'int_std_amount'"
        )
    internal_std_amount_default = float(int_std_amount_val)

    amount_in_mix_val = _row_get(intstd_row, "amount_in_std_mix")
    if amount_in_mix_val is None:
        raise ValueError(
            f"Internal standard '{exporter.internal_standard_compound}' is missing 'amount_in_std_mix'"
        )
    internal_std_amount_mm = float(amount_in_mix_val)

    mm_field = _row_get(intstd_row, "mm_files")
    internal_std_mm_samples = _resolve_mm_samples(mm_field)

    # Rows 6+: values per sample
    for sample_idx, sample_name in enumerate(samples):
        row = 5 + sample_idx
        worksheet.write(row, 0, None)
        worksheet.write(row, 1, sample_name)

        sample_data = (
            provider.get_sample_corrected_data(sample_name)
            if provider is not None
            else exporter._get_sample_corrected_data(sample_name)
        )

        if exporter.internal_standard_compound:
            internal_std_data = sample_data.get(
                exporter.internal_standard_compound, [0.0]
            )
            # MATLAB uses only M+0 for internal standard normalization (processIntegrals.m line 24)
            # internalStandardCorrection = integrationData(metaboliteStandard).ionsRawCorr(:, 1)
            internal_std_signal = (
                internal_std_data[0]
                if internal_std_data and len(internal_std_data) > 0
                else 0.0
            )
            sample_internal_std_amount = (
                internal_std_amount_mm
                if sample_name in internal_std_mm_samples
                else internal_std_amount_default
            )
        else:
            internal_std_signal = 1.0
            sample_internal_std_amount = 1.0

        for col, compound_row in enumerate(compounds):
            compound_name = compound_row["compound_name"]

            iso_data = sample_data.get(compound_name, [0.0])
            total_signal = sum(iso_data)

            if (
                exporter.internal_standard_compound
                and compound_name != exporter.internal_standard_compound
            ):
                mrrf = mrrf_values.get(compound_name, 1.0)
                if internal_std_signal > 0 and mrrf > 0:
                    calibrated_abundance = (
                        total_signal
                        * (sample_internal_std_amount / internal_std_signal)
                        * (1 / mrrf)
                    )
                    logger.debug(
                        f"Abundance for {compound_name}: total_signal={total_signal:.1f}, "
                        f"sample_int_std_amount={sample_internal_std_amount}, int_std_signal={internal_std_signal:.1f}, "
                        f"mrrf={mrrf:.3f}, result={calibrated_abundance:.3f} nmol"
                    )
                else:
                    calibrated_abundance = 0.0
                    logger.debug(
                        f"No valid calibration for {compound_name} (int_std_signal={internal_std_signal:.3f}, mrrf={mrrf:.3f})"
                    )
            elif (
                exporter.internal_standard_compound
                and compound_name == exporter.internal_standard_compound
            ):
                calibrated_abundance = (
                    sample_internal_std_amount
                    if sample_internal_std_amount > 0
                    else 0.0
                )
                logger.debug(
                    f"Internal standard {compound_name} abundance: {calibrated_abundance} nmol (known amount)"
                )
            else:
                calibrated_abundance = 0.0
                logger.debug(
                    f"No internal standard calibration available for {compound_name}"
                )

            if validation_data and sample_name in validation_data:
                is_valid = validation_data[sample_name].get(compound_name, True)
                if not is_valid:
                    worksheet.write(row, col + 2, calibrated_abundance, invalid_format)
                else:
                    worksheet.write(row, col + 2, calibrated_abundance)
            else:
                worksheet.write(row, col + 2, calibrated_abundance)

        if progress_callback and (sample_idx + 1) % 5 == 0:
            progress = start_progress + (sample_idx + 1) / len(samples) * (
                end_progress - start_progress
            )
            progress_callback(int(progress))

        if getattr(exporter, "internal_standard_compound", None):
            logger.info("Abundances sheet created with MRRF calibration applied")
        else:
            logger.info(
                "Abundances sheet created with raw abundance values (no internal standard)"
            )
