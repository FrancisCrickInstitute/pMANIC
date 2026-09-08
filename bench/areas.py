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
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
LEVELS = {"4": ("auto", "balanced"), "7": ("auto", "off")}
TOLERANCES = (1e-9, 1e-6, 1e-4, 1e-3, 1e-2)
EXPECTED_MODES = ("labelled", "unlabelled")
METADATA_KEY = "__manic_area_snapshot_v1__"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _discover_databases(cache: Path = CACHE) -> dict[str, Path]:
    databases = {}
    for mode in EXPECTED_MODES:
        matches = sorted(cache.glob(f"{mode}-*.db"))
        if len(matches) != 1:
            sys.exit(
                f"expected one {mode} database under {cache}, found {len(matches)}; "
                "the bench keeps one per workload, so run `uv run pytest bench` "
                "with the options for the workload you want to snapshot"
            )
        databases[mode] = matches[0]
    return databases


def _dataset_provenance(data: Path = BENCH_DATA) -> dict[str, str]:
    """Identity of the generated data, not of the database built from it.

    The cached database is rebuilt (under a new name) whenever the importer or
    schema changes, but the fitter only sees the EIC data, so snapshots taken
    on either side of such a change are still comparable.
    """
    return {
        mode: _file_sha256(data / mode / "manifest.json") for mode in EXPECTED_MODES
    }


def _cell_areas(job: tuple[str, str, str, list[str], str]) -> dict[str, np.ndarray]:
    db, mode, name, samples, level = job
    database.DB_FILE = Path(db)
    fit_type, noise_gate = LEVELS[level]
    compound = read_compound(name)
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
        values = np.asarray(areas, dtype=np.float64)
        rows[f"{mode}|{level}|{name}|{eic.sample_name}"] = values
    return rows


def _snapshot_path(out: Path) -> Path:
    return out if out.suffix == ".npz" else out.with_name(f"{out.name}.npz")


def _save_snapshot(
    out: Path, table: dict[str, np.ndarray], provenance: dict[str, str]
) -> Path:
    out = _snapshot_path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    payload = {
        METADATA_KEY: np.asarray(json.dumps(provenance, sort_keys=True)),
        **table,
    }
    try:
        with temporary.open("xb") as handle:
            np.savez(handle, **payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, out)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return out


def snapshot(out: Path) -> None:
    databases = _discover_databases()
    provenance = _dataset_provenance()
    jobs = []
    for mode, db in databases.items():
        database.DB_FILE = db
        names = list_compound_names()
        samples = list_active_samples()
        jobs += [
            (str(db), mode, name, samples, level)
            for level in LEVELS
            for name in names
        ]
    started = time.perf_counter()
    table: dict[str, np.ndarray] = {}
    with ProcessPoolExecutor() as pool:
        for rows in pool.map(_cell_areas, jobs, chunksize=4):
            table.update(rows)
    saved = _save_snapshot(out, table, provenance)
    print(f"{len(table)} cells in {time.perf_counter() - started:.0f}s -> {saved}")


def _relative_difference(before: np.ndarray, after: np.ndarray) -> float:
    """Largest per-channel change relative to that channel, floored at 1 unit.

    Per channel rather than per cell so a minor isotopologue moving from 1 to
    1000 next to an M+0 of 1e6 is reported. Non-finite input yields nan.
    """
    if before.shape != after.shape or before.size == 0:
        return np.nan
    scale = np.maximum(np.abs(before), 1.0)
    return float(np.max(np.abs(before - after) / scale))


def _load_snapshot(path: Path) -> tuple[dict[str, str], dict[str, np.ndarray]]:
    with np.load(path, allow_pickle=False) as archive:
        if METADATA_KEY not in archive.files:
            sys.exit(f"{path} has no provenance metadata; regenerate it")
        metadata = json.loads(str(archive[METADATA_KEY].item()))
        table = {
            key: np.array(archive[key], copy=True)
            for key in archive.files
            if key != METADATA_KEY
        }
    if not isinstance(metadata, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in metadata.items()
    ):
        sys.exit(f"invalid database provenance in {path}")
    return metadata, table


def diff(before_path: Path, after_path: Path, show: int) -> None:
    before_metadata, before = _load_snapshot(before_path)
    after_metadata, after = _load_snapshot(after_path)
    if before_metadata != after_metadata:
        sys.exit(
            "snapshots were fitted from different generated datasets; "
            "regenerate both against the same testdata/bench"
        )
    if set(before) != set(after):
        sys.exit("snapshots cover different cells; regenerate both on the same bench data")
    scored = {key: _relative_difference(before[key], after[key]) for key in before}
    unusable = sorted(key for key, rel in scored.items() if np.isnan(rel))
    for key in unusable:
        print(f"not comparable  {key}: before {before[key]} after {after[key]}")
    rows = sorted(
        ((rel, key) for key, rel in scored.items() if not np.isnan(rel)), reverse=True
    )
    by_level: dict[str, list[float]] = {}
    for rel, key in rows:
        by_level.setdefault(key.split("|", 3)[1], []).append(rel)
    for level, values in sorted(by_level.items()):
        rel = np.asarray(values)
        counts = "  ".join(
            f">{tol:g}: {int(np.sum(rel > tol))}" for tol in TOLERANCES
        )
        identical = int(np.sum(rel == 0))
        print(
            f"level {level}: {rel.size} cells  "
            f"identical: {identical}  {counts}"
        )
    for rel, key in rows[:show]:
        if rel == 0:
            break
        print(f"\n{rel:.3e}  {key}")
        print(f"  before {np.array2string(before[key], precision=1, max_line_width=200)}")
        print(f"  after  {np.array2string(after[key], precision=1, max_line_width=200)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    snap = commands.add_parser("snapshot", help="fit every cell and write an .npz table")
    snap.add_argument("out", type=Path)
    compare = commands.add_parser("diff", help="compare two snapshot tables")
    compare.add_argument("before", type=Path)
    compare.add_argument("after", type=Path)
    compare.add_argument(
        "--show", type=int, default=10, help="largest differences to print"
    )
    args = parser.parse_args()
    if args.command == "snapshot":
        snapshot(args.out)
    else:
        diff(args.before, args.after, args.show)


if __name__ == "__main__":
    main()
