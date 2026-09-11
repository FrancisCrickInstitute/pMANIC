#!/usr/bin/env python3
"""Generate a synthetic unlabelled GC-MS dataset for MANIC smoke testing.

Creates:
  testdata/unlabelled_synthetic/compounds.csv
  testdata/unlabelled_synthetic/*.cdf
  testdata/unlabelled_synthetic/README.md

The chromatograms are intentionally *not* clean: peaks tail (exponentially
modified Gaussians), shot noise scales with signal, silicone column bleed
(m/z 73/147/207/281) drifts upward across the run, every target channel sits
on a wavy chemical baseline, and untargeted background peaks fill out the TIC.

Run from the repository root:
  uv run python scripts/generate_unlabelled_synthetic_data.py
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import assert_never

import numpy as np
import pandas as pd

from synthetic_gcms import (
    BLEED_IONS,
    _baseline_trace,
    _emg_trace,
    _write_cdf,
    assemble_scan_arrays,
    channel_points,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "testdata" / "unlabelled_synthetic"

START_S = 60.0
END_S = 1500.0
DT_S = 0.5
RT_DRIFT_PER_INJECTION = 0.003
WRITE_LEFT_MIN = 1.0
WRITE_RIGHT_MIN = 2.5
N_BACKGROUND_PEAKS = 80
BACKGROUND_RT_CLEARANCE_MIN = 0.5

KO_PROFILE = {
    "Citrate": 2.2,
    "Glutamate": 1.8,
    "Glucose": 0.45,
    "Lactate": 1.6,
    "Succinate": 1.4,
    "Alanine": 0.7,
}


class SampleKind(Enum):
    MM = "mm"
    QC = "qc"
    BIO = "bio"
    DEFECT = "defect"


@dataclass
class CompoundSpec:
    name: str
    rt: float
    loffset: float
    roffset: float
    quant: float
    q1: float
    q1_ratio: float | None
    amount: float | None
    sigma: float
    tau: float
    tr_window: float | None = None
    q2: float | None = None
    q2_ratio: float | None = None
    istd_amt: float | None = None
    overlap_dt: float | None = None
    overlap_frac: float | None = None


@dataclass
class SampleSpec:
    name: str
    note: str
    kind: SampleKind
    order: int
    rt_shift: float = 0.0
    quant_scale: float = 1.0
    is_scale: float = 1.0
    omit: frozenset[str] = field(default_factory=frozenset)
    v_scale: dict[str, dict[int, float]] = field(default_factory=dict)
    overlap_frac: float | None = None
    profile: dict[str, float] = field(default_factory=dict)


COMPOUNDS = [
    CompoundSpec("Pyruvate", 4.50, 0.12, 0.12, 174.0, 99.0, 0.40, 4.5, 0.028, 0.018),
    CompoundSpec(
        "Alanine",
        5.00,
        0.12,
        0.12,
        116.0,
        147.0,
        0.45,
        5.0,
        0.030,
        0.020,
        tr_window=0.08,
        q2=73.0,
        q2_ratio=0.25,
        overlap_dt=0.12,
        overlap_frac=0.90,
    ),
    CompoundSpec(
        "Valine",
        5.45,
        0.12,
        0.12,
        144.0,
        218.0,
        0.35,
        4.0,
        0.030,
        0.020,
        overlap_dt=0.12,
        overlap_frac=0.90,
    ),
    CompoundSpec("Leucine", 5.85, 0.12, 0.12, 158.0, 102.0, 0.45, 4.2, 0.031, 0.021),
    CompoundSpec("Isoleucine", 5.97, 0.12, 0.12, 158.0, 218.0, 0.40, 3.8, 0.031, 0.021),
    CompoundSpec(
        "Lactate",
        6.50,
        0.12,
        0.12,
        117.0,
        147.0,
        0.35,
        8.0,
        0.038,
        0.030,
        overlap_dt=0.12,
        overlap_frac=0.90,
    ),
    CompoundSpec(
        "Proline",
        6.90,
        0.12,
        0.12,
        142.0,
        216.0,
        0.30,
        3.6,
        0.032,
        0.022,
        overlap_dt=0.12,
        overlap_frac=0.90,
    ),
    CompoundSpec("Glycine", 7.20, 0.12, 0.12, 174.0, 248.0, None, 4.0, 0.032, 0.022),
    CompoundSpec(
        "Succinate",
        7.55,
        0.12,
        0.12,
        247.0,
        147.0,
        0.55,
        3.8,
        0.036,
        0.028,
        overlap_dt=0.12,
        overlap_frac=0.90,
    ),
    CompoundSpec("Fumarate", 7.85, 0.12, 0.12, 245.0, 147.0, 0.50, 3.2, 0.035, 0.026),
    CompoundSpec(
        "Serine",
        8.10,
        0.12,
        0.12,
        204.0,
        218.0,
        0.40,
        3.5,
        0.034,
        0.024,
        q2=100.0,
        overlap_dt=0.12,
        overlap_frac=0.90,
    ),
    CompoundSpec("Threonine", 8.45, 0.12, 0.12, 117.0, 218.0, 0.35, 3.4, 0.034, 0.024),
    CompoundSpec("Malate", 8.85, 0.12, 0.12, 233.0, 245.0, 0.40, 3.6, 0.038, 0.030),
    CompoundSpec(
        "Methionine",
        9.15,
        0.12,
        0.12,
        176.0,
        128.0,
        0.38,
        2.8,
        0.033,
        0.023,
        overlap_dt=0.12,
        overlap_frac=0.90,
    ),
    CompoundSpec(
        "Phenylethanol",
        9.40,
        0.10,
        0.20,
        106.0,
        91.0,
        0.55,
        2.0,
        0.028,
        0.018,
        q2=77.0,
        q2_ratio=0.22,
        overlap_dt=0.12,
        overlap_frac=0.90,
    ),
    CompoundSpec("Aspartate", 9.85, 0.12, 0.12, 232.0, 218.0, 0.42, 3.5, 0.036, 0.026),
    CompoundSpec(
        "Glutamate",
        10.35,
        0.12,
        0.12,
        246.0,
        156.0,
        0.36,
        4.8,
        0.038,
        0.028,
        overlap_dt=0.12,
        overlap_frac=0.90,
    ),
    CompoundSpec(
        "Phenylalanine",
        10.85,
        0.12,
        0.12,
        192.0,
        218.0,
        0.40,
        3.2,
        0.034,
        0.024,
        overlap_dt=0.12,
        overlap_frac=0.90,
    ),
    CompoundSpec("Asparagine", 11.35, 0.12, 0.12, 188.0, 116.0, 0.45, 2.6, 0.036, 0.026),
    CompoundSpec(
        "Citrate",
        12.00,
        0.15,
        0.15,
        273.0,
        147.0,
        0.42,
        3.0,
        0.045,
        0.040,
        q2=73.0,
        q2_ratio=0.20,
        overlap_dt=0.12,
        overlap_frac=0.90,
    ),
    CompoundSpec("Uncalibrated", 13.20, 0.12, 0.12, 156.0, 99.0, 0.33, None, 0.033, 0.021),
    CompoundSpec(
        "Glucose",
        13.70,
        0.12,
        0.12,
        319.0,
        205.0,
        0.50,
        10.0,
        0.042,
        0.055,
        overlap_dt=0.12,
        overlap_frac=0.90,
    ),
    CompoundSpec("Tyrosine", 14.10, 0.12, 0.12, 218.0, 280.0, 0.35, 2.8, 0.036, 0.026),
    CompoundSpec(
        "scyllo-Inositol",
        14.50,
        0.12,
        0.12,
        318.0,
        217.0,
        0.30,
        1.0,
        0.035,
        0.025,
        istd_amt=10.0,
    ),
    CompoundSpec(
        "myo-Inositol", 15.20, 0.12, 0.12, 305.0, 217.0, 0.45, 2.2, 0.038, 0.028
    ),
    CompoundSpec("Tryptophan", 16.10, 0.12, 0.12, 202.0, 291.0, 0.28, 1.5, 0.040, 0.030),
    CompoundSpec("Palmitate", 18.40, 0.12, 0.12, 313.0, 117.0, 0.60, 3.0, 0.044, 0.034),
    CompoundSpec("Stearate", 20.80, 0.12, 0.12, 341.0, 117.0, 0.55, 2.4, 0.046, 0.036),
    CompoundSpec(
        "Cholesterol", 23.60, 0.15, 0.15, 368.0, 329.0, 0.80, 2.0, 0.050, 0.045
    ),
]


SAMPLES = [
    SampleSpec("MM_01", "standard mixture replicate 1", SampleKind.MM, 1),
    SampleSpec(
        "MM_02",
        "standard mixture replicate 2",
        SampleKind.MM,
        2,
        rt_shift=0.01,
        quant_scale=1.05,
    ),
    SampleSpec(
        "MM_03",
        "standard mixture replicate 3",
        SampleKind.MM,
        3,
        rt_shift=-0.008,
        quant_scale=0.97,
    ),
    SampleSpec("QC_pool_01", "pooled QC early in the sequence", SampleKind.QC, 4),
    SampleSpec("WT_01", "wild-type biological sample", SampleKind.BIO, 5, overlap_frac=1.00),
    SampleSpec(
        "WT_02",
        "wild-type, slightly stronger Q neighbours",
        SampleKind.BIO,
        6,
        quant_scale=0.92,
        overlap_frac=1.05,
    ),
    SampleSpec(
        "WT_03",
        "wild-type biological sample",
        SampleKind.BIO,
        7,
        quant_scale=1.08,
        overlap_frac=1.00,
    ),
    SampleSpec(
        "WT_04",
        "wild-type, stronger Q neighbours",
        SampleKind.BIO,
        8,
        quant_scale=0.86,
        overlap_frac=1.15,
    ),
    SampleSpec(
        "WT_05",
        "wild-type biological sample",
        SampleKind.BIO,
        9,
        quant_scale=1.14,
        overlap_frac=1.00,
    ),
    SampleSpec(
        "WT_06",
        "wild-type, strongest Q neighbours",
        SampleKind.BIO,
        10,
        quant_scale=0.97,
        overlap_frac=1.25,
    ),
    SampleSpec(
        "KO_01",
        "knockout abundance shift",
        SampleKind.BIO,
        11,
        profile=dict(KO_PROFILE),
        overlap_frac=1.00,
    ),
    SampleSpec(
        "KO_02",
        "knockout, slightly stronger Q neighbours",
        SampleKind.BIO,
        12,
        profile=dict(KO_PROFILE),
        overlap_frac=1.08,
    ),
    SampleSpec(
        "KO_03",
        "knockout abundance shift",
        SampleKind.BIO,
        13,
        profile=dict(KO_PROFILE),
        overlap_frac=1.00,
    ),
    SampleSpec(
        "KO_04",
        "knockout, stronger Q neighbours",
        SampleKind.BIO,
        14,
        profile=dict(KO_PROFILE),
        overlap_frac=1.15,
    ),
    SampleSpec(
        "KO_05",
        "knockout abundance shift",
        SampleKind.BIO,
        15,
        profile=dict(KO_PROFILE),
        overlap_frac=1.00,
    ),
    SampleSpec(
        "KO_06",
        "knockout, strongest Q neighbours",
        SampleKind.BIO,
        16,
        profile=dict(KO_PROFILE),
        overlap_frac=1.22,
    ),
    SampleSpec("QC_pool_02", "pooled QC late in the sequence", SampleKind.QC, 17),
    SampleSpec(
        "Sample_04_ratio_fail",
        "Alanine both qualifier to Q checks fail",
        SampleKind.DEFECT,
        18,
        v_scale={"Alanine": {1: 1.80, 2: 1.80}},
    ),
    SampleSpec(
        "Sample_05_rt_shift",
        "tR miss on Alanine. Qualifier to Q still good",
        SampleKind.DEFECT,
        19,
        rt_shift=0.16,
    ),
    SampleSpec(
        "Sample_06_partial",
        "Citrate qualifier 2 fail, qualifier 1 pass",
        SampleKind.DEFECT,
        20,
        v_scale={"Citrate": {2: 2.40}},
    ),
    SampleSpec(
        "Sample_07_missing",
        "Alanine absent",
        SampleKind.DEFECT,
        21,
        omit=frozenset({"Alanine"}),
    ),
    SampleSpec(
        "Sample_08_low_is",
        "IS almost gone. Tile validation fails if IS is set",
        SampleKind.DEFECT,
        22,
        is_scale=0.03,
    ),
    SampleSpec(
        "Sample_09_overlap",
        "Stronger Phenylethanol neighbour",
        SampleKind.DEFECT,
        23,
        overlap_frac=1.10,
    ),
]


def _sample_seed(name: str) -> int:
    return int(hashlib.md5(name.encode()).hexdigest()[:8], 16)


def _nominal(mz: float) -> int:
    return int(np.floor(mz + 0.5))


def _target_mzs() -> set[float]:
    masses: set[float] = set()
    for compound in COMPOUNDS:
        masses.add(compound.quant)
        masses.add(compound.q1)
        if compound.q2 is not None:
            masses.add(compound.q2)
    return masses


def _targets_for(sample: SampleSpec) -> tuple[list[CompoundSpec], float]:
    match sample.kind:
        case SampleKind.MM | SampleKind.QC | SampleKind.BIO | SampleKind.DEFECT:
            return [c for c in COMPOUNDS if c.name not in sample.omit], 1.0
        case _:
            assert_never(sample.kind)


def _slice_bounds(time_min: np.ndarray, lo: float, hi: float) -> tuple[int, int]:
    start = int(np.searchsorted(time_min, lo, side="left"))
    stop = int(np.searchsorted(time_min, hi, side="right"))
    start = max(0, start)
    stop = min(time_min.size, stop)
    if stop <= start:
        return 0, 0
    return start, stop


def _background_hits_target(
    mz: float, rt: float, target_mzs: set[float], target_rts: list[float]
) -> bool:
    nominal = _nominal(mz)
    return any(
        _nominal(target_mz) == nominal
        and abs(rt - comp_rt) < BACKGROUND_RT_CLEARANCE_MIN
        for target_mz in target_mzs
        for comp_rt in target_rts
    )


def _background_peaks(
    rng: np.random.Generator,
) -> list[tuple[float, float, float, float, float]]:
    target_mzs = _target_mzs()
    target_rts = [compound.rt for compound in COMPOUNDS]
    peaks: list[tuple[float, float, float, float, float]] = []
    attempts = 0
    while len(peaks) < N_BACKGROUND_PEAKS and attempts < 2000:
        attempts += 1
        mz = float(rng.uniform(60.0, 400.0))
        rt = float(rng.uniform(1.5, 24.5))
        if _background_hits_target(mz, rt, target_mzs, target_rts):
            continue
        amp = float(np.exp(rng.uniform(np.log(300.0), np.log(9000.0))))
        sigma = float(rng.uniform(0.02, 0.06))
        tau = float(rng.uniform(0.0, 0.05))
        peaks.append((mz, rt, amp, sigma, tau))
    return peaks


def build_sample_cdf(sample: SampleSpec) -> tuple[np.ndarray, ...]:
    scan_time_s = np.arange(START_S, END_S + DT_S / 2, DT_S, dtype=np.float64)
    time_min = scan_time_s / 60.0
    duration = float(time_min[-1] - time_min[0])
    n_scans = time_min.size

    scan_chunks: list[np.ndarray] = []
    mass_chunks: list[np.ndarray] = []
    inten_chunks: list[np.ndarray] = []

    def _push(
        scan_ids: np.ndarray, masses: np.ndarray, intensities: np.ndarray
    ) -> None:
        if scan_ids.size == 0:
            return
        scan_chunks.append(scan_ids)
        mass_chunks.append(masses)
        inten_chunks.append(intensities)

    rng = np.random.default_rng(_sample_seed(sample.name))
    selected, amount_scale = _targets_for(sample)

    for compound in selected:
        center = (
            float(compound.rt)
            + sample.order * RT_DRIFT_PER_INJECTION
            + sample.rt_shift
            + float(rng.normal(0.0, 0.004))
        )
        amount = float(compound.amount or 2.0) * amount_scale
        compound_scale = (
            sample.quant_scale
            * sample.profile.get(compound.name, 1.0)
            * float(np.clip(rng.normal(1.0, 0.05), 0.5, 1.6))
        )
        if compound.istd_amt is not None:
            compound_scale *= sample.is_scale
        base_amp = 2.0e4 * amount * compound_scale
        v_scales = sample.v_scale.get(compound.name, {})

        channel_specs: list[tuple[float, float, int]] = [
            (float(compound.quant), 1.0, 0),
        ]
        relative = float(compound.q1_ratio or 0.35) * v_scales.get(1, 1.0)
        channel_specs.append((float(compound.q1), relative, 1))
        if compound.q2 is not None:
            relative = float(compound.q2_ratio or 0.20) * v_scales.get(2, 1.0)
            channel_specs.append((float(compound.q2), relative, 2))

        write_lo = min(compound.rt, center) - WRITE_LEFT_MIN
        write_hi = max(compound.rt, center) + WRITE_RIGHT_MIN
        neighbor_frac = 0.0
        if compound.overlap_dt:
            neighbor_frac = (
                sample.overlap_frac
                if sample.overlap_frac is not None
                else float(compound.overlap_frac or 0.0)
            )
            write_hi = max(write_hi, center + float(compound.overlap_dt) + 0.6)
        start, stop = _slice_bounds(time_min, write_lo, write_hi)
        if stop <= start:
            continue
        window = time_min[start:stop]

        for mz, relative, ordinal in channel_specs:
            peak = _emg_trace(
                window,
                center,
                base_amp * relative,
                float(compound.sigma),
                float(compound.tau),
            )
            if ordinal == 0 and neighbor_frac:
                peak = peak + _emg_trace(
                    window,
                    center + float(compound.overlap_dt),
                    base_amp * neighbor_frac,
                    float(compound.sigma),
                    float(compound.tau),
                )
            baseline = _baseline_trace(
                window, rng, level=float(rng.uniform(35.0, 90.0))
            )
            _push(
                *channel_points(
                    peak + baseline,
                    mz,
                    rng,
                    scan_offset=start,
                    active_fraction=1e-4,
                )
            )

    for bleed_mz, bleed_amp in BLEED_IONS.items():
        ramp = bleed_amp * (0.55 + 0.9 * (time_min - time_min[0]) / duration)
        wobble = 1.0 + 0.06 * np.sin(
            2.0 * np.pi * time_min / rng.uniform(5.0, 11.0)
            + rng.uniform(0.0, 2.0 * np.pi)
        )
        _push(
            *channel_points(
                ramp * wobble,
                bleed_mz,
                rng,
                active_fraction=0.0,
            )
        )

    for bg_mz, bg_rt, bg_amp, bg_sigma, bg_tau in _background_peaks(rng):
        start, stop = _slice_bounds(time_min, bg_rt - 0.8, bg_rt + 1.6)
        if stop <= start:
            continue
        window = time_min[start:stop]
        trace = _emg_trace(window, bg_rt, bg_amp, bg_sigma, max(bg_tau, 0.005))
        _push(*channel_points(trace, bg_mz, rng, scan_offset=start))

    if scan_chunks:
        mass, intensity, scan_index, point_count, total_intensity = assemble_scan_arrays(
            n_scans,
            np.concatenate(scan_chunks),
            np.concatenate(mass_chunks),
            np.concatenate(inten_chunks),
        )
    else:
        mass, intensity, scan_index, point_count, total_intensity = assemble_scan_arrays(
            n_scans,
            np.zeros(0, dtype=np.int32),
            np.zeros(0, dtype=np.float64),
            np.zeros(0, dtype=np.float64),
        )
    return (
        scan_time_s,
        mass,
        intensity,
        scan_index,
        point_count,
        total_intensity,
    )


def write_compound_list(path: Path) -> None:
    rows = []
    for compound in COMPOUNDS:
        rows.append(
            {
                "name": compound.name,
                "tR": compound.rt,
                "lOffset": compound.loffset,
                "rOffset": compound.roffset,
                "tR Window": compound.tr_window
                if compound.tr_window is not None
                else max(compound.loffset, compound.roffset),
                "QIon": compound.quant,
                "QualifierIon1": compound.q1,
                "QualifierIon2": compound.q2 if compound.q2 is not None else "",
                "Qualifier 1 Ratio": (
                    compound.q1_ratio if compound.q1_ratio is not None else ""
                ),
                "Qualifier 1 Tolerance": 0.25 if compound.q1_ratio is not None else "",
                "Qualifier 2 Ratio": (
                    compound.q2_ratio if compound.q2_ratio is not None else ""
                ),
                "Qualifier 2 Tolerance": 0.25 if compound.q2_ratio is not None else "",
                "Amount in StdMix": (
                    compound.amount if compound.amount is not None else ""
                ),
                "Int Std amount": (
                    compound.istd_amt if compound.istd_amt is not None else ""
                ),
                "MM Files": "MM_*",
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def _compound_note(compound: CompoundSpec) -> str:
    bits: list[str] = []
    if compound.tr_window is not None:
        bits.append(f"tR window {compound.tr_window}")
    if compound.q1_ratio is None:
        bits.append("no expected ratio")
    if compound.q2 is not None and compound.q2_ratio is None:
        bits.append("qualifier 2 has no ratio")
    if compound.overlap_dt is not None:
        bits.append("neighbour on Q")
    if compound.amount is None:
        bits.append("no Amount in StdMix")
    if compound.istd_amt is not None:
        bits.append(f"internal standard {compound.istd_amt}")
    ko = KO_PROFILE.get(compound.name)
    if ko is not None:
        bits.append(f"KO ×{ko}")
    shared = [
        other.name
        for other in COMPOUNDS
        if other.name != compound.name and _nominal(other.quant) == _nominal(compound.quant)
    ]
    if shared:
        bits.append(f"shares Q {compound.quant:.0f} with {shared[0]}")
    return "; ".join(bits)


def write_readme(path: Path) -> None:
    compound_lines = [
        "| Compound | tR (min) | Ions | Notes |",
        "|---|---|---|---|",
    ]
    for compound in COMPOUNDS:
        ions = f"Q {compound.quant:.0f}, qualifier 1 {compound.q1:.0f}"
        if compound.q2 is not None:
            ions += f", qualifier 2 {compound.q2:.0f}"
        compound_lines.append(
            f"| {compound.name} | {compound.rt:.2f} | {ions} | {_compound_note(compound)} |"
        )

    sample_lines = [
        "| Order | Sample | Kind | Purpose |",
        "|---|---|---|---|",
    ]
    for sample in SAMPLES:
        sample_lines.append(
            f"| {sample.order} | `{sample.name}` | {sample.kind.value} | {sample.note} |"
        )

    path.write_text(
        f"""# Synthetic unlabelled dataset

Generated by `scripts/generate_unlabelled_synthetic_data.py`. The
chromatograms mimic a real run: tailing peaks (exponentially modified
Gaussians), signal-dependent shot noise, upward-drifting silicone column
bleed (m/z 73/147/207/281), wavy chemical baselines on every target channel,
and untargeted background peaks in the TIC.

## How to load in MANIC

1. Start MANIC and choose **Unlabelled targeted analysis**.
2. **File → Load Compounds/Parameter List** → select `compounds.csv`.
3. **File → Load Raw Data (CDF)** → select this folder.
4. Set **scyllo-Inositol** as the internal standard if you want relative or
   semi-quantitative amounts.
5. Inspect EICs, then **File → Export Data...**.

## Compounds

The method list is a polar TMS panel. The original eight QC-story compounds
keep their ions, ratios, windows, and the Phenylethanol overlap. The added
metabolites use common TMS fragments.

{chr(10).join(compound_lines)}

## Samples

Injection order is the sequence number. Retention time also drifts by
`order * 0.003` min.

WT and KO biological samples differ in abundance. KO raises Citrate,
Glutamate, Lactate, and Succinate, and lowers Glucose and Alanine.

Most targets have a close neighbour on the Q ion so deconvolution has
something to split. Qualifier channels stay on. Leucine and Isoleucine
share Q 158 and sit 0.12 min apart. `Sample_0*` files are the small
designed QC set. The other vials only vary abundance and neighbour height.

{chr(10).join(sample_lines)}

Reference ion ratios in `compounds.csv` use fractional tolerances (±25%).

## Notes

- CDF files are synthetic ANDI-style NetCDF with the variables MANIC reads.
- These are simulated signals, not real GC-MS spectra.
- Rebuild anytime with:

```bash
uv run python scripts/generate_unlabelled_synthetic_data.py
```
""",
        encoding="utf-8",
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.cdf"):
        old.unlink()

    write_compound_list(OUT_DIR / "compounds.csv")
    write_readme(OUT_DIR / "README.md")

    for sample in SAMPLES:
        (
            scan_time_s,
            mass,
            intensity,
            scan_index,
            point_count,
            total_intensity,
        ) = build_sample_cdf(sample)
        _write_cdf(
            OUT_DIR / f"{sample.name}.cdf",
            scan_time_s=scan_time_s,
            mass=mass,
            intensity=intensity,
            scan_index=scan_index,
            point_count=point_count,
            total_intensity=total_intensity,
        )

    print(f"Wrote synthetic unlabelled dataset to {OUT_DIR}")
    print(f"  compounds: {OUT_DIR / 'compounds.csv'}")
    print(f"  CDF files: {len(list(OUT_DIR.glob('*.cdf')))}")


if __name__ == "__main__":
    main()
