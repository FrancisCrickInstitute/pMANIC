#!/usr/bin/env python3
"""Generate large synthetic GC-MS benchmark datasets for MANIC.

Creates, under ``--out`` (default ``testdata/bench``):

  labelled/     compounds.csv  manifest.json  <sample>.cdf x N
  unlabelled/   compounds.csv  manifest.json  <sample>.cdf x N

The labelled compound table is ``example_compounds_list.xls``. Unlabelled
targets are generated. Chromatogram physics matches the small unlabelled
generator (EMG peaks, silicone bleed, chemical baseline, untargeted
background). Same ``--seed`` and arguments write byte-identical CDFs and
manifests.

Run from the repository root:

  uv run python scripts/generate_bench_data.py --mode both
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path

import numpy as np
import pandas as pd

import synthetic_gcms
from synthetic_gcms import (
    BLEED_IONS,
    _baseline_trace,
    _emg_trace,
    _write_cdf,
    assemble_scan_arrays,
    channel_points,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "testdata" / "bench"
LABELLED_XLS = ROOT / "example_compounds_list.xls"

START_S = 60.0
END_S = 1500.0
N_BACKGROUND_PEAKS = 36
BASE_HEIGHT = 1.5e5
SATURATION_CLIP = 2.5e6
LABEL_PURITY = 0.99
TRUTH_GRID = 480
WRITE_LEFT_MIN = 1.0
WRITE_RIGHT_MIN = 2.5

_FORMULA_TOKEN = re.compile(r"^([A-Z][a-z]?)(\d+)$")
_TRAPZ = getattr(np, "trapezoid", np.trapz)
_GENERATOR_INPUTS = (Path(__file__), Path(synthetic_gcms.__file__), LABELLED_XLS)

# Natural-abundance extra-neutron probabilities used for MID convolution.
_ISOTOPE: dict[str, tuple[tuple[int, float], ...]] = {
    "C": ((0, 1.0 - 0.0107), (1, 0.0107)),
    "H": ((0, 1.0 - 0.000115), (1, 0.000115)),
    "N": ((0, 1.0 - 0.00364), (1, 0.00364)),
    "O": ((0, 1.0 - 0.00038 - 0.00205), (1, 0.00038), (2, 0.00205)),
    "Si": ((0, 1.0 - 0.0468 - 0.0309), (1, 0.0468), (2, 0.0309)),
    "S": ((0, 1.0 - 0.0076 - 0.0429), (1, 0.0076), (2, 0.0429)),
    "P": ((0, 1.0),),
}

_NAMED_UNLABELLED = (
    "Alanine",
    "Lactate",
    "Glycine",
    "Serine",
    "Citrate",
    "Glucose",
    "Glutamate",
    "Phenylalanine",
    "Valine",
    "scyllo-Inositol",
)

_LABELLED_NEAR_PAIRS = (
    ("Cysteine 218", "Cysteine"),
    ("Deoxyribose", "aKG"),
    ("Mannose", "Galactose"),
    ("Glucose", "Sorbitol-Mannitol"),
)


class Scope(Enum):
    SAMPLE = "sample"
    COMPOUND = "compound"
    CELL = "cell"


class Scenario(Enum):
    CLEAN = "CLEAN"
    NOISY = "NOISY"
    DRIFTING_BASELINE = "DRIFTING_BASELINE"
    RT_SHIFT = "RT_SHIFT"
    LOW_IS = "LOW_IS"
    SATURATED_DETECTOR = "SATURATED_DETECTOR"
    OVERLAP_NEIGHBOUR = "OVERLAP_NEIGHBOUR"
    SHOULDER = "SHOULDER"
    BROAD_TAILING = "BROAD_TAILING"
    TRACE_LEVEL = "TRACE_LEVEL"
    NEAR_COELUTION = "NEAR_COELUTION"
    MISSING = "MISSING"
    HEAVY_LABEL = "HEAVY_LABEL"
    UNLABELLED_CONTROL = "UNLABELLED_CONTROL"
    RATIO_FAIL = "RATIO_FAIL"

    @property
    def scope(self) -> Scope:
        return _SCENARIO_SCOPE[self]


class SampleKind(Enum):
    BIOLOGICAL = "BIOLOGICAL"
    STANDARD_MIX = "STANDARD_MIX"


_SCENARIO_SCOPE = {
    Scenario.CLEAN: Scope.SAMPLE,
    Scenario.NOISY: Scope.SAMPLE,
    Scenario.DRIFTING_BASELINE: Scope.SAMPLE,
    Scenario.RT_SHIFT: Scope.SAMPLE,
    Scenario.LOW_IS: Scope.SAMPLE,
    Scenario.SATURATED_DETECTOR: Scope.SAMPLE,
    Scenario.OVERLAP_NEIGHBOUR: Scope.COMPOUND,
    Scenario.SHOULDER: Scope.COMPOUND,
    Scenario.BROAD_TAILING: Scope.COMPOUND,
    Scenario.TRACE_LEVEL: Scope.COMPOUND,
    Scenario.NEAR_COELUTION: Scope.COMPOUND,
    Scenario.MISSING: Scope.CELL,
    Scenario.HEAVY_LABEL: Scope.CELL,
    Scenario.UNLABELLED_CONTROL: Scope.CELL,
    Scenario.RATIO_FAIL: Scope.CELL,
}

_SAMPLE_SCENARIOS = (
    Scenario.NOISY,
    Scenario.DRIFTING_BASELINE,
    Scenario.RT_SHIFT,
    Scenario.LOW_IS,
    Scenario.SATURATED_DETECTOR,
)
_COMPOUND_SCENARIOS = (
    Scenario.OVERLAP_NEIGHBOUR,
    Scenario.SHOULDER,
    Scenario.BROAD_TAILING,
    Scenario.TRACE_LEVEL,
    Scenario.NEAR_COELUTION,
)


@dataclass(frozen=True)
class ScenarioDelta:
    shot_noise_mul: float = 1.0
    baseline_noise_mul: float = 1.0
    baseline_level_mul: float = 1.0
    drift_mul: float = 1.0
    rt_shift_min: float = 0.0
    rt_shift_max: float = 0.0
    is_height_mul: float = 1.0
    clip: float | None = None
    overlap: bool = False
    overlap_dt_min: float = 0.0
    overlap_dt_max: float = 0.0
    overlap_height_min: float = 0.0
    overlap_height_max: float = 0.0
    shoulder: bool = False
    shoulder_dt: float = 0.0
    shoulder_height_mul: float = 0.0
    sigma_mul: float = 1.0
    tau_mul: float = 1.0
    height_mul: float = 1.0
    present: bool = True
    enrichment_min: float | None = None
    enrichment_max: float | None = None
    enrichment_fixed: float | None = None
    ratio_mul: float = 1.0


SCENARIO_EFFECTS: dict[Scenario, ScenarioDelta] = {
    Scenario.CLEAN: ScenarioDelta(),
    Scenario.NOISY: ScenarioDelta(shot_noise_mul=3.0, baseline_noise_mul=2.0),
    Scenario.DRIFTING_BASELINE: ScenarioDelta(baseline_level_mul=4.0, drift_mul=4.0),
    Scenario.RT_SHIFT: ScenarioDelta(rt_shift_min=0.05, rt_shift_max=0.12),
    Scenario.LOW_IS: ScenarioDelta(is_height_mul=0.02),
    Scenario.SATURATED_DETECTOR: ScenarioDelta(clip=SATURATION_CLIP),
    Scenario.OVERLAP_NEIGHBOUR: ScenarioDelta(
        overlap=True,
        overlap_dt_min=0.08,
        overlap_dt_max=0.14,
        overlap_height_min=0.6,
        overlap_height_max=1.2,
    ),
    Scenario.SHOULDER: ScenarioDelta(shoulder=True, shoulder_dt=0.04, shoulder_height_mul=0.35),
    Scenario.BROAD_TAILING: ScenarioDelta(sigma_mul=2.2, tau_mul=3.0),
    Scenario.TRACE_LEVEL: ScenarioDelta(height_mul=0.004),
    Scenario.NEAR_COELUTION: ScenarioDelta(),
    Scenario.MISSING: ScenarioDelta(present=False),
    Scenario.HEAVY_LABEL: ScenarioDelta(enrichment_min=0.85, enrichment_max=0.98),
    Scenario.UNLABELLED_CONTROL: ScenarioDelta(enrichment_fixed=0.0),
    Scenario.RATIO_FAIL: ScenarioDelta(ratio_mul=2.0),
}


@dataclass(frozen=True)
class PeakShape:
    sigma_min: float
    tau_min: float


@dataclass(frozen=True)
class Target:
    name: str
    rt: float
    loffset: float
    roffset: float
    channels: tuple[float, ...]
    channel_fractions: tuple[float, ...] | None
    shape: PeakShape
    base_height: float
    amount: float | None
    is_internal_standard: bool
    label_atoms: int
    formula: str | None


@dataclass(frozen=True)
class SampleSpec:
    name: str
    kind: SampleKind
    scale: float
    enrichment: float
    scenarios: frozenset[Scenario]


@dataclass(frozen=True)
class PeakTruth:
    sample: str
    compound: str
    scenarios: tuple[str, ...]
    rt_actual: float
    present: bool
    channel_mz: tuple
    channel_fractions: tuple
    channel_heights: tuple
    true_total_area: float
    true_channel_areas: tuple


def _compose(deltas: list[ScenarioDelta]) -> ScenarioDelta:
    out = ScenarioDelta()
    for delta in deltas:
        out = ScenarioDelta(
            shot_noise_mul=out.shot_noise_mul * delta.shot_noise_mul,
            baseline_noise_mul=out.baseline_noise_mul * delta.baseline_noise_mul,
            baseline_level_mul=out.baseline_level_mul * delta.baseline_level_mul,
            drift_mul=out.drift_mul * delta.drift_mul,
            rt_shift_min=max(out.rt_shift_min, delta.rt_shift_min),
            rt_shift_max=max(out.rt_shift_max, delta.rt_shift_max),
            is_height_mul=out.is_height_mul * delta.is_height_mul,
            clip=delta.clip if delta.clip is not None else out.clip,
            overlap=out.overlap or delta.overlap,
            overlap_dt_min=max(out.overlap_dt_min, delta.overlap_dt_min),
            overlap_dt_max=max(out.overlap_dt_max, delta.overlap_dt_max),
            overlap_height_min=max(out.overlap_height_min, delta.overlap_height_min),
            overlap_height_max=max(out.overlap_height_max, delta.overlap_height_max),
            shoulder=out.shoulder or delta.shoulder,
            shoulder_dt=delta.shoulder_dt or out.shoulder_dt,
            shoulder_height_mul=delta.shoulder_height_mul or out.shoulder_height_mul,
            sigma_mul=out.sigma_mul * delta.sigma_mul,
            tau_mul=out.tau_mul * delta.tau_mul,
            height_mul=out.height_mul * delta.height_mul,
            present=out.present and delta.present,
            enrichment_min=(
                delta.enrichment_min
                if delta.enrichment_min is not None
                else out.enrichment_min
            ),
            enrichment_max=(
                delta.enrichment_max
                if delta.enrichment_max is not None
                else out.enrichment_max
            ),
            enrichment_fixed=(
                delta.enrichment_fixed
                if delta.enrichment_fixed is not None
                else out.enrichment_fixed
            ),
            ratio_mul=out.ratio_mul * delta.ratio_mul,
        )
    return out


def _effects_for(scenarios: frozenset[Scenario]) -> ScenarioDelta:
    return _compose([SCENARIO_EFFECTS[s] for s in sorted(scenarios, key=lambda s: s.name)])


def _peak_shape(loffset: float, roffset: float) -> PeakShape:
    return PeakShape(
        sigma_min=max(0.012, min(loffset, roffset) * 0.45),
        tau_min=max(0.008, roffset * 0.40),
    )


def _parse_formula(formula: str | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not formula:
        return counts
    for token in formula.replace(",", " ").split():
        match = _FORMULA_TOKEN.match(token)
        if match is None:
            continue
        counts[match.group(1)] = int(match.group(2))
    return counts


def _poly_pow(base: list[float], n: int) -> list[float]:
    out = [1.0]
    for _ in range(n):
        out = np.convolve(out, base).tolist()
    return out


def _natural_abundance(counts: dict[str, int], max_mass: int) -> np.ndarray:
    dist = [1.0]
    for element, n_atoms in counts.items():
        if n_atoms <= 0:
            continue
        table = _ISOTOPE.get(element)
        if table is None:
            continue
        width = max(shift for shift, _p in table) + 1
        base = [0.0] * width
        for shift, prob in table:
            base[shift] = prob
        dist = np.convolve(dist, _poly_pow(base, n_atoms)).tolist()
    arr = np.asarray(dist, dtype=np.float64)
    if arr.size < max_mass + 1:
        arr = np.pad(arr, (0, max_mass + 1 - arr.size))
    return arr[: max_mass + 1]


def _binomial_pmf(n: int, p: float) -> np.ndarray:
    if n <= 0:
        return np.ones(1, dtype=np.float64)
    p = float(np.clip(p, 0.0, 1.0))
    k = np.arange(n + 1, dtype=np.float64)
    logc = (
        math.lgamma(n + 1)
        - np.array([math.lgamma(i + 1) + math.lgamma(n - i + 1) for i in range(n + 1)])
    )
    return np.exp(logc + k * math.log(p + 1e-300) + (n - k) * math.log1p(-p))


def labelled_channel_fractions(
    formula: str | None, label_atoms: int, enrichment: float
) -> tuple[float, ...]:
    n_label = max(0, int(label_atoms))
    counts = _parse_formula(formula)
    leftover = dict(counts)
    # Labelable carbons belong in the tracer term rather than the remaining
    # natural-abundance term. At zero experimental enrichment they still have
    # carbon's natural 13C probability.
    leftover["C"] = max(0, leftover.get("C", 0) - n_label)
    natural = _natural_abundance(leftover, n_label + 20)
    natural_13c = dict(_ISOTOPE["C"])[1]
    tracer_probability = natural_13c + (
        LABEL_PURITY - natural_13c
    ) * float(enrichment)
    tracer = _binomial_pmf(n_label, tracer_probability)
    conv = np.convolve(tracer, natural)
    fracs = np.asarray(conv[: n_label + 1], dtype=np.float64)
    total = float(fracs.sum())
    if total <= 0:
        fracs = np.zeros(n_label + 1, dtype=np.float64)
        fracs[0] = 1.0
    else:
        fracs = fracs / total
    return tuple(float(x) for x in fracs)


def _pick_internal_standard(names: list[str]) -> str:
    lowered = [(name, name.lower()) for name in names]
    for needle in ("scyllo", "inositol"):
        for name, low in lowered:
            if needle in low:
                return name
    for name, low in lowered:
        if "norvaline" in low:
            return name
    return names[-1]


def _scenario_names(*groups: frozenset[Scenario]) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for scenario in sorted(group, key=lambda s: s.name):
            if scenario is Scenario.CLEAN:
                continue
            if scenario.name not in seen:
                names.append(scenario.name)
                seen.add(scenario.name)
    return tuple(names) if names else (Scenario.CLEAN.name,)


def _assign_exclusive(
    rng: np.random.Generator,
    names: list[str],
    scenarios: tuple[Scenario, ...],
    min_each: int,
) -> dict[str, frozenset[Scenario]]:
    assigned = {name: frozenset({Scenario.CLEAN}) for name in names}
    if not names or not scenarios:
        return assigned
    order = names.copy()
    rng.shuffle(order)
    per = min(min_each, len(order) // len(scenarios))
    if per <= 0:
        return assigned
    cursor = 0
    for scenario in scenarios:
        for name in order[cursor : cursor + per]:
            assigned[name] = frozenset({scenario})
        cursor += per
    return assigned


def _choose_near_pairs(names: set[str], pairs: tuple[tuple[str, str], ...]) -> list[tuple[str, str]]:
    chosen: list[tuple[str, str]] = []
    for left, right in pairs:
        if left in names and right in names:
            chosen.append((left, right))
    return chosen


def _load_labelled_targets() -> tuple[list[Target], pd.DataFrame, str]:
    df = pd.read_excel(LABELLED_XLS, engine="xlrd")
    names = [str(n) for n in df["name"].tolist()]
    is_name = _pick_internal_standard(names)
    df = df.copy()
    df["MMFiles"] = "*_MM_01*,*_MM_02*"
    if "Sorbitol-Mannitol" in set(names):
        df.loc[df["name"] == "Sorbitol-Mannitol", "tR"] = 15.765
    is_mask = df["name"].astype(str) == is_name
    df.loc[is_mask, "IntStdAmount"] = 1.0
    df.loc[is_mask, "AmountInStdMix"] = 1.0

    targets: list[Target] = []
    for _, row in df.iterrows():
        name = str(row["name"])
        mass0 = float(row["Mass0"])
        label_atoms = int(row["LabelAtoms"])
        loffset = float(row["lOffset"])
        roffset = float(row["rOffset"])
        amount = float(row["AmountInStdMix"]) if pd.notna(row["AmountInStdMix"]) else None
        formula = str(row["Formula"]) if pd.notna(row["Formula"]) else None
        channels = tuple(mass0 + i for i in range(label_atoms + 1))
        targets.append(
            Target(
                name=name,
                rt=float(row["tR"]),
                loffset=loffset,
                roffset=roffset,
                channels=channels,
                channel_fractions=None,
                shape=_peak_shape(loffset, roffset),
                base_height=BASE_HEIGHT,
                amount=amount,
                is_internal_standard=name == is_name,
                label_atoms=label_atoms,
                formula=formula,
            )
        )
    return targets, df, is_name


def _nominal(mz: float) -> int:
    return int(np.floor(mz + 0.5))


def _plan_unlabelled_rows(
    rng: np.random.Generator, n_compounds: int
) -> tuple[list[dict], str, list[tuple[str, str]]]:
    n_compounds = max(1, n_compounds)
    names = list(_NAMED_UNLABELLED)
    next_idx = 1
    while len(names) < n_compounds:
        names.append(f"U{next_idx:03d}")
        next_idx += 1
    names = names[:n_compounds]
    is_name = _pick_internal_standard(names)

    rts = np.linspace(2.4, 23.6, n_compounds)
    rts = np.clip(rts + rng.normal(0.0, 0.07, size=n_compounds), 2.2, 23.8)

    used_q: set[int] = set()
    rows: list[dict] = []
    pair_idxs = [
        (i, i + 1)
        for i in range(8, n_compounds - 1, max(n_compounds // 4, 8))
    ][:4]
    if n_compounds >= 8 and len(pair_idxs) < 4:
        pair_idxs = [(i, j) for i, j in ((2, 3), (12, 13), (22, 23), (32, 33)) if j < n_compounds]
    for i, name in enumerate(names):
        loffset = float(rng.choice([0.08, 0.10, 0.12, 0.15]))
        roffset = float(rng.choice([0.10, 0.12, 0.14, 0.18]))
        has_v2 = i % 4 != 0
        has_q1_ratio = i % 5 != 0
        has_q2_ratio = has_v2 and i % 3 != 0
        q_ion = 90.0 + 3.0 * i
        while _nominal(q_ion) in used_q:
            q_ion += 1.0
        used_q.add(_nominal(q_ion))
        v1 = q_ion + 31.0
        if _nominal(v1) == _nominal(q_ion):
            v1 += 2.0
        v2 = q_ion + 58.0 if has_v2 else None
        if v2 is not None and _nominal(v2) in {_nominal(q_ion), _nominal(v1)}:
            v2 += 3.0
        q1_ratio = float(rng.uniform(0.22, 0.55)) if has_q1_ratio else None
        q2_ratio = float(rng.uniform(0.12, 0.35)) if has_q2_ratio else None
        amount = 1.0 if name == is_name else float(rng.choice([2.0, 3.5, 5.0, 8.0]))
        rows.append(
            {
                "name": name,
                "tR": float(rts[i]),
                "lOffset": loffset,
                "rOffset": roffset,
                "tR Window": max(loffset, roffset),
                "QIon": q_ion,
                "QualifierIon1": v1,
                "QualifierIon2": v2,
                "q1_ratio": q1_ratio,
                "q2_ratio": q2_ratio,
                "amount": amount,
                "istd": 1.0 if name == is_name else None,
                "is_is": name == is_name,
            }
        )

    for left_i, right_i in pair_idxs:
        rows[right_i]["tR"] = rows[left_i]["tR"] + 0.04
        rows[right_i]["QIon"] = rows[left_i]["QIon"]
        v1 = rows[right_i]["QIon"] + 41.0
        if _nominal(v1) == _nominal(rows[right_i]["QIon"]):
            v1 += 2.0
        rows[right_i]["QualifierIon1"] = v1
        if rows[right_i]["QualifierIon2"] is not None:
            v2 = rows[right_i]["QIon"] + 67.0
            if _nominal(v2) in {
                _nominal(rows[right_i]["QIon"]),
                _nominal(rows[right_i]["QualifierIon1"]),
            }:
                v2 += 3.0
            rows[right_i]["QualifierIon2"] = v2

    pairs = [(rows[i]["name"], rows[j]["name"]) for i, j in pair_idxs]
    return rows, is_name, pairs


def _unlabelled_targets(
    rng: np.random.Generator, n_compounds: int
) -> tuple[list[Target], pd.DataFrame, str, list[tuple[str, str]], set[str]]:
    rows, is_name, pairs = _plan_unlabelled_rows(rng, n_compounds)
    has_ratio = {
        row["name"]
        for row in rows
        if row["q1_ratio"] is not None or row["q2_ratio"] is not None
    }
    csv_rows = []
    targets: list[Target] = []
    for row in rows:
        channels = [float(row["QIon"]), float(row["QualifierIon1"])]
        fractions = [1.0, float(row["q1_ratio"] if row["q1_ratio"] is not None else 0.35)]
        if row["QualifierIon2"] is not None:
            channels.append(float(row["QualifierIon2"]))
            fractions.append(
                float(row["q2_ratio"] if row["q2_ratio"] is not None else 0.20)
            )
        targets.append(
            Target(
                name=row["name"],
                rt=float(row["tR"]),
                loffset=float(row["lOffset"]),
                roffset=float(row["rOffset"]),
                channels=tuple(channels),
                channel_fractions=tuple(fractions),
                shape=_peak_shape(float(row["lOffset"]), float(row["rOffset"])),
                base_height=BASE_HEIGHT,
                amount=float(row["amount"]),
                is_internal_standard=bool(row["is_is"]),
                label_atoms=0,
                formula=None,
            )
        )
        csv_rows.append(
            {
                "name": row["name"],
                "tR": row["tR"],
                "lOffset": row["lOffset"],
                "rOffset": row["rOffset"],
                "tR Window": row["tR Window"],
                "QIon": row["QIon"],
                "QualifierIon1": row["QualifierIon1"],
                "QualifierIon2": row["QualifierIon2"] if row["QualifierIon2"] is not None else "",
                "Qualifier 1 Ratio": row["q1_ratio"] if row["q1_ratio"] is not None else "",
                "Qualifier 1 Tolerance": 0.25 if row["q1_ratio"] is not None else "",
                "Qualifier 2 Ratio": row["q2_ratio"] if row["q2_ratio"] is not None else "",
                "Qualifier 2 Tolerance": 0.25 if row["q2_ratio"] is not None else "",
                "Amount in StdMix": row["amount"],
                "Int Std amount": row["istd"] if row["istd"] is not None else "",
                "MM Files": "MM_*",
            }
        )
    return targets, pd.DataFrame(csv_rows), is_name, pairs, has_ratio


def _build_samples(
    rng: np.random.Generator,
    mode: str,
    n_samples: int,
) -> tuple[list[SampleSpec], dict[str, float]]:
    n_std = min(2, n_samples)
    samples: list[SampleSpec] = []
    for i in range(n_std):
        if mode == "labelled":
            name = f"Std_MM_{i + 1:02d}"
        else:
            name = f"MM_{i + 1:02d}"
        samples.append(
            SampleSpec(
                name=name,
                kind=SampleKind.STANDARD_MIX,
                scale=1.0,
                enrichment=0.0,
                scenarios=frozenset({Scenario.CLEAN}),
            )
        )
    bio_names: list[str] = []
    for i in range(n_samples - n_std):
        name = f"Bio_{i + 1:03d}"
        bio_names.append(name)
        samples.append(
            SampleSpec(
                name=name,
                kind=SampleKind.BIOLOGICAL,
                scale=float(np.clip(rng.normal(1.0, 0.12), 0.55, 1.7)),
                enrichment=float(np.clip(rng.normal(0.20, 0.07), 0.05, 0.35)),
                scenarios=frozenset({Scenario.CLEAN}),
            )
        )
    assigned = _assign_exclusive(rng, bio_names, _SAMPLE_SCENARIOS, 8)
    out: list[SampleSpec] = []
    rt_shifts: dict[str, float] = {}
    for spec in samples:
        scenarios = assigned.get(spec.name, spec.scenarios)
        if spec.kind is SampleKind.STANDARD_MIX:
            scenarios = frozenset({Scenario.CLEAN})
        effect = _effects_for(scenarios)
        shift = 0.0
        if effect.rt_shift_max > 0:
            shift = float(rng.uniform(effect.rt_shift_min, effect.rt_shift_max))
        rt_shifts[spec.name] = shift
        out.append(
            SampleSpec(
                name=spec.name,
                kind=spec.kind,
                scale=spec.scale,
                enrichment=spec.enrichment,
                scenarios=scenarios,
            )
        )
    return out, rt_shifts


def _assign_compound_scenarios(
    rng: np.random.Generator,
    targets: list[Target],
    near_pairs: list[tuple[str, str]],
    is_name: str,
) -> dict[str, frozenset[Scenario]]:
    names = [t.name for t in targets]
    near_names = {a for pair in near_pairs for a in pair}
    pool = [n for n in names if n not in near_names]
    others = tuple(s for s in _COMPOUND_SCENARIOS if s is not Scenario.NEAR_COELUTION)
    assigned = _assign_exclusive(rng, pool, others, 8)
    for name in names:
        assigned.setdefault(name, frozenset({Scenario.CLEAN}))
    if len(near_names) >= 8 or (near_names and len(targets) < 16):
        for name in near_names:
            assigned[name] = frozenset({Scenario.NEAR_COELUTION})
    elif near_names:
        extra = [n for n in pool if assigned[n] == frozenset({Scenario.CLEAN})]
        rng.shuffle(extra)
        needed = max(0, 8 - len(near_names))
        for name in extra[:needed]:
            near_names.add(name)
        for name in near_names:
            assigned[name] = frozenset({Scenario.NEAR_COELUTION})
    if is_name in assigned and Scenario.TRACE_LEVEL in assigned[is_name]:
        swap = next(
            (
                name
                for name in names
                if name != is_name and assigned[name] == frozenset({Scenario.CLEAN})
            ),
            None,
        )
        if swap is not None:
            assigned[swap] = frozenset({Scenario.TRACE_LEVEL})
        assigned[is_name] = frozenset({Scenario.CLEAN})
    return assigned


def _assign_cell_scenarios(
    rng: np.random.Generator,
    mode: str,
    samples: list[SampleSpec],
    targets: list[Target],
    unlabelled_has_ratio: set[str],
) -> dict[tuple[str, str], frozenset[Scenario]]:
    if mode == "labelled":
        cell_scens = (
            Scenario.MISSING,
            Scenario.HEAVY_LABEL,
            Scenario.UNLABELLED_CONTROL,
        )
    else:
        cell_scens = (Scenario.MISSING, Scenario.RATIO_FAIL)
    total = len(samples) * len(targets)
    n_each = int(math.ceil(0.05 * total)) if total else 0
    assigned: dict[tuple[str, str], frozenset[Scenario]] = {}
    used: set[tuple[str, str]] = set()

    def _eligible(scenario: Scenario) -> list[tuple[str, str]]:
        cells: list[tuple[str, str]] = []
        for sample in samples:
            if sample.kind is SampleKind.STANDARD_MIX:
                continue
            for target in targets:
                key = (sample.name, target.name)
                if target.is_internal_standard and scenario is Scenario.MISSING:
                    continue
                if scenario in (Scenario.HEAVY_LABEL, Scenario.UNLABELLED_CONTROL):
                    if target.label_atoms <= 0 or target.is_internal_standard:
                        continue
                if scenario is Scenario.RATIO_FAIL and target.name not in unlabelled_has_ratio:
                    continue
                cells.append(key)
        return cells

    for scenario in cell_scens:
        pool = [c for c in _eligible(scenario) if c not in used]
        rng.shuffle(pool)
        take = min(n_each, len(pool))
        for key in pool[:take]:
            assigned[key] = frozenset({scenario})
            used.add(key)
    for sample in samples:
        for target in targets:
            assigned.setdefault((sample.name, target.name), frozenset({Scenario.CLEAN}))
    return assigned


def _amount(target: Target) -> float:
    if target.amount is None or target.amount <= 0:
        return 1.0
    return float(target.amount)


def _cell_enrichment(
    sample: SampleSpec,
    effect: ScenarioDelta,
    rng: np.random.Generator,
) -> float:
    if sample.kind is SampleKind.STANDARD_MIX:
        return 0.0
    if effect.enrichment_fixed is not None:
        return float(effect.enrichment_fixed)
    if effect.enrichment_min is not None and effect.enrichment_max is not None:
        return float(rng.uniform(effect.enrichment_min, effect.enrichment_max))
    return float(sample.enrichment)


def _channel_fractions(
    target: Target,
    enrichment: float,
    ratio_mul: float,
) -> tuple[float, ...]:
    if target.channel_fractions is None:
        return labelled_channel_fractions(target.formula, target.label_atoms, enrichment)
    fracs = list(target.channel_fractions)
    if ratio_mul != 1.0 and len(fracs) > 1:
        fracs = [fracs[0], *[f * ratio_mul for f in fracs[1:]]]
    return tuple(float(f) for f in fracs)


def _noiseless_area(
    rt_lo: float,
    rt_hi: float,
    center: float,
    amplitude: float,
    sigma: float,
    tau: float,
    shoulder_amp: float,
    shoulder_dt: float,
) -> float:
    if rt_hi <= rt_lo or (amplitude <= 0 and shoulder_amp <= 0):
        return 0.0
    grid = np.linspace(rt_lo, rt_hi, TRUTH_GRID, dtype=np.float64)
    trace = _emg_trace(grid, center, amplitude, sigma, tau)
    if shoulder_amp > 0:
        trace = trace + _emg_trace(grid, center + shoulder_dt, shoulder_amp, sigma, tau)
    return float(_TRAPZ(trace, grid))


def _slice_bounds(
    time_min: np.ndarray, lo: float, hi: float
) -> tuple[int, int]:
    start = int(np.searchsorted(time_min, lo, side="left"))
    stop = int(np.searchsorted(time_min, hi, side="right"))
    start = max(0, start)
    stop = min(time_min.size, stop)
    if stop <= start:
        return 0, 0
    return start, stop


def _baseline_on_window(
    window: np.ndarray,
    rng: np.random.Generator,
    level: float,
    effect: ScenarioDelta,
    run_start: float,
    run_duration: float,
) -> np.ndarray:
    if window.size == 0:
        return window
    base = _baseline_trace(window, rng, level * effect.baseline_level_mul)
    if effect.baseline_noise_mul != 1.0:
        extra = rng.normal(
            0.0,
            0.12 * level * (effect.baseline_noise_mul - 1.0),
            size=window.size,
        )
        base = np.clip(base + extra, 1.0, None)
    if effect.drift_mul > 1.0:
        extra_drift = (
            (effect.drift_mul - 1.0)
            * 0.5
            * level
            * effect.baseline_level_mul
            * (window - run_start)
            / run_duration
        )
        base = np.clip(base + extra_drift, 1.0, None)
    return base


def _background_peaks(
    rng: np.random.Generator,
    targets: list[Target],
    time_lo: float,
    time_hi: float,
) -> list[tuple[float, float, float, float, float]]:
    target_mzs = {float(mz) for t in targets for mz in t.channels}
    target_rts = [float(t.rt) for t in targets]
    peaks: list[tuple[float, float, float, float, float]] = []
    attempts = 0
    while len(peaks) < N_BACKGROUND_PEAKS and attempts < 400:
        attempts += 1
        mz = float(rng.uniform(60.0, 450.0))
        rt = float(rng.uniform(time_lo + 0.4, time_hi - 0.4))
        nominal = _nominal(mz)
        if any(
            _nominal(t) == nominal and abs(rt - comp_rt) < 0.5
            for t in target_mzs
            for comp_rt in target_rts
        ):
            continue
        amp = float(np.exp(rng.uniform(np.log(300.0), np.log(9000.0))))
        sigma = float(rng.uniform(0.02, 0.06))
        tau = float(rng.uniform(0.0, 0.05))
        peaks.append((mz, rt, amp, sigma, tau))
    return peaks


def _render_sample(
    sample: SampleSpec,
    targets: list[Target],
    compound_scen: dict[str, frozenset[Scenario]],
    cell_scen: dict[tuple[str, str], frozenset[Scenario]],
    rt_shift: float,
    rng: np.random.Generator,
    scan_time_s: np.ndarray,
    time_min: np.ndarray,
) -> tuple[tuple[np.ndarray, ...], list[PeakTruth]]:
    n_scans = time_min.size
    run_start = float(time_min[0])
    run_duration = float(time_min[-1] - time_min[0])
    sample_effect = _effects_for(sample.scenarios)
    scan_chunks: list[np.ndarray] = []
    mass_chunks: list[np.ndarray] = []
    inten_chunks: list[np.ndarray] = []
    truths: list[PeakTruth] = []

    def _push(scans: np.ndarray, masses: np.ndarray, intens: np.ndarray) -> None:
        if scans.size:
            scan_chunks.append(scans)
            mass_chunks.append(masses)
            inten_chunks.append(intens)

    for target in targets:
        cell = cell_scen[(sample.name, target.name)]
        c_scen = compound_scen[target.name]
        effect = _compose(
            [
                sample_effect,
                _effects_for(c_scen),
                _effects_for(cell),
            ]
        )
        scen_names = _scenario_names(sample.scenarios, c_scen, cell)
        center = target.rt + rt_shift
        if not effect.present:
            truths.append(
                PeakTruth(
                    sample=sample.name,
                    compound=target.name,
                    scenarios=scen_names,
                    rt_actual=center,
                    present=False,
                    channel_mz=tuple(float(m) for m in target.channels),
                    channel_fractions=tuple(0.0 for _ in target.channels),
                    channel_heights=tuple(0.0 for _ in target.channels),
                    true_total_area=0.0,
                    true_channel_areas=tuple(0.0 for _ in target.channels),
                )
            )
            write_lo = target.rt - 0.45
            write_hi = target.rt + 0.45
            start, stop = _slice_bounds(time_min, write_lo, write_hi)
            if stop > start:
                window = time_min[start:stop]
                level = float(rng.uniform(35.0, 90.0))
                base = _baseline_on_window(
                    window, rng, level, effect, run_start, run_duration
                )
                for mz in target.channels:
                    _push(
                        *channel_points(
                            base,
                            mz,
                            rng,
                            scan_offset=start,
                            shot_scale=effect.shot_noise_mul,
                            clip=effect.clip,
                            active_fraction=0.0,
                        )
                    )
            continue

        height_mul = effect.height_mul
        if target.is_internal_standard:
            height_mul *= effect.is_height_mul
        amount = _amount(target)
        scale = 1.0 if sample.kind is SampleKind.STANDARD_MIX else sample.scale
        enrichment = _cell_enrichment(sample, effect, rng)
        fractions = _channel_fractions(target, enrichment, effect.ratio_mul)
        sigma = target.shape.sigma_min * effect.sigma_mul
        tau = max(target.shape.tau_min * effect.tau_mul, 1e-4)
        write_lo = min(target.rt, center) - WRITE_LEFT_MIN
        write_hi = max(target.rt, center) + WRITE_RIGHT_MIN
        if effect.overlap:
            write_hi = max(write_hi, center + effect.overlap_dt_max + 0.6)
        if effect.shoulder:
            write_hi = max(write_hi, center + effect.shoulder_dt + 0.6)
        start, stop = _slice_bounds(time_min, write_lo, write_hi)
        window = time_min[start:stop] if stop > start else time_min[:0]
        areas: list[float] = []
        heights: list[float] = []
        overlap_dt = 0.0
        overlap_frac = 0.0
        if effect.overlap:
            overlap_dt = float(rng.uniform(effect.overlap_dt_min, effect.overlap_dt_max))
            overlap_frac = float(
                rng.uniform(effect.overlap_height_min, effect.overlap_height_max)
            )
        for idx, (mz, frac) in enumerate(zip(target.channels, fractions)):
            amp = target.base_height * amount * scale * height_mul * frac
            shoulder_amp = amp * effect.shoulder_height_mul if effect.shoulder else 0.0
            peak = _emg_trace(window, center, amp, sigma, tau)
            if shoulder_amp > 0:
                peak = peak + _emg_trace(
                    window, center + effect.shoulder_dt, shoulder_amp, sigma, tau
                )
            if idx == 0 and overlap_frac > 0:
                peak = peak + _emg_trace(
                    window, center + overlap_dt, amp * overlap_frac, sigma, tau
                )
            level = float(rng.uniform(35.0, 90.0))
            base = _baseline_on_window(
                window, rng, level, effect, run_start, run_duration
            )
            _push(
                *channel_points(
                    peak + base,
                    mz,
                    rng,
                    scan_offset=start,
                    shot_scale=effect.shot_noise_mul,
                    clip=effect.clip,
                    active_fraction=1e-4,
                )
            )
            area = _noiseless_area(
                target.rt - target.loffset,
                target.rt + target.roffset,
                center,
                amp,
                sigma,
                tau,
                shoulder_amp,
                effect.shoulder_dt,
            )
            areas.append(area)
            heights.append(amp)
        truths.append(
            PeakTruth(
                sample=sample.name,
                compound=target.name,
                scenarios=scen_names,
                rt_actual=center,
                present=True,
                channel_mz=tuple(float(m) for m in target.channels),
                channel_fractions=tuple(float(f) for f in fractions),
                channel_heights=tuple(float(h) for h in heights),
                true_total_area=float(sum(areas)),
                true_channel_areas=tuple(areas),
            )
        )

    duration = run_duration
    for bleed_mz, bleed_amp in BLEED_IONS.items():
        ramp = bleed_amp * (0.55 + 0.9 * (time_min - time_min[0]) / duration)
        wobble = 1.0 + 0.06 * np.sin(
            2.0 * np.pi * time_min / rng.uniform(5.0, 11.0)
            + rng.uniform(0.0, 2.0 * np.pi)
        )
        if sample_effect.baseline_level_mul > 1.0:
            ramp = ramp * sample_effect.baseline_level_mul
        _push(
            *channel_points(
                ramp * wobble,
                bleed_mz,
                rng,
                shot_scale=sample_effect.shot_noise_mul,
                clip=sample_effect.clip,
                active_fraction=0.0,
            )
        )

    for bg_mz, bg_rt, bg_amp, bg_sigma, bg_tau in _background_peaks(
        rng, targets, float(time_min[0]), float(time_min[-1])
    ):
        start, stop = _slice_bounds(time_min, bg_rt - 0.8, bg_rt + 1.6)
        if stop <= start:
            continue
        window = time_min[start:stop]
        trace = _emg_trace(window, bg_rt, bg_amp, bg_sigma, max(bg_tau, 0.005))
        _push(
            *channel_points(
                trace,
                bg_mz,
                rng,
                scan_offset=start,
                shot_scale=sample_effect.shot_noise_mul,
                clip=sample_effect.clip,
            )
        )

    if scan_chunks:
        mass, intensity, scan_index, point_count, total = assemble_scan_arrays(
            n_scans,
            np.concatenate(scan_chunks),
            np.concatenate(mass_chunks),
            np.concatenate(inten_chunks),
        )
    else:
        mass, intensity, scan_index, point_count, total = assemble_scan_arrays(
            n_scans, np.zeros(0, dtype=np.int32), np.zeros(0), np.zeros(0)
        )
    return (scan_time_s, mass, intensity, scan_index, point_count, total), truths


def _json_ready(obj):
    if isinstance(obj, Enum):
        return obj.name
    if isinstance(obj, frozenset):
        return sorted(_json_ready(x) for x in obj)
    if isinstance(obj, tuple):
        return [_json_ready(x) for x in obj]
    if isinstance(obj, list):
        return [_json_ready(x) for x in obj]
    if isinstance(obj, dict):
        return {key: _json_ready(value) for key, value in obj.items()}
    if is_dataclass(obj) and not isinstance(obj, type):
        return {key: _json_ready(value) for key, value in asdict(obj).items()}
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, Path):
        return str(obj)
    return obj


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _generator_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in _GENERATOR_INPUTS:
        digest.update(path.name.encode("utf-8"))
        digest.update(bytes.fromhex(_file_sha256(path)))
    return digest.hexdigest()


def _manifest_fingerprint(payload: dict) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _write_manifest(
    path: Path,
    *,
    seed: int,
    mode: str,
    scan_dt_s: float,
    n_samples: int,
    n_compounds: int,
    internal_standard: str,
    samples: list[SampleSpec],
    compounds: list[Target],
    truths: list[PeakTruth],
) -> None:
    payload = {
        "seed": seed,
        "mode": mode,
        "scan_dt_s": scan_dt_s,
        "start_s": START_S,
        "end_s": END_S,
        "generator_fingerprint": _generator_fingerprint(),
        "n_samples": n_samples,
        "n_compounds": n_compounds,
        "internal_standard": internal_standard,
        "samples": _json_ready(samples),
        "compounds": _json_ready(compounds),
        "truths": _json_ready(truths),
    }
    artifacts = [path.parent / "compounds.csv", *sorted(path.parent.glob("*.cdf"))]
    payload["artifact_hashes"] = {
        artifact.name: _file_sha256(artifact) for artifact in artifacts
    }
    payload["manifest_fingerprint"] = _manifest_fingerprint(payload)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _generate_dataset_contents(
    mode: str,
    *,
    n_samples: int,
    seed: int,
    scan_dt_s: float,
    out_dir: Path,
) -> tuple[int, int, float, float]:
    started = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.cdf"):
        old.unlink()

    root = np.random.SeedSequence(int(seed))
    streams = root.spawn(1 + n_samples)
    assign_rng = np.random.default_rng(streams[0])

    if mode == "labelled":
        targets, compounds_df, is_name = _load_labelled_targets()
        near_pairs = _choose_near_pairs(
            {t.name for t in targets}, _LABELLED_NEAR_PAIRS
        )
        unlabelled_has_ratio: set[str] = set()
    else:
        targets, compounds_df, is_name, near_pairs, unlabelled_has_ratio = (
            _unlabelled_targets(assign_rng, 100)
        )

    compound_scen = _assign_compound_scenarios(
        assign_rng, targets, near_pairs, is_name
    )
    samples, rt_shifts = _build_samples(assign_rng, mode, n_samples)
    cell_scen = _assign_cell_scenarios(
        assign_rng, mode, samples, targets, unlabelled_has_ratio
    )
    compounds_df.to_csv(out_dir / "compounds.csv", index=False)

    scan_time_s = np.arange(START_S, END_S + scan_dt_s / 2, scan_dt_s, dtype=np.float64)
    time_min = scan_time_s / 60.0
    all_truths: list[PeakTruth] = []
    for spec, stream in zip(samples, streams[1:]):
        rng = np.random.default_rng(stream)
        arrays, truths = _render_sample(
            spec,
            targets,
            compound_scen,
            cell_scen,
            rt_shifts[spec.name],
            rng,
            scan_time_s,
            time_min,
        )
        (
            scan_t,
            mass,
            intensity,
            scan_index,
            point_count,
            total_intensity,
        ) = arrays
        _write_cdf(
            out_dir / f"{spec.name}.cdf",
            scan_time_s=scan_t,
            mass=mass,
            intensity=intensity,
            scan_index=scan_index,
            point_count=point_count,
            total_intensity=total_intensity,
        )
        all_truths.extend(truths)

    _write_manifest(
        out_dir / "manifest.json",
        seed=seed,
        mode=mode,
        scan_dt_s=scan_dt_s,
        n_samples=len(samples),
        n_compounds=len(targets),
        internal_standard=is_name,
        samples=samples,
        compounds=targets,
        truths=all_truths,
    )
    elapsed = time.perf_counter() - started
    cdf_bytes = sum(p.stat().st_size for p in out_dir.glob("*.cdf"))
    mb = cdf_bytes / (1024 * 1024)
    print(
        f"{mode}: {len(samples)} files, {len(targets)} compounds, "
        f"{mb:.1f} MB, {elapsed:.1f}s"
    )
    return len(samples), len(targets), mb, elapsed


def generate_dataset(
    mode: str,
    *,
    n_samples: int,
    seed: int,
    scan_dt_s: float,
    out_dir: Path,
) -> tuple[int, int, float, float]:
    """Generate into a staging directory and replace the corpus only on success."""
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    transaction_dir = Path(
        tempfile.mkdtemp(prefix=f".{out_dir.name}-generation-", dir=out_dir.parent)
    )
    staging_dir = transaction_dir / "new"
    backup_dir = transaction_dir / "old"
    try:
        result = _generate_dataset_contents(
            mode,
            n_samples=n_samples,
            seed=seed,
            scan_dt_s=scan_dt_s,
            out_dir=staging_dir,
        )
        had_previous = out_dir.exists()
        try:
            if had_previous:
                os.replace(out_dir, backup_dir)
            os.replace(staging_dir, out_dir)
        except BaseException:
            if had_previous and backup_dir.exists() and not out_dir.exists():
                os.replace(backup_dir, out_dir)
            raise
        return result
    finally:
        shutil.rmtree(transaction_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate deterministic labelled and unlabelled GC-MS benchmark "
            "datasets (CDF files, compound tables, and manifest.json ground truth)."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("labelled", "unlabelled", "both"),
        required=True,
        help="Which dataset to write.",
    )
    parser.add_argument("--n-samples", type=int, default=30, help="Samples per dataset (default 30).")
    parser.add_argument("--seed", type=int, default=1, help="Root SeedSequence seed.")
    parser.add_argument(
        "--scan-dt-s",
        type=float,
        default=0.5,
        help="Scan interval in seconds (default 0.5; use 0.1 for a denser axis).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output directory (labelled/ and unlabelled/ are created under it).",
    )
    args = parser.parse_args()
    if args.n_samples < 1:
        parser.error("--n-samples must be >= 1")
    if args.scan_dt_s <= 0:
        parser.error("--scan-dt-s must be > 0")

    modes = ("labelled", "unlabelled") if args.mode == "both" else (args.mode,)
    for mode in modes:
        generate_dataset(
            mode,
            n_samples=args.n_samples,
            seed=args.seed,
            scan_dt_s=args.scan_dt_s,
            out_dir=args.out / mode,
        )


if __name__ == "__main__":
    main()
