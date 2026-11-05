"""Write the full Excel export of both cached bench databases, for diffing two commits.

    uv run python bench/export.py .benchmarks/export-base
    uv run python scripts/diff_export.py .benchmarks/export-base-labelled.xlsx <candidate>-labelled.xlsx

Uses the same settings as the `export` bench stage, so run the bench once first
to build the databases.
"""

from __future__ import annotations

import sys
from pathlib import Path

from conftest import CASES, cached_db

from manic.io.data_exporter import DataExporter


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: export.py OUTPUT_PREFIX", file=sys.stderr)
        return 2
    for name, case in CASES.items():
        cached_db(case)
        exporter = DataExporter(case.mode)
        exporter.set_internal_standard(case.internal_standard)
        exporter.set_use_legacy_integration(False)
        path = Path(f"{argv[0]}-{name}.xlsx")
        assert exporter.export_to_excel(path, include_carbon_enrichment=case.labelled)
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
