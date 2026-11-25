from __future__ import annotations

from manic.models.sample_note import get_sample_notes

HEADERS = ("Compound", "Sample", "Note")


def write(workbook, exporter) -> None:
    """The Notes sheet: one row per note, in compound list order then sample order.

    Notes on a deleted compound or sample stay in the session and are left out here,
    as that compound or sample is left out of every other sheet.
    """
    provider = exporter._provider
    compound_rank = {
        row["compound_name"]: rank for rank, row in enumerate(provider.get_all_compounds())
    }
    sample_rank = {name: rank for rank, name in enumerate(provider.get_all_samples())}
    notes = sorted(
        (compound_rank[compound], sample_rank[sample], compound, sample, note)
        for (compound, sample), note in get_sample_notes().items()
        if compound in compound_rank and sample in sample_rank
    )

    worksheet = workbook.add_worksheet("Notes")
    wrap = workbook.add_format({"text_wrap": True, "valign": "top"})
    top = workbook.add_format({"valign": "top"})
    worksheet.set_column(0, 1, 28, top)
    worksheet.set_column(2, 2, 80, wrap)
    for col, header in enumerate(HEADERS):
        worksheet.write_string(0, col, header)
    for row, (_, _, compound, sample, note) in enumerate(notes, start=1):
        # write_string, never write: a note starting with = + - or @ stays text.
        worksheet.write_string(row, 0, compound, top)
        worksheet.write_string(row, 1, sample, top)
        worksheet.write_string(row, 2, note, wrap)
