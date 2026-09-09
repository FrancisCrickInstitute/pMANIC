from __future__ import annotations

from typing import Callable

from manic.io.compound_reader import read_compound
from manic.sheet_generators.formats import baseline_off_header, peak_verdict_formats
from manic.validation.peak_verdict import PeakVerdict
from manic.validation.unlabelled_identity import (
    QUALIFIER_OUTCOME_FILL,
    QualifierOutcome,
    QualifierRatioResult,
    qualifier_outcome,
)


def _write_header(worksheet, workbook, headers: list[str]) -> None:
    header_format = workbook.add_format(
        {"bold": True, "bg_color": "#D9EAF7", "border": 1}
    )
    for column, header in enumerate(headers):
        worksheet.write(0, column, header, header_format)
        worksheet.set_column(column, column, max(12, min(36, len(header) + 3)))


def _positive(value) -> bool:
    return value is not None and float(value) > 0


def _pass_label(passed: bool | None, qc_available: bool) -> str | None:
    if passed is not None:
        return "PASS" if passed else "REVIEW"
    return None if qc_available else "N/A"


def _channel_area(areas: list[float] | None, ordinal: int) -> float:
    if not areas or ordinal >= len(areas):
        return 0.0
    return float(areas[ordinal])


def _q_area(areas: list[float] | None) -> float:
    return _channel_area(areas, 0)


def write(
    workbook,
    exporter,
    progress_callback: Callable[[int], None] | None = None,
    validation_data=None,
) -> None:
    provider = exporter._provider
    samples = provider.get_all_samples()
    compound_rows = provider.get_all_compounds()
    compounds = [read_compound(row["compound_name"]) for row in compound_rows]
    compound_meta = {row["compound_name"]: row for row in compound_rows}
    bulk_data = provider.load_bulk_sample_data()

    _write_raw_values(
        workbook,
        samples,
        compounds,
        bulk_data,
        validation_data,
    )
    if progress_callback:
        progress_callback(30)

    _write_abundances(
        workbook,
        exporter,
        samples,
        compounds,
        compound_rows,
        compound_meta,
        bulk_data,
        validation_data,
    )
    if progress_callback:
        progress_callback(60)

    _write_qualifier_qc(
        workbook,
        provider,
        samples,
        compounds,
        bulk_data,
        progress_callback,
    )
    if progress_callback:
        progress_callback(100)


def _write_q_column_headers(worksheet, compounds, baseline_off_header_format) -> None:
    worksheet.write(0, 0, "Compound Name")
    worksheet.write(0, 1, None)
    for col, compound in enumerate(compounds):
        header_fmt = (
            None if compound.baseline_correction else baseline_off_header_format
        )
        worksheet.write(0, col + 2, compound.compound_name, header_fmt)

    worksheet.write(1, 0, "Mass")
    worksheet.write(1, 1, None)
    for col, compound in enumerate(compounds):
        worksheet.write(1, col + 2, compound.analysis_channels[0].mz)

    worksheet.write(2, 0, "tR")
    worksheet.write(2, 1, None)
    for col, compound in enumerate(compounds):
        worksheet.write(2, col + 2, compound.retention_time)


def _write_raw_values(workbook, samples, compounds, bulk_data, validation_data) -> None:
    worksheet = workbook.add_worksheet("Raw Values")
    verdict_formats = peak_verdict_formats(workbook)
    baseline_off_header_format = baseline_off_header(workbook)
    _write_q_column_headers(worksheet, compounds, baseline_off_header_format)

    for sample_idx, sample_name in enumerate(samples):
        row = 3 + sample_idx
        worksheet.write(row, 0, None)
        worksheet.write(row, 1, sample_name)
        areas_by_compound = bulk_data.get(sample_name, {})
        sample_verdicts = (validation_data or {}).get(sample_name, {})
        for col, compound in enumerate(compounds):
            value = _q_area(areas_by_compound.get(compound.compound_name))
            fmt = verdict_formats[sample_verdicts.get(compound.compound_name, PeakVerdict.PASS)]
            worksheet.write(row, col + 2, value, fmt)


def _write_abundances(
    workbook,
    exporter,
    samples,
    compounds,
    compound_rows,
    compound_meta,
    bulk_data,
    validation_data,
) -> None:
    worksheet = workbook.add_worksheet("Abundances")
    verdict_formats = peak_verdict_formats(workbook)
    rel_unit_format = workbook.add_format({"bg_color": "#D9D9D9"})
    baseline_off_header_format = baseline_off_header(workbook)

    mrrf_values = {}
    if exporter.internal_standard_compound:
        try:
            mrrf_values = exporter._provider.get_mrrf_values(
                compound_rows,
                exporter.internal_standard_compound,
                internal_standard_isotope_index=0,
            )
        except TypeError:
            mrrf_values = exporter._provider.get_mrrf_values(
                compound_rows,
                exporter.internal_standard_compound,
            )

    is_std_selected = exporter.internal_standard_compound is not None
    _write_q_column_headers(worksheet, compounds, baseline_off_header_format)

    worksheet.write(3, 0, "Units")
    worksheet.write(3, 1, None)
    for col, compound in enumerate(compounds):
        meta = compound_meta[compound.compound_name]
        if not is_std_selected:
            unit = "Peak Area"
        elif _positive(meta["amount_in_std_mix"]):
            unit = "nmol"
        else:
            unit = "Relative"
        unit_fmt = rel_unit_format if unit == "Relative" else None
        worksheet.write(3, col + 2, unit, unit_fmt)

    internal_meta = compound_meta.get(exporter.internal_standard_compound)
    mm_samples = set()
    if internal_meta is not None:
        mm_samples = set(
            exporter._provider.resolve_mm_samples(internal_meta["mm_files"])
        )

    for sample_idx, sample_name in enumerate(samples):
        row = 4 + sample_idx
        worksheet.write(row, 0, None)
        worksheet.write(row, 1, sample_name)
        areas_by_compound = bulk_data.get(sample_name, {})
        sample_verdicts = (validation_data or {}).get(sample_name, {})
        internal_area = _q_area(
            areas_by_compound.get(exporter.internal_standard_compound)
        )
        if internal_meta is not None:
            std_amount = (
                float(internal_meta["amount_in_std_mix"])
                if sample_name in mm_samples
                and _positive(internal_meta["amount_in_std_mix"])
                else float(internal_meta["int_std_amount"] or 0.0)
            )
        else:
            std_amount = 1.0

        for col, compound in enumerate(compounds):
            value = _q_area(areas_by_compound.get(compound.compound_name))
            mrrf = mrrf_values.get(compound.compound_name)
            if (
                exporter.internal_standard_compound
                and compound.compound_name == exporter.internal_standard_compound
            ):
                value = std_amount if std_amount > 0 else value
            elif (
                exporter.internal_standard_compound
                and internal_area > 0
                and _positive(internal_meta["int_std_amount"] if internal_meta else None)
                and _positive(mrrf)
            ):
                value = value * std_amount / internal_area / float(mrrf)
            fmt = verdict_formats[sample_verdicts.get(compound.compound_name, PeakVerdict.PASS)]
            worksheet.write(row, col + 2, value, fmt)


def _write_qualifier_qc(
    workbook,
    provider,
    samples,
    compounds,
    bulk_data,
    progress_callback,
) -> None:
    qc_sheet = workbook.add_worksheet("Qualifier QC")
    qc_headers = [
        "Sample",
        "Compound",
        "Q Ion m/z",
        "Q Ion Area",
        "Qualifier Ion",
        "Qualifier Ion m/z",
        "Qualifier Ion Area",
        "Observed Ratio (Qualifier Ion/Q Ion)",
        "Expected Ratio",
        "Fractional Tolerance",
        "Pass",
        "Outcome",
    ]
    _write_header(qc_sheet, workbook, qc_headers)
    outcome_formats = {
        outcome: workbook.add_format(
            {
                "bg_color": fill,
                "font_color": (
                    "#000000" if outcome is QualifierOutcome.PARTIAL else "#FFFFFF"
                ),
            }
        )
        for outcome, fill in QUALIFIER_OUTCOME_FILL.items()
    }

    qc_row = 1
    total = max(1, len(samples) * len(compounds))
    completed = 0
    for sample in samples:
        for compound in compounds:
            try:
                qc = provider.assess_unlabelled_identity(
                    sample, compound.compound_name
                )
            except (LookupError, ValueError):
                qc = None

            outcome = qualifier_outcome(qc)
            row_format = outcome_formats[outcome]
            areas = bulk_data.get(sample, {}).get(compound.compound_name)
            q_area = _q_area(areas)
            qualifier_results = (
                qc.qualifier_ratios
                if qc is not None
                else tuple(
                    QualifierRatioResult(channel, None, None)
                    for channel in compound.analysis_channels[1:]
                )
            )
            for ratio in qualifier_results:
                values = [
                    sample,
                    compound.compound_name,
                    compound.analysis_channels[0].mz,
                    q_area,
                    ratio.channel.ordinal,
                    ratio.channel.mz,
                    _channel_area(areas, ratio.channel.ordinal),
                    ratio.observed_ratio,
                    ratio.channel.expected_ratio,
                    ratio.channel.ratio_tolerance,
                    _pass_label(ratio.passed, qc_available=qc is not None),
                    outcome.value,
                ]
                for column, value in enumerate(values):
                    qc_sheet.write(qc_row, column, value, row_format)
                qc_row += 1

            completed += 1
            if progress_callback:
                progress_callback(60 + int(completed / total * 40))
