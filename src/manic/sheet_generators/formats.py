from __future__ import annotations

from typing import TYPE_CHECKING

from manic.validation.peak_verdict import PEAK_VERDICT_FILL, PeakVerdict

if TYPE_CHECKING:
    from xlsxwriter.format import Format

BASELINE_OFF_FONT_COLOR = "#1F5FBF"


def baseline_off_header(workbook):
    return workbook.add_format({"font_color": BASELINE_OFF_FONT_COLOR})


def peak_verdict_formats(workbook) -> dict[PeakVerdict, Format | None]:
    return {
        verdict: None if fill is None else workbook.add_format({"bg_color": fill})
        for verdict, fill in PEAK_VERDICT_FILL.items()
    }
