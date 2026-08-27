#!/usr/bin/env python3
"""Build an unlabelled (quantifier/qualifier) compound list from real CDF data.

Picks strong TIC peaks in a reference file, chooses a quantifier ion and up
to two qualifier ions from each apex spectrum, then measures retention time
and qualifier/quantifier area ratios across every file so the list ships with
data-derived expected ratios and tolerances.

The output CSV deliberately uses the legacy OLD_MANIC Gv3 header names
(QIon / ValIon1 / ValIon2); the pythonMANIC importer accepts them directly.

Usage:
    uv run python scripts/build_unlabelled_compound_list.py <cdf_dir> \
        --output compounds.csv [--targets 8] [--rt-min 4.5] [--rt-max 70]
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

from manic.io.cdf_reader import CdfFileData, read_cdf_file
from manic.processors.eic_calculator import extract_eic

# Ubiquitous column-bleed / contaminant ions that must never anchor a target
DEFAULT_EXCLUDED_MZ = {73, 75, 147, 149, 167, 207, 221, 279, 281, 355, 429}


@dataclass(slots=True)
class Target:
    name: str
    rt: float
    loffset: float
    roffset: float
    quant_mz: float
    qual_mzs: list[float] = field(default_factory=list)
    qual_ratios: list[float] = field(default_factory=list)
    qual_tolerances: list[float] = field(default_factory=list)
    rt_window: float = 0.12
    n_detected: int = 0
    rt_spread: float = 0.0


def _spectrum_at_scan(cdf: CdfFileData, scan: int) -> tuple[np.ndarray, np.ndarray]:
    start = int(cdf.scan_index[scan])
    end = (
        int(cdf.scan_index[scan + 1])
        if scan + 1 < len(cdf.scan_index)
        else len(cdf.mass)
    )
    return cdf.mass[start:end], cdf.intensity[start:end]


def _nominal(mz: np.ndarray) -> np.ndarray:
    return np.floor(mz + 0.5).astype(int)


def _pick_ions(
    masses: np.ndarray,
    intensities: np.ndarray,
    excluded: set[int],
    min_qualifier_fraction: float,
) -> tuple[float, list[float]] | None:
    """Quantifier = strongest non-ubiquitous ion; qualifiers = next strongest.

    Ions within +/-1 nominal Da of an already-chosen ion are skipped so the
    qualifier channels carry independent fragment information instead of the
    quantifier's own natural-abundance isotopologues.
    """
    if masses.size == 0:
        return None
    order = np.argsort(intensities)[::-1]
    chosen: list[int] = []
    quant: float | None = None
    quant_intensity = 0.0
    quals: list[float] = []
    for idx in order:
        nominal = int(_nominal(masses[idx : idx + 1])[0])
        if nominal in excluded:
            continue
        if any(abs(nominal - c) <= 1 for c in chosen):
            continue
        if quant is None:
            quant = float(nominal)
            quant_intensity = float(intensities[idx])
            chosen.append(nominal)
            continue
        if intensities[idx] < min_qualifier_fraction * quant_intensity:
            break
        quals.append(float(nominal))
        chosen.append(nominal)
        if len(quals) == 2:
            break
    if quant is None or not quals:
        return None
    return quant, quals


def _pick_tic_peaks(
    times_min: np.ndarray,
    tic: np.ndarray,
    n_targets: int,
    min_separation_min: float,
    prominence_fraction: float,
    rt_min: float | None,
    rt_max: float | None,
) -> np.ndarray:
    dt = float(np.median(np.diff(times_min)))
    distance = max(1, int(min_separation_min / dt))
    peaks, props = find_peaks(
        tic,
        prominence=prominence_fraction * float(tic.max()),
        distance=distance,
    )
    if rt_min is not None:
        peaks = peaks[times_min[peaks] >= rt_min]
    if rt_max is not None:
        peaks = peaks[times_min[peaks] <= rt_max]
    if peaks.size == 0:
        raise SystemExit("No TIC peaks found; relax --prominence or --rt-min/--rt-max")
    prominences = dict(zip(peaks, props["prominences"]))
    if peaks.size > n_targets:
        peaks = np.array(
            sorted(peaks, key=lambda p: prominences[p], reverse=True)[:n_targets]
        )
    return np.array(sorted(peaks, key=lambda p: times_min[p]))


def _integrate(
    eic_time: np.ndarray,
    eic_intensity: np.ndarray,
    channel_count: int,
    rt: float,
    search_half_window: float,
    offset: float,
) -> tuple[list[float], float | None]:
    """Locate the quantifier apex, then integrate each channel around it.

    The apex is found on the quantifier channel within rt +/- search_half_window;
    areas are trapezoid integrals over apex +/- offset after subtracting each
    channel's local minimum (a simple local-baseline correction).

    Returns (areas, quantifier apex time or None).
    """
    matrix = eic_intensity.reshape(channel_count, eic_time.size)
    search = (eic_time >= rt - search_half_window) & (eic_time <= rt + search_half_window)
    if search.sum() < 3:
        return [0.0] * channel_count, None
    quant = matrix[0, search].astype(float)
    if quant.max() <= 0:
        return [0.0] * channel_count, None
    apex = float(eic_time[search][int(np.argmax(quant))])

    mask = (eic_time >= apex - offset) & (eic_time <= apex + offset)
    if mask.sum() < 3:
        return [0.0] * channel_count, None
    t = eic_time[mask]
    areas: list[float] = []
    for channel in range(channel_count):
        y = matrix[channel, mask].astype(float)
        y = y - y.min()
        areas.append(float(np.trapezoid(y, t)))
    return areas, apex


def build_list(args: argparse.Namespace) -> list[Target]:
    directory = Path(args.cdf_dir)
    files = sorted(p for p in directory.iterdir() if p.suffix.lower() == ".cdf")
    if not files:
        raise SystemExit(f"No CDF files in {directory}")

    reference = read_cdf_file(str(files[0]))
    ref_times = reference.scan_time / 60.0
    peaks = _pick_tic_peaks(
        ref_times,
        reference.total_intensity,
        args.targets,
        args.min_separation,
        args.prominence,
        args.rt_min,
        args.rt_max,
    )
    excluded = {int(m) for m in args.exclude_mz.split(",")} if args.exclude_mz else set(DEFAULT_EXCLUDED_MZ)

    targets: list[Target] = []
    for peak in peaks:
        masses, intensities = _spectrum_at_scan(reference, int(peak))
        picked = _pick_ions(masses, intensities, excluded, args.min_qualifier_fraction)
        if picked is None:
            print(f"  skip peak at {ref_times[peak]:.2f} min: no usable ion set", file=sys.stderr)
            continue
        quant, quals = picked
        targets.append(
            Target(
                name="",
                rt=float(ref_times[peak]),
                loffset=args.offset,
                roffset=args.offset,
                quant_mz=quant,
                qual_mzs=quals,
            )
        )

    if not targets:
        raise SystemExit("No targets with a quantifier + qualifier ion set were found")

    # Measure every target in every file.
    for target in targets:
        apexes: list[float] = []
        area_rows: list[list[float]] = []
        mzs = [target.quant_mz, *target.qual_mzs]
        for path in files:
            cdf = read_cdf_file(str(path)) if path != files[0] else reference
            try:
                eic = extract_eic(
                    target.name or "target",
                    target.rt,
                    target.quant_mz,
                    cdf,
                    mass_tol=args.mass_tol,
                    rt_window=args.measure_window,
                    target_mzs=mzs,
                )
            except ValueError:
                continue
            areas, apex = _integrate(
                eic.time,
                eic.intensity,
                len(mzs),
                target.rt,
                args.measure_window,
                target.loffset,
            )
            if apex is None or max(areas) <= 0:
                continue
            apexes.append(apex)
            area_rows.append(areas)

        if not apexes:
            print(f"  drop target near {target.rt:.2f} min: undetected everywhere", file=sys.stderr)
            continue

        target.n_detected = len(apexes)
        target.rt = float(np.median(apexes))
        target.rt_spread = float(np.max(np.abs(np.asarray(apexes) - target.rt)))
        if args.max_rt_spread is not None and target.rt_spread > args.max_rt_spread:
            print(
                f"  drop target near {target.rt:.2f} min: RT spread {target.rt_spread:.3f} min "
                f"exceeds --max-rt-spread {args.max_rt_spread}",
                file=sys.stderr,
            )
            continue
        # MANIC integrates a fixed window anchored at the expected tR, so the
        # window must cover the observed inter-file RT drift; otherwise drifted
        # files are mis-integrated and their ratios destabilise. Capped at 0.18
        # so the window stays inside the app's +/-0.2 min EIC import span.
        drift_offset = float(np.clip(target.rt_spread + 0.06, args.offset, 0.18))
        target.loffset = target.roffset = drift_offset

        # The quantifier must be the base peak: promote the channel with the
        # largest median area to quantifier, demoting the original pick to
        # qualifier. Apex-spectrum intensities can mislead when a spike or a
        # co-elutant dominates one scan.
        median_areas = [float(np.median([row[i] for row in area_rows])) for i in range(len(mzs))]
        order = sorted(range(len(mzs)), key=lambda i: median_areas[i], reverse=True)
        mzs = [mzs[i] for i in order]
        area_rows = [[row[i] for i in order] for row in area_rows]
        target.quant_mz = mzs[0]
        target.qual_mzs = mzs[1:]

        ratio_rows = [
            [row[q] / row[0] if row[0] > 0 else float("nan") for q in range(1, len(mzs))]
            for row in area_rows
            if row[0] > 0
        ]
        for q_idx in range(len(target.qual_mzs)):
            col = [row[q_idx] for row in ratio_rows]
            median = float(np.median(col))
            if len(col) >= 4:
                mad = float(np.median(np.abs(np.asarray(col) - median)))
                frac = 1.4826 * mad / median if median > 0 else 0.0
                tol = float(np.clip(3.0 * frac, 0.25, 0.5))
            else:
                tol = 0.3
            target.qual_ratios.append(round(median, 4))
            target.qual_tolerances.append(round(tol, 2))
        target.rt_window = round(min(max(target.rt_spread + 0.03, 0.12), 0.30), 2)
        target.name = f"UNK_{target.rt:.2f}min_mz{int(target.quant_mz)}"

    return [t for t in targets if t.name]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cdf_dir", help="Directory containing .cdf files")
    parser.add_argument("--output", required=True, help="Destination compounds CSV")
    parser.add_argument("--targets", type=int, default=8)
    parser.add_argument("--min-separation", type=float, default=1.0,
                        help="Minimum minutes between target peaks")
    parser.add_argument("--prominence", type=float, default=0.02,
                        help="TIC peak prominence as a fraction of TIC max")
    parser.add_argument("--rt-min", type=float, default=None)
    parser.add_argument("--rt-max", type=float, default=None)
    parser.add_argument("--offset", type=float, default=0.12,
                        help="lOffset/rOffset integration half-window (min, keep <= 0.18)")
    parser.add_argument("--measure-window", type=float, default=0.25,
                        help="Half-window used while measuring apices/areas (min)")
    parser.add_argument("--mass-tol", type=float, default=0.25)
    parser.add_argument("--max-rt-spread", type=float, default=None,
                        help="Drop targets whose inter-file RT drift exceeds this (min). "
                             "MANIC integrates fixed windows anchored at the expected tR, "
                             "so high-drift targets cannot be integrated reliably.")
    parser.add_argument("--min-qualifier-fraction", type=float, default=0.10,
                        help="Qualifier apex intensity must be at least this fraction of quantifier")
    parser.add_argument("--exclude-mz", default=None,
                        help="Comma-separated nominal m/z to exclude (overrides built-in bleed list)")
    args = parser.parse_args()

    if args.offset > 0.18:
        raise SystemExit("--offset must stay <= 0.18 so the window fits the app's ±0.2 min EIC import")

    targets = build_list(args)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "name", "tR", "lOffset", "rOffset", "QIon", "ValIon1", "ValIon2",
            "Qualifier 1 Ratio", "Qualifier 1 Tolerance",
            "Qualifier 2 Ratio", "Qualifier 2 Tolerance", "tR Window",
        ])
        for t in targets:
            q1 = t.qual_mzs[0] if t.qual_mzs else ""
            q2 = t.qual_mzs[1] if len(t.qual_mzs) > 1 else ""
            r1 = t.qual_ratios[0] if t.qual_ratios else ""
            r2 = t.qual_ratios[1] if len(t.qual_ratios) > 1 else ""
            tol1 = t.qual_tolerances[0] if t.qual_tolerances else ""
            tol2 = t.qual_tolerances[1] if len(t.qual_tolerances) > 1 else ""
            writer.writerow([
                t.name, f"{t.rt:.3f}", f"{t.loffset:.2f}", f"{t.roffset:.2f}",
                int(t.quant_mz), int(q1) if q1 != "" else "", int(q2) if q2 != "" else "",
                r1, tol1, r2, tol2, f"{t.rt_window:.2f}",
            ])

    print(f"Wrote {len(targets)} targets to {out}\n")
    print(f"{'name':<22} {'tR':>7} {'Q':>5} {'V1':>5} {'V2':>5} {'r1':>7} {'r2':>7} {'det':>4} {'rtSpread':>9}")
    for t in targets:
        q1 = int(t.qual_mzs[0]) if t.qual_mzs else ""
        q2 = int(t.qual_mzs[1]) if len(t.qual_mzs) > 1 else ""
        r1 = f"{t.qual_ratios[0]:.3f}" if t.qual_ratios else ""
        r2 = f"{t.qual_ratios[1]:.3f}" if len(t.qual_ratios) > 1 else ""
        flag = "  <-- check RT drift" if t.rt_spread > t.rt_window else ""
        print(
            f"{t.name:<22} {t.rt:7.3f} {int(t.quant_mz):>5} {q1!s:>5} {q2!s:>5} "
            f"{r1:>7} {r2:>7} {t.n_detected:>4} {t.rt_spread:8.3f}{flag}"
        )


if __name__ == "__main__":
    main()
