"""Compare every sheet name and cell value of two .xlsx exports.

    uv run python scripts/diff_export.py baseline.xlsx candidate.xlsx

Exits 0 when both workbooks hold the same sheets in the same order and every
cell value is identical, and 1 otherwise, printing each difference.
"""

from __future__ import annotations

import sys
from itertools import zip_longest
from pathlib import Path

from openpyxl import load_workbook

MAX_REPORTED = 50


def _rows(sheet) -> list[tuple]:
    return [tuple(row) for row in sheet.iter_rows(values_only=True)]


def diff_workbooks(base: Path, candidate: Path) -> list[str]:
    a = load_workbook(base, read_only=True, data_only=False)
    b = load_workbook(candidate, read_only=True, data_only=False)
    try:
        if a.sheetnames != b.sheetnames:
            return [f"sheet names differ: {a.sheetnames} != {b.sheetnames}"]
        diffs = []
        for name in a.sheetnames:
            rows_a, rows_b = _rows(a[name]), _rows(b[name])
            for r, (row_a, row_b) in enumerate(zip_longest(rows_a, rows_b, fillvalue=()), 1):
                for c, (va, vb) in enumerate(zip_longest(row_a, row_b), 1):
                    if va != vb or type(va) is not type(vb):
                        diffs.append(f"{name}!R{r}C{c}: {va!r} != {vb!r}")
        return diffs
    finally:
        a.close()
        b.close()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: diff_export.py BASELINE.xlsx CANDIDATE.xlsx", file=sys.stderr)
        return 2
    diffs = diff_workbooks(Path(argv[0]), Path(argv[1]))
    for line in diffs[:MAX_REPORTED]:
        print(line)
    if len(diffs) > MAX_REPORTED:
        print(f"... and {len(diffs) - MAX_REPORTED} more")
    if diffs:
        print(f"FAIL: {len(diffs)} cell difference(s)")
        return 1
    print("OK: every sheet and cell value identical")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
