"""Append one benchmark run to bench/history.tsv, or print the history.

    uv run python -m pytest bench --bench-repeat 3 --benchmark-json=RUN.json
    uv run python scripts/record_bench.py RUN.json --machine "Apple M1 Pro, 8 cores"
    uv run python scripts/record_bench.py

Each stage becomes one row: the median of its benchmarks' medians, in
milliseconds, and the fewest rounds any of them ran. With no JSON the history
is printed as a table, one line per stage and one column per run.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

HISTORY = Path(__file__).resolve().parents[1] / "bench" / "history.tsv"
COLUMNS = ["date", "commit", "machine", "action", "median_ms", "rounds"]


def record(run_json: Path, machine: str, history: Path = HISTORY) -> list[list[str]]:
    run = json.loads(run_json.read_text())
    if run["commit_info"]["dirty"]:
        raise ValueError("run was taken on a dirty checkout; commit first and rerun")
    commit = run["commit_info"]["id"][:8]
    date = run["datetime"][:10]
    existing = list(csv.reader(history.open(), delimiter="\t")) if history.exists() else []
    if any(row[1] == commit and row[2] == machine for row in existing[1:]):
        raise ValueError(f"{commit} on {machine!r} is already recorded")

    stages: dict[str, list[dict]] = {}
    for bench in run["benchmarks"]:
        action = bench["name"].removeprefix("test_").split("[")[0]
        stages.setdefault(action, []).append(bench["stats"])
    if not stages:
        raise ValueError("run holds no benchmarks")
    rows = [
        [
            date,
            commit,
            machine,
            action,
            f"{statistics.median(s['median'] for s in stats) * 1000:.1f}",
            str(min(s["rounds"] for s in stats)),
        ]
        for action, stats in stages.items()
    ]
    with history.open("a", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        if not existing:
            writer.writerow(COLUMNS)
        writer.writerows(rows)
    return rows


def table(history: Path = HISTORY) -> str:
    rows = list(csv.DictReader(history.open(), delimiter="\t"))
    runs = list(dict.fromkeys((r["commit"], r["machine"]) for r in rows))
    actions = list(dict.fromkeys(r["action"] for r in rows))
    cell = {(r["commit"], r["machine"], r["action"]): r["median_ms"] for r in rows}
    lines = [
        ["median ms", *(commit for commit, _ in runs)],
        ["", *(machine for _, machine in runs)],
        *([action, *(cell.get((*run, action), "-") for run in runs)] for action in actions),
    ]
    widths = [max(len(line[i]) for line in lines) for i in range(len(lines[0]))]
    return "\n".join(
        "  ".join(
            value.ljust(w) if i == 0 else value.rjust(w)
            for i, (value, w) in enumerate(zip(line, widths))
        ).rstrip()
        for line in lines
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Record or print benchmark history.")
    parser.add_argument("run_json", nargs="?", type=Path)
    parser.add_argument("--machine", help='short label, e.g. "Apple M1 Pro, 8 cores"')
    args = parser.parse_args(argv)
    if args.run_json is None:
        print(table())
        return 0
    if not args.machine:
        print("--machine is required when recording a run", file=sys.stderr)
        return 2
    try:
        rows = record(args.run_json, args.machine)
    except ValueError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    print(f"recorded {len(rows)} actions for {rows[0][1]} on {args.machine}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
