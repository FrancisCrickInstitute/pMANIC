from __future__ import annotations

from typing import Callable

from manic.io.compound_reader import read_compound, read_compound_with_session
from manic.validation.unlabelled_identity import QualifierRatioResult


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


def write(
    workbook,
    exporter,
    progress_callback: Callable[[int], None] | None = None,
) -> None:
    """Write long-form targeted results, identity QC, and method metadata."""

    provider = exporter._provider
    samples = provider.get_all_samples()
    compound_rows = provider.get_all_compounds()
    compounds = [read_compound(row["compound_name"]) for row in compound_rows]
    compound_meta = {row["compound_name"]: row for row in compound_rows}

    bulk_data = provider.load_bulk_sample_data()
    mrrf_values = {}
    assumed_rf: set = set()
    if exporter.internal_standard_compound:
        try:
            mrrf_values = provider.get_mrrf_values(
                compound_rows,
                exporter.internal_standard_compound,
                internal_standard_isotope_index=0,
                assumed=assumed_rf,
            )
        except TypeError:
            # Providers without provenance support (e.g. in-memory) treat every
            # response factor as measured; uncalibrated labelling is skipped.
            mrrf_values = provider.get_mrrf_values(
                compound_rows,
                exporter.internal_standard_compound,
            )

    results = workbook.add_worksheet("Targeted Results")
    result_headers = [
        "Sample",
        "Compound",
        "Q Ion m/z",
        "Q Ion Area",
        "Response Ratio to Internal Standard",
        "Estimated Amount",
        "Result Type",
        "Identity Status",
        "Observed RT (min)",
        "RT Error (min)",
        "Identity Reasons",
    ]
    _write_header(results, workbook, result_headers)

    qc_sheet = workbook.add_worksheet("Qualifier QC")
    qc_headers = [
        "Sample",
        "Compound",
        "V Ion",
        "V Ion m/z",
        "Observed Ratio (V Ion/Q Ion)",
        "Expected Ratio",
        "Fractional Tolerance",
        "Pass",
    ]
    _write_header(qc_sheet, workbook, qc_headers)

    result_row = 1
    qc_row = 1
    total = max(1, len(samples) * len(compounds))
    completed = 0
    for sample in samples:
        sample_data = bulk_data.get(sample, {})
        internal_standard_area = None
        if exporter.internal_standard_compound:
            internal_areas = sample_data.get(
                exporter.internal_standard_compound, []
            )
            if internal_areas and internal_areas[0] > 0:
                internal_standard_area = float(internal_areas[0])

        for compound in compounds:
            areas = sample_data.get(compound.compound_name, [])
            quantifier_area = float(areas[0]) if areas else 0.0
            response_ratio = (
                quantifier_area / internal_standard_area
                if internal_standard_area
                else None
            )

            estimated_amount = None
            result_type = "Q ion peak area"
            meta = compound_meta[compound.compound_name]
            internal_meta = compound_meta.get(
                exporter.internal_standard_compound
            )
            mrrf = mrrf_values.get(compound.compound_name)
            can_estimate = (
                internal_standard_area
                and internal_meta is not None
                and _positive(internal_meta["int_std_amount"])
                and _positive(meta["amount_in_std_mix"])
                and _positive(mrrf)
            )
            if can_estimate:
                estimated_amount = (
                    quantifier_area
                    * float(internal_meta["int_std_amount"])
                    / internal_standard_area
                    / float(mrrf)
                )
                if compound.compound_name in assumed_rf:
                    result_type = (
                        "Uncalibrated estimate (response factor assumed = 1.0)"
                    )
                else:
                    result_type = "Semi-quantitative estimate (single-point RF)"
            elif response_ratio is not None:
                result_type = "Relative response ratio"

            try:
                qc = provider.assess_unlabelled_identity(
                    sample, compound.compound_name
                )
            except (LookupError, ValueError):
                # Extraction legitimately skips compounds with no detectable
                # signal in a sample; report that instead of aborting export.
                qc = None
            results.write_row(
                result_row,
                0,
                [
                    sample,
                    compound.compound_name,
                    compound.analysis_channels[0].mz,
                    quantifier_area,
                    response_ratio,
                    estimated_amount,
                    result_type,
                    qc.status.value if qc is not None else "unavailable",
                    qc.observed_rt if qc is not None else None,
                    qc.rt_error if qc is not None else None,
                    (
                        "; ".join(qc.reasons)
                        if qc is not None and qc.reasons
                        else ("EIC or compound data unavailable" if qc is None else "")
                    ),
                ],
            )
            result_row += 1

            qualifier_results = (
                qc.qualifier_ratios
                if qc is not None
                else tuple(
                    QualifierRatioResult(channel, None, None)
                    for channel in compound.analysis_channels[1:]
                )
            )
            for ratio in qualifier_results:
                qc_sheet.write_row(
                    qc_row,
                    0,
                    [
                        sample,
                        compound.compound_name,
                        ratio.channel.ordinal,
                        ratio.channel.mz,
                        ratio.observed_ratio,
                        ratio.channel.expected_ratio,
                        ratio.channel.ratio_tolerance,
                        _pass_label(ratio.passed, qc_available=qc is not None),
                    ],
                )
                qc_row += 1

            completed += 1
            if progress_callback:
                progress_callback(int(completed / total * 90))

    method = workbook.add_worksheet("Targeted Method")
    method_notes = [
        ("Analysis mode", "Unlabelled targeted GC-MS"),
        ("Quantification", "Q-ion integrated area; V ions are not added to the response"),
        (
            "Identity interpretation",
            "RT and qualifier ratios support identity but do not replace "
            "library-spectrum confirmation",
        ),
        (
            "Estimated amounts",
            "Semi-quantitative single-point response-factor estimates; "
            "not a validated calibration curve",
        ),
        (
            "Uncalibrated estimates",
            "Compounds without a measured standard response use an assumed "
            "response factor of 1.0 and are flagged as uncalibrated",
        ),
        (
            "tR",
            "Ion table is the loaded method. Current tR table is the session "
            "value used for integration and identity QC after Apply",
        ),
    ]
    for row, note in enumerate(method_notes):
        method.write_row(row, 0, note)
    method.set_column(0, 0, 24)
    method.set_column(1, 1, 100)

    ion_headers = [
        "Compound",
        "Role",
        "Ordinal",
        "m/z",
        "Expected Ratio",
        "Fractional Tolerance",
        "RT Tolerance (min)",
    ]
    ion_title_row = len(method_notes) + 1
    method.write(ion_title_row, 0, "Ion definitions")
    ion_header_row = ion_title_row + 1
    for column, header in enumerate(ion_headers):
        method.write(ion_header_row, column, header)
    method_row = ion_header_row + 1
    for compound in compounds:
        for channel in compound.analysis_channels:
            method.write_row(
                method_row,
                0,
                [
                    compound.compound_name,
                    channel.role.value,
                    channel.ordinal,
                    channel.mz,
                    channel.expected_ratio,
                    channel.ratio_tolerance,
                    compound.rt_tolerance,
                ],
            )
            method_row += 1

    current_headers = ["Sample", "Compound", "tR (min)"]
    current_title_row = method_row + 1
    method.write(current_title_row, 0, "Current tR")
    current_header_row = current_title_row + 1
    for column, header in enumerate(current_headers):
        method.write(current_header_row, column, header)
    method_row = current_header_row + 1
    for sample in samples:
        for compound in compounds:
            current = read_compound_with_session(compound.compound_name, sample)
            method.write_row(
                method_row,
                0,
                [sample, current.compound_name, current.retention_time],
            )
            method_row += 1

    if progress_callback:
        progress_callback(100)
