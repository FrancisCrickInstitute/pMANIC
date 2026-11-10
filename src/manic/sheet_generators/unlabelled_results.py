from __future__ import annotations

from typing import Callable

from manic.io.compound_reader import read_compound
from manic.processors.calibration import internal_standard_amount
from manic.sheet_generators.formats import baseline_off_header, peak_verdict_formats
from manic.validation.peak_verdict import PeakVerdict
from manic.validation.unlabelled_identity import (
    QualifierOutcome,
    QualifierRatioResult,
    qualifier_outcome,
)


def _positive(value) -> bool:
    return value is not None and float(value) > 0


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
    assumed_mrrf: set = set()
    if exporter.internal_standard_compound:
        mrrf_values = exporter._provider.get_mrrf_values(
            compound_rows,
            exporter.internal_standard_compound,
            internal_standard_isotope_index=0,
            assumed=assumed_mrrf,
        )
    exporter.assumed_mrrf = assumed_mrrf

    is_std_selected = exporter.internal_standard_compound is not None
    _write_q_column_headers(worksheet, compounds, baseline_off_header_format)

    worksheet.write(3, 0, "Units")
    worksheet.write(3, 1, None)
    for col, compound in enumerate(compounds):
        meta = compound_meta[compound.compound_name]
        if not is_std_selected:
            unit = "Peak Area"
        elif _positive(meta["amount_in_std_mix"]) and compound.compound_name not in assumed_mrrf:
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
        std_amount = (
            internal_standard_amount(
                internal_meta["int_std_amount"],
                internal_meta["amount_in_std_mix"],
                sample_name in mm_samples,
            )
            if internal_meta is not None
            else 0.0
        )

        for col, compound in enumerate(compounds):
            value = _q_area(areas_by_compound.get(compound.compound_name))
            mrrf = mrrf_values.get(compound.compound_name)
            if (
                exporter.internal_standard_compound
                and compound.compound_name == exporter.internal_standard_compound
            ):
                value = std_amount if std_amount > 0 else None
            elif exporter.internal_standard_compound:
                calibrated = internal_area > 0 and std_amount > 0 and _positive(mrrf)
                # An uncalibrated area under the nmol/Relative header would read as a real amount.
                value = value * std_amount / internal_area / float(mrrf) if calibrated else None
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
    worksheet = workbook.add_worksheet("Qualifier QC")
    red = workbook.add_format({"bg_color": "#FFCCCC"})
    grey = workbook.add_format({"bg_color": "#E7E6E6"})
    # Keyed by QualifierRatioResult.passed: outside tolerance, not assessed, passed.
    verdict_formats = {False: red, None: grey, True: None}
    outcome_formats = {
        QualifierOutcome.PASS: workbook.add_format({"bg_color": "#C6EFCE"}),
        QualifierOutcome.PARTIAL: workbook.add_format({"bg_color": "#FFEB9C"}),
        QualifierOutcome.FAIL: red,
        QualifierOutcome.NOT_DETECTED: grey,
        QualifierOutcome.NO_QUALIFIERS: grey,
    }

    header_labels = ("Compound Name", "Ion", "Mass", "Tolerance", "Value")
    first_sample_row = len(header_labels)
    worksheet.freeze_panes(first_sample_row, 2)

    identities = {}
    header_columns = []
    for compound in compounds:
        name = compound.compound_name
        identities[name] = provider.assess_unlabelled_identity_by_sample(name, samples)
        if progress_callback:
            # Keeps the export cancellable while the identities are read.
            progress_callback(60)
        quantifier, *qualifiers = compound.analysis_channels
        header_columns.append((name, "Quant", quantifier.mz, None, "Area"))
        header_columns += [
            (name, f"Qual {channel.ordinal}", channel.mz, channel.ratio_tolerance, value)
            for channel in qualifiers
            for value in ("Area", "Obs ratio", "Exp ratio")
        ]
        header_columns.append((name, None, None, None, "Outcome"))
        header_columns.append((None,) * len(header_labels))  # empty column between compounds

    # The workbook is constant_memory, so rows are written top to bottom.
    for row, label in enumerate(header_labels):
        worksheet.write(row, 0, label)
        for col, header in enumerate(header_columns, start=2):
            worksheet.write(row, col, header[row])

    for sample_idx, sample in enumerate(samples):
        row = first_sample_row + sample_idx
        worksheet.write(row, 1, sample)
        col = 2
        for compound in compounds:
            qc = identities[compound.compound_name][sample]
            if isinstance(qc, (LookupError, ValueError)):
                qc = None
            elif isinstance(qc, Exception):
                raise qc

            areas = bulk_data.get(sample, {}).get(compound.compound_name)
            worksheet.write(row, col, _q_area(areas))
            ratios = (
                qc.qualifier_ratios
                if qc is not None
                else tuple(
                    QualifierRatioResult(channel, None, None)
                    for channel in compound.analysis_channels[1:]
                )
            )
            for ratio in ratios:
                channel = ratio.channel
                worksheet.write(row, col + 1, _channel_area(areas, channel.ordinal))
                worksheet.write(
                    row, col + 2, ratio.observed_ratio, verdict_formats[ratio.passed]
                )
                worksheet.write(row, col + 3, channel.expected_ratio)
                col += 3
            outcome = qualifier_outcome(qc)
            worksheet.write(row, col + 1, outcome.value, outcome_formats[outcome])
            col += 3  # the Quant column, the Outcome column and the empty one

        if progress_callback:
            progress_callback(60 + int((sample_idx + 1) / len(samples) * 40))
