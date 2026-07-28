from __future__ import annotations

from typing import Callable

from manic.io.compound_reader import read_compound


def _write_header(worksheet, workbook, headers: list[str]) -> None:
    header_format = workbook.add_format(
        {"bold": True, "bg_color": "#D9EAF7", "border": 1}
    )
    for column, header in enumerate(headers):
        worksheet.write(0, column, header, header_format)
        worksheet.set_column(column, column, max(12, min(36, len(header) + 3)))


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
    if exporter.internal_standard_compound:
        mrrf_values = provider.get_mrrf_values(
            compound_rows,
            exporter.internal_standard_compound,
            internal_standard_isotope_index=0,
        )

    results = workbook.add_worksheet("Targeted Results")
    result_headers = [
        "Sample",
        "Compound",
        "Quantifier m/z",
        "Quantifier Area",
        "Response Ratio to Internal Standard",
        "Estimated Amount",
        "Result Type",
        "Identity Status",
        "Observed RT (min)",
        "RT Error (min)",
    ]
    _write_header(results, workbook, result_headers)

    qc_sheet = workbook.add_worksheet("Qualifier QC")
    qc_headers = [
        "Sample",
        "Compound",
        "Qualifier",
        "Qualifier m/z",
        "Observed Ratio (Qualifier/QIon)",
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
            result_type = "Quantifier peak area"
            meta = compound_meta[compound.compound_name]
            internal_meta = compound_meta.get(
                exporter.internal_standard_compound
            )
            mrrf = mrrf_values.get(compound.compound_name)
            if (
                internal_standard_area
                and internal_meta is not None
                and internal_meta["int_std_amount"] is not None
                and float(internal_meta["int_std_amount"]) > 0
                and meta["amount_in_std_mix"] is not None
                and float(meta["amount_in_std_mix"]) > 0
                and mrrf is not None
                and float(mrrf) > 0
            ):
                estimated_amount = (
                    quantifier_area
                    * float(internal_meta["int_std_amount"])
                    / internal_standard_area
                    / float(mrrf)
                )
                result_type = "Semi-quantitative estimate (single-point RF)"
            elif response_ratio is not None:
                result_type = "Relative response ratio"

            qc = provider.assess_unlabelled_identity(
                sample, compound.compound_name
            )
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
                    qc.status.value,
                    qc.observed_rt,
                    qc.rt_error,
                ],
            )
            result_row += 1

            for ratio in qc.qualifier_ratios:
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
                        (
                            None
                            if ratio.passed is None
                            else ("PASS" if ratio.passed else "REVIEW")
                        ),
                    ],
                )
                qc_row += 1

            completed += 1
            if progress_callback:
                progress_callback(int(completed / total * 90))

    method = workbook.add_worksheet("Targeted Method")
    method.write_row(0, 0, ["Analysis mode", "Unlabelled targeted GC-MS"])
    method.write_row(
        1,
        0,
        [
            "Quantification",
            "Quantifier-ion integrated area; qualifiers are not added to the response",
        ],
    )
    method.write_row(
        2,
        0,
        [
            "Identity interpretation",
            "RT and qualifier ratios support identity but do not replace library-spectrum confirmation",
        ],
    )
    method.write_row(
        3,
        0,
        [
            "Estimated amounts",
            "Semi-quantitative single-point response-factor estimates; not a validated calibration curve",
        ],
    )
    method.set_column(0, 0, 24)
    method.set_column(1, 1, 100)
    method_headers = [
        "Compound",
        "Role",
        "Ordinal",
        "m/z",
        "Expected Ratio",
        "Fractional Tolerance",
        "Reference RT (min)",
        "RT Tolerance (min)",
    ]
    for column, header in enumerate(method_headers):
        method.write(5, column, header)
    method_row = 6
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
                    compound.retention_time,
                    compound.rt_tolerance,
                ],
            )
            method_row += 1

    if progress_callback:
        progress_callback(100)
