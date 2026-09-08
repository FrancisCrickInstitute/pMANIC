"""Fitted areas for every compound x sample cell, for diffing two commits.

The bench times code; it does not say whether an optimisation changed the
answers. This does. Run it once per commit and diff the two tables:

    uv run python bench/areas.py snapshot /tmp/before.npz
    git switch <branch>
    uv run python bench/areas.py snapshot /tmp/after.npz
    uv run python bench/areas.py diff /tmp/before.npz /tmp/after.npz

Snapshot reads the cached bench databases under bench/cache/ (run the bench once
to create them) and fits every cell in both datasets at level 4 (the shipped
default) and level 7 (the most expensive), about 6 minutes on 8 cores.
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from manic.io.compound_reader import read_compound
from manic.io.eic_reader import read_eics_batch
from manic.io.list_compound_names import list_compound_names
from manic.io.sample_reader import list_active_samples
from manic.models import database
from manic.processors.chromatographic_peak_deconvolution import deconvolve_channel_matrix
from manic.processors.integration import integrate_bundle_areas

CACHE = Path(__file__).resolve().parent / "cache"
LEVELS = {"4": ("auto", "balanced"), "7": ("auto", "off")}
TOLERANCES = (1e-9, 1e-6, 1e-4, 1e-3, 1e-2)


def _cell_areas(job: tuple[str, str, list[str], str]) -> dict[str, np.ndarray]:
    db, name, samples, level = job
    database.DB_FILE = Path(db)
    fit_type, noise_gate = LEVELS[level]
    compound = read_compound(name)
    mode = Path(db).stem.split("-")[0]
    rows = {}
    for eic in read_eics_batch(samples, compound, use_corrected=False):
        matrix = np.asarray(eic.intensity, dtype=np.float64)
        bundle = deconvolve_channel_matrix(
            eic.time,
            matrix,
            retention_time=compound.retention_time,
            loffset=compound.loffset,
            roffset=compound.roffset,
            stringency=level,
            fit_type=fit_type,
            noise_gate=noise_gate,
        )
        areas, _ = integrate_bundle_areas(
            eic.time,
            bundle,
            matrix,
            baseline_correction=bool(compound.baseline_correction),
            use_legacy=False,
            retention_time=compound.retention_time,
            loffset=compound.loffset,
            roffset=compound.roffset,
            label_atoms=compound.label_atoms,
            channel_count=matrix.shape[0] if matrix.ndim > 1 else 1,
        )
        rows[f"{mode}|{level}|{name}|{eic.sample_name}"] = np.asarray(areas, dtype=np.float64)
    return rows


def snapshot(out: Path) -> None:
    databases = sorted(CACHE.glob("*.db"))
    if not databases:
        sys.exit(f"no cached bench databases under {CACHE}; run `uv run pytest bench` first")
    jobs = []
    for db in databases:
        database.DB_FILE = db
        names = list_compound_names()
        samples = list_active_samples()
        jobs += [(str(db), name, samples, level) for level in LEVELS for name in names]
    started = time.perf_counter()
    table: dict[str, np.ndarray] = {}
    with ProcessPoolExecutor() as pool:
        for rows in pool.map(_cell_areas, jobs, chunksize=4):
            table.update(rows)
    np.savez(out, **table)
    print(f"{len(table)} cells in {time.perf_counter() - started:.0f}s -> {out}")


def _relative_difference(before: np.ndarray, after: np.ndarray) -> float:
    scale = max(float(np.max(np.abs(before))), 1.0)
    return float(np.max(np.abs(before - after))) / scale


def diff(before_path: Path, after_path: Path, show: int) -> None:
    before = np.load(before_path)
    after = np.load(after_path)
    if set(before.files) != set(after.files):
        sys.exit("snapshots cover different cells; regenerate both on the same bench data")
    rows = sorted(
        ((_relative_difference(before[key], after[key]), key) for key in before.files),
        reverse=True,
    )
    by_level: dict[str, list[float]] = {}
    for rel, key in rows:
        by_level.setdefault(key.split("|")[1], []).append(rel)
    for level, values in sorted(by_level.items()):
        rel = np.asarray(values)
        counts = "  ".join(f">{tol:g}: {int(np.sum(rel > tol))}" for tol in TOLERANCES)
        print(f"level {level}: {rel.size} cells  identical: {int(np.sum(rel == 0))}  {counts}")
    for rel, key in rows[:show]:
        if rel == 0:
            break
        print(f"\n{rel:.3e}  {key}")
        print(f"  before {np.array2string(before[key], precision=1, max_line_width=200)}")
        print(f"  after  {np.array2string(after[key], precision=1, max_line_width=200)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    snap = commands.add_parser("snapshot", help="fit every cell and write an .npz table")
    snap.add_argument("out", type=Path)
    compare = commands.add_parser("diff", help="compare two snapshot tables")
    compare.add_argument("before", type=Path)
    compare.add_argument("after", type=Path)
    compare.add_argument("--show", type=int, default=10, help="largest differences to print")
    args = parser.parse_args()
    if args.command == "snapshot":
        snapshot(args.out)
    else:
        diff(args.before, args.after, args.show)


if __name__ == "__main__":
    main()
