#!/usr/bin/env python3
"""Calibrate qualifier ratios in an unlabelled compound list through MANIC itself.

A compound list built from spectra (build_unlabelled_compound_list.py) ships
with ratios measured by simple trapezoid integration. MANIC's own pipeline
integrates with deconvolution, which measures weak channels differently, so
the imported list can flag most samples as review_required. This script runs
the list through MANIC's real import + integration path, collects the
observed qualifier/quantifier ratios across all samples, and rewrites the
expected ratios and tolerances from what the app actually measures — the
same way a lab would establish reference ratios from a set of injections.

Usage:
    uv run python scripts/calibrate_unlabelled_ratios.py <cdf_dir> <compounds.csv> \
        [--output calibrated.csv]
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
import tempfile
from pathlib import Path

import numpy as np

import manic.models.database as dbmod
from manic.io.compounds_import import import_compound_excel
from manic.io.data_provider import DataProvider
from manic.io.eic_importer import import_eics
from manic.models.analysis import AnalysisMode

SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cdf_dir", help="Directory containing the .cdf files")
    parser.add_argument("compounds_csv", help="Compound list to calibrate")
    parser.add_argument("--output", default=None, help="Output CSV (default: overwrite input)")
    args = parser.parse_args()

    csv_path = Path(args.compounds_csv)
    out_path = Path(args.output) if args.output else csv_path

    with csv_path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not rows or fieldnames is None:
        raise SystemExit(f"{csv_path} is empty")

    tmp = Path(tempfile.mkdtemp(prefix="manic_calibrate_"))
    dbmod.DB_FILE = tmp / "calibration.db"
    with sqlite3.connect(dbmod.DB_FILE) as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    import_compound_excel(csv_path, AnalysisMode.UNLABELLED)
    import_eics(args.cdf_dir)

    provider = DataProvider()
    with sqlite3.connect(dbmod.DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        samples = [
            r["sample_name"]
            for r in conn.execute("SELECT sample_name FROM samples ORDER BY sample_name")
        ]

    print(f"Calibrating against {len(samples)} samples\n")
    print(f"{'compound':<22} {'ion':>4} {'old':>7} {'new':>7} {'tol':>5} {'n':>3}")
    for row in rows:
        name = row["name"]
        observed: dict[int, list[float]] = {1: [], 2: []}
        for sample in samples:
            try:
                qc = provider.assess_unlabelled_identity(sample, name)
            except (LookupError, ValueError):
                continue
            if qc.observed_rt is None:
                continue
            for result in qc.qualifier_ratios:
                if result.observed_ratio is not None and np.isfinite(result.observed_ratio):
                    observed[result.channel.ordinal].append(result.observed_ratio)

        for ordinal in (1, 2):
            ratio_col = f"Qualifier {ordinal} Ratio"
            tol_col = f"Qualifier {ordinal} Tolerance"
            if ratio_col not in row or not row.get(f"ValIon{ordinal}"):
                continue
            values = observed[ordinal]
            if len(values) < 3:
                print(f"{name:<22} V{ordinal:<3} {row.get(ratio_col, ''):>7} {'skip':>7} {'':>5} {len(values):>3}  (too few detections)")
                continue
            old = row.get(ratio_col, "")
            median = float(np.median(values))
            mad = float(np.median(np.abs(np.asarray(values) - median)))
            frac = 1.4826 * mad / median if median > 0 else 0.0
            tol = float(np.clip(3.0 * frac, 0.30, 0.60))
            row[ratio_col] = f"{median:.4f}"
            row[tol_col] = f"{tol:.2f}"
            print(f"{name:<22} V{ordinal:<3} {old:>7} {median:7.3f} {tol:5.0%} {len(values):>3}")

    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote calibrated list to {out_path}")


if __name__ == "__main__":
    main()
