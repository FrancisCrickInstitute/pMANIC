"""Fitted areas for every compound x sample cell, for diffing two commits.

The bench times code; it does not say whether an optimisation changed the
answers. This does. Run it once per commit and diff the two tables:

    uv run python bench/areas.py snapshot .benchmarks/areas-before.npz
    git switch <branch>
    uv run python bench/areas.py snapshot .benchmarks/areas-after.npz
    uv run python bench/areas.py diff .benchmarks/areas-before.npz .benchmarks/areas-after.npz

Snapshot reads the cached bench databases under bench/cache/ (run the bench once
to create them) and fits every cell in both datasets at level 4 (the shipped
default) and level 7 (the most expensive), about 6 minutes on 8 cores. Each
snapshot records the dataset manifests it was fitted from, so two snapshots
compare only when they describe the same generated data, whichever commit
built the databases.

`snapshot --perturb 1e-12` nudges every intensity by a random relative amount
of that size before fitting. Diffing it against an unperturbed snapshot of the
same commit counts the cells whose answer depends on last-digit arithmetic,
which is what differs between machines and BLAS libraries:

    uv run python bench/areas.py snapshot .benchmarks/areas.npz
    uv run python bench/areas.py snapshot --perturb 1e-12 .benchmarks/areas-perturbed.npz
    uv run python bench/areas.py diff .benchmarks/areas.npz .benchmarks/areas-perturbed.npz
"""

from __future__ import annotations

import argparse
import hashlib
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
BENCH_DATA = Path(__file__).resolve().parents[1] / "testdata" / "bench"
MODES = ("labelled", "unlabelled")
LEVELS = {"4": ("auto", "balanced"), "7": ("auto", "off")}
TOLERANCES = (1e-9, 1e-6, 1e-4, 1e-3, 1e-2)
PROVENANCE_KEY = "manifest_sha256"


def _discover_databases(cache: Path = CACHE) -> dict[str, Path]:
    databases = {}
    for mode in MODES:
        matches = sorted(cache.glob(f"{mode}-*.db"))
        if len(matches) != 1:
            sys.exit(
                f"expected one {mode} database under {cache}, found {len(matches)}; "
                "the bench keeps one per workload, so run `uv run pytest bench` "
                "with the options for the workload you want to snapshot"
            )
        databases[mode] = matches[0]
    return databases


def _dataset_provenance(data: Path = BENCH_DATA) -> str:
    """Identity of the generated data, not of the database built from it.

    The cached database is rebuilt (under a new name) whenever the importer or
    schema changes, but the fitter only sees the EIC data, so snapshots taken
    on either side of such a change are still comparable.
    """
    return " ".join(
        hashlib.sha256((data / mode / "manifest.json").read_bytes()).hexdigest()
        for mode in MODES
    )


def _perturbed(matrix: np.ndarray, key: str, eps: float) -> np.ndarray:
    """Nudge every intensity by a random relative amount in [-eps, eps], seeded by cell."""
    seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "little")
    noise = np.random.default_rng(seed).uniform(-eps, eps, size=matrix.shape)
    return matrix * (1.0 + noise)


def _cell_areas(job: tuple[str, str, str, list[str], str, float]) -> dict[str, np.ndarray]:
    db, mode, name, samples, level, eps = job
    database.DB_FILE = Path(db)
    fit_type, noise_gate = LEVELS[level]
    compound = read_compound(name)
    rows = {}
    for eic in read_eics_batch(samples, compound, use_corrected=False):
        key = f"{mode}|{level}|{name}|{eic.sample_name}"
        matrix = np.asarray(eic.intensity, dtype=np.float64)
        if eps:
            matrix = _perturbed(matrix, key, eps)
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
        rows[key] = np.asarray(areas, dtype=np.float64)
    return rows


def snapshot(out: Path, eps: float = 0.0) -> None:
    databases = _discover_databases()
    provenance = _dataset_provenance()
    jobs = []
    for mode, db in databases.items():
        database.DB_FILE = db
        names = list_compound_names()
        samples = list_active_samples()
        jobs += [
            (str(db), mode, name, samples, level, eps) for level in LEVELS for name in names
        ]
    started = time.perf_counter()
    table: dict[str, np.ndarray] = {}
    with ProcessPoolExecutor() as pool:
        for rows in pool.map(_cell_areas, jobs, chunksize=4):
            table.update(rows)
    _save_snapshot(out, table, provenance)
    print(f"{len(table)} cells in {time.perf_counter() - started:.0f}s -> {out}")


def _save_snapshot(out: Path, table: dict[str, np.ndarray], provenance: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, **{PROVENANCE_KEY: np.asarray(provenance)}, **table)


def _relative_difference(before: np.ndarray, after: np.ndarray) -> float:
    """Largest per-channel change relative to that channel, floored at 1 unit.

    Per channel rather than per cell so a minor isotopologue moving from 1 to
    1000 next to an M+0 of 1e6 is reported. Non-finite input yields nan.
    """
    if before.shape != after.shape or before.size == 0:
        return np.nan
    scale = np.maximum(np.abs(before), 1.0)
    return float(np.max(np.abs(before - after) / scale))


def _load_snapshot(path: Path) -> tuple[str, dict[str, np.ndarray]]:
    archive = np.load(path)
    table = {key: archive[key] for key in archive.files if key != PROVENANCE_KEY}
    return str(archive[PROVENANCE_KEY]), table


def diff(before_path: Path, after_path: Path, show: int) -> None:
    before_provenance, before = _load_snapshot(before_path)
    after_provenance, after = _load_snapshot(after_path)
    if before_provenance != after_provenance:
        sys.exit(
            "snapshots were fitted from different generated datasets; "
            "regenerate both against the same testdata/bench"
        )
    if set(before) != set(after):
        sys.exit("snapshots cover different cells; regenerate both on the same bench data")
    scored = {key: _relative_difference(before[key], after[key]) for key in before}
    for key in sorted(key for key, rel in scored.items() if np.isnan(rel)):
        print(f"not comparable  {key}: before {before[key]} after {after[key]}")
    rows = sorted(
        ((rel, key) for key, rel in scored.items() if not np.isnan(rel)), reverse=True
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
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    snap = commands.add_parser("snapshot", help="fit every cell and write an .npz table")
    snap.add_argument("out", type=Path)
    snap.add_argument(
        "--perturb",
        type=float,
        default=0.0,
        metavar="EPS",
        help="nudge every intensity by up to EPS relative before fitting (try 1e-12)",
    )
    compare = commands.add_parser("diff", help="compare two snapshot tables")
    compare.add_argument("before", type=Path)
    compare.add_argument("after", type=Path)
    compare.add_argument("--show", type=int, default=10, help="largest differences to print")
    args = parser.parse_args()
    if args.command == "snapshot":
        snapshot(args.out, args.perturb)
    else:
        diff(args.before, args.after, args.show)


if __name__ == "__main__":
    main()
