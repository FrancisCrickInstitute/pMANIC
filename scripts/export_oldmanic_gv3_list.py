#!/usr/bin/env python3
"""Export a pythonMANIC unlabelled compound list in OLD_MANIC Gv3 format.

OLD_MANIC's unlabelled mode loads .xls/.xlsx files with exactly these columns:
    name, tR, lOffset, rOffset, QIon, ValIon1, ValIon2, tR_Window

Both ValIons are mandatory there (rows missing ValIon2 are dropped with a
warning), and the ratio/tolerance columns are dropped because OLD_MANIC never
performed automated ratio QC — it only integrated the three ions and overlaid
the scaled V-ion traces for visual confirmation.

Usage:
    uv run python scripts/export_oldmanic_gv3_list.py <compounds.csv> [--output out.xlsx]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

OLD_MANIC_COLUMNS = [
    "name",
    "tR",
    "lOffset",
    "rOffset",
    "QIon",
    "ValIon1",
    "ValIon2",
    "tR_Window",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compounds_csv", help="pythonMANIC unlabelled compound list (CSV)")
    parser.add_argument("--output", default=None, help="Destination .xlsx (default: <input>_gv3.xlsx)")
    args = parser.parse_args()

    csv_path = Path(args.compounds_csv)
    out_path = (
        Path(args.output)
        if args.output
        else csv_path.with_name(f"{csv_path.stem}_gv3.xlsx")
    )

    df = pd.read_csv(csv_path)

    def _norm(name: str) -> str:
        return str(name).strip().lower().replace(" ", "").replace("_", "")

    df.columns = [_norm(c) for c in df.columns]
    df = df.rename(
        columns={
            "quantion": "qion",
            "qualifierion1": "valion1",
            "qualifierion2": "valion2",
            "trwindow": "tr_window",
        }
    )

    required = {"name", "tr", "loffset", "roffset", "qion", "valion1", "valion2"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"{csv_path.name}: missing column(s): {', '.join(sorted(missing))}")

    before = len(df)
    df = df[df["valion2"].notna() & (df["valion2"].astype(str).str.strip() != "")]
    dropped = before - len(df)
    if dropped:
        print(f"Dropped {dropped} row(s) without ValIon2 (mandatory in OLD_MANIC Gv3)")

    out = pd.DataFrame(
        {
            "name": df["name"],
            "tR": df["tr"].astype(float),
            "lOffset": df["loffset"].astype(float),
            "rOffset": df["roffset"].astype(float),
            "QIon": df["qion"].astype(float).astype(int),
            "ValIon1": df["valion1"].astype(float).astype(int),
            "ValIon2": df["valion2"].astype(float).astype(int),
            "tR_Window": (
                df["tr_window"].astype(float)
                if "tr_window" in df
                else df[["loffset", "roffset"]].max(axis=1).astype(float)
            ),
        },
        columns=OLD_MANIC_COLUMNS,
    )

    out.to_excel(out_path, index=False)
    print(f"Wrote {len(out)} compounds in OLD_MANIC Gv3 format to {out_path}")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
