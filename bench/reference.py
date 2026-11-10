"""The exported results of both bench datasets, kept in git so a changed number shows.

    uv run python bench/reference.py check
    uv run python bench/reference.py update --pr 281 --why "EMG tail no longer clipped"

`check` exports both datasets with the current code and compares every cell with
bench/reference/<dataset>.tsv. It fails when a number moved by more than 0.05%, or
when any text, sheet or cell appeared or disappeared. CI runs it on every pull request.

`update` rewrites those files and adds an entry to bench/reference/HISTORY.md saying
which pull request changed the results, why, and by how much on each sheet. A pull
request that means to change results runs it and commits the outcome, so the history
of the reference files is the history of the science.

The datasets are the synthetic ones the bench uses; generate them first with
`uv run python scripts/generate_bench_data.py --mode both` (running the bench does it too).
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
import tempfile
from datetime import date
from itertools import zip_longest
from pathlib import Path

from openpyxl import load_workbook

REFERENCE = Path(__file__).parent / "reference"
HISTORY = REFERENCE / "HISTORY.md"
# The same code gives slightly different fits on another machine: a GitHub macOS runner
# differed from the Apple M1 Pro that made the reference in 22 of 52,569 numbers, by
# 0.004% at most. 0.05% clears that noise and is far below any change that matters.
RELATIVE_TOLERANCE = 5e-4
ABSOLUTE_TOLERANCE = 1e-9

Sheets = dict[str, list[list[str]]]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{value:.7g}"
    return str(value).replace("\t", " ").replace("\n", " ")


def render(workbook: Path) -> Sheets:
    """Every sheet as rows of text cells, numbers to seven significant digits."""
    book = load_workbook(workbook, read_only=True, data_only=True)
    try:
        return {
            sheet.title: [[_cell(v) for v in row] for row in sheet.iter_rows(values_only=True)]
            for sheet in book.worksheets
        }
    finally:
        book.close()


def write(sheets: Sheets, path: Path) -> None:
    lines = []
    for title, rows in sheets.items():
        lines.append(f"## {title}")
        lines.extend("\t".join(row).rstrip("\t") for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read(path: Path) -> Sheets:
    sheets: Sheets = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            rows = sheets.setdefault(line[3:], [])
        else:
            rows.append(line.split("\t"))
    return sheets


def _number(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def compare(old: Sheets, new: Sheets) -> dict[str, dict]:
    """Per sheet: how many numbers there are, the relative change of each one that moved,
    and how many cells changed in any other way (text, or a cell added or removed)."""
    report = {}
    for title in dict.fromkeys([*old, *new]):
        moved, other, numbers = [], 0, 0
        rows = zip_longest(old.get(title, []), new.get(title, []), fillvalue=[])
        for old_row, new_row in rows:
            for a, b in zip_longest(old_row, new_row, fillvalue=""):
                x, y = _number(a), _number(b)
                numbers += y is not None
                if a == b:
                    continue
                if x is None or y is None:
                    other += 1
                elif not math.isclose(x, y, rel_tol=RELATIVE_TOLERANCE, abs_tol=ABSOLUTE_TOLERANCE):
                    moved.append(abs(y - x) / max(abs(x), abs(y)))
        report[title] = {"numbers": numbers, "moved": moved, "other": other}
    return report


def _summary(title: str, sheet: dict) -> str:
    moved = sheet["moved"]
    # Two significant digits, so a change far below 0.01% still reads as one.
    typical = f"{statistics.median(moved) * 100:.2g}%" if moved else ""
    largest = f"{max(moved) * 100:.2g}%" if moved else ""
    return (
        f"| {title} | {sheet['numbers']} | {len(moved)} | {typical} | {largest} "
        f"| {sheet['other'] or ''} |"
    )


def _table(report: dict[str, dict]) -> list[str]:
    return [
        "| Sheet | Numbers | Changed | Typical change | Largest change | Other cells changed |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        *(_summary(title, sheet) for title, sheet in report.items()),
    ]


def _changed(report: dict[str, dict]) -> bool:
    return any(sheet["moved"] or sheet["other"] for sheet in report.values())


def current() -> dict[str, Sheets]:
    """Export both datasets with the code as it is now."""
    # The bench's own modules: imported here so the comparison loads without them.
    import export
    from conftest import CASES

    with tempfile.TemporaryDirectory() as folder:
        prefix = Path(folder) / "export"
        if export.main([str(prefix)]):
            raise SystemExit("export failed")
        return {name: render(Path(f"{prefix}-{name}.xlsx")) for name in CASES}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    update = commands.add_parser("update")
    update.add_argument("--pr", type=int, required=True, help="the pull request that changes the results")
    update.add_argument("--why", required=True, help="one sentence a scientist can read")
    args = parser.parse_args(argv)

    results = current()
    reports = {}
    for name, sheets in results.items():
        path = REFERENCE / f"{name}.tsv"
        reports[name] = compare(read(path) if path.exists() else {}, sheets)

    if args.command == "check":
        for name, report in reports.items():
            print(f"\n{name}")
            print("\n".join(_table(report)))
        if any(_changed(report) for report in reports.values()):
            print(
                "\nFAIL: exported results differ from bench/reference. If this pull request "
                "means to change them, run `bench/reference.py update --pr N --why ...` "
                "and commit the result."
            )
            return 1
        print("\nOK: exported results match bench/reference")
        return 0

    if not any(_changed(report) for report in reports.values()):
        print("Nothing changed; reference and history left as they are.")
        return 0
    entry = [f"## {date.today().isoformat()}, #{args.pr}", "", args.why, ""]
    for name, sheets in results.items():
        write(sheets, REFERENCE / f"{name}.tsv")
        if _changed(reports[name]):
            entry += [f"**{name}**", "", *_table(reports[name]), ""]
    with HISTORY.open("a", encoding="utf-8") as history:
        history.write("\n".join(entry) + "\n")
    print("\n".join(entry))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
