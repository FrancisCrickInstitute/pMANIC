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

from pathlib import Path

import numpy as np
import pandas as pd
from netCDF4 import Dataset
from scipy.stats import exponnorm

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "testdata" / "unlabelled_synthetic"

# Chromatographic time axis (seconds → minutes after /60 in MANIC).
START_S = 60.0
END_S = 1200.0
DT_S = 0.5

# Compounds for the targeted method and synthetic chromatograms.
# sigma/tau control the EMG peak width and tailing (minutes).
COMPOUNDS = [
    {
        "name": "Alanine",
        "rt": 5.00,
        "loffset": 0.12,
        "roffset": 0.12,
        "quant": 116.0,
        "q1": 147.0,
        "q1_ratio": 0.45,
        "q2": 73.0,
        "q2_ratio": 0.25,
        "amount": 5.0,
        "istd_amt": None,
        "sigma": 0.030,
        "tau": 0.020,
    },
    {
        "name": "Lactate",
        "rt": 6.50,
        "loffset": 0.12,
        "roffset": 0.12,
        "quant": 117.0,
        "q1": 147.0,
        "q1_ratio": 0.35,
        "q2": None,
        "q2_ratio": None,
        "amount": 8.0,
        "istd_amt": None,
        "sigma": 0.038,
        "tau": 0.030,
    },
    {
        "name": "Citrate",
        "rt": 12.00,
        "loffset": 0.15,
        "roffset": 0.15,
        "quant": 273.0,
        "q1": 147.0,
        "q1_ratio": 0.42,
        "q2": 73.0,
        "q2_ratio": 0.20,
        "amount": 3.0,
        "istd_amt": None,
        "sigma": 0.045,
        "tau": 0.040,
    },
    {
        "name": "scyllo-Inositol",
        "rt": 14.50,
        "loffset": 0.12,
        "roffset": 0.12,
        "quant": 318.0,
        "q1": 217.0,
        "q1_ratio": 0.30,
        "q2": None,
        "q2_ratio": None,
        "amount": 1.0,
        "istd_amt": 10.0,
        "sigma": 0.035,
        "tau": 0.025,
    },
]

# Silicone column bleed ions (nominal m/z → base amplitude in counts).
BLEED_IONS = {73.0: 260.0, 147.0: 420.0, 207.0: 350.0, 281.0: 520.0}

# Number of untargeted background peaks that make the TIC look like a real run.
N_BACKGROUND_PEAKS = 22

# Sample definitions: name, RT shift (min), quant scale, ratio scale, notes
SAMPLES = [
    ("Sample_01", 0.00, 1.00, 1.00, "nominal biological sample"),
    ("Sample_02", 0.02, 0.70, 1.00, "later RT, lower abundance"),
    ("Sample_03", -0.01, 1.25, 0.98, "earlier RT, higher abundance"),
    ("Sample_04_ratio_fail", 0.00, 1.00, 1.80, "Alanine qualifier ratio will fail QC"),
    ("Sample_05_rt_shift", 0.09, 1.00, 1.00, "RT near tolerance edge for Alanine"),
    ("MM_01", 0.00, 1.00, 1.00, "standard mixture replicate 1"),
    ("MM_02", 0.01, 1.05, 1.00, "standard mixture replicate 2"),
]


def _emg_trace(
    time_min: np.ndarray,
    center: float,
    amplitude: float,
    sigma: float,
    tau: float,
) -> np.ndarray:
    """Tailed chromatographic peak (exponentially modified Gaussian).

    Scaled so the apex lands on ``center`` with height ``amplitude``.
    """
    if amplitude <= 0 or sigma <= 0:
        return np.zeros_like(time_min)
    shape = max(tau / sigma, 1e-3)
    raw = exponnorm.pdf(time_min, shape, loc=center, scale=sigma)
    mode_t = float(time_min[int(np.argmax(raw))])
    # One correction pass so the apex (not the Gaussian mean) sits on center.
    raw = exponnorm.pdf(
        time_min, shape, loc=center + (center - mode_t), scale=sigma
    )
    peak = float(raw.max())
    if peak <= 0:
        return np.zeros_like(time_min)
    return amplitude * raw / peak


def _baseline_trace(
    time_min: np.ndarray, rng: np.random.Generator, level: float
) -> np.ndarray:
    """Low wavy chemical baseline: sine wander + upward drift + noise."""
    duration = float(time_min[-1] - time_min[0])
    phase = rng.uniform(0.0, 2.0 * np.pi)
    wander = 0.55 * level * np.sin(
        2.0 * np.pi * time_min / rng.uniform(4.0, 9.0) + phase
    )
    drift = 0.5 * level * (time_min - time_min[0]) / duration
    noise = rng.normal(0.0, 0.12 * level, size=time_min.size)
    return np.clip(level + wander + drift + noise, 1.0, None)


def _write_cdf(
    path: Path,
    *,
    scan_time_s: np.ndarray,
    mass: np.ndarray,
    intensity: np.ndarray,
    scan_index: np.ndarray,
    point_count: np.ndarray,
    total_intensity: np.ndarray,
) -> None:
    with Dataset(path, "w", format="NETCDF3_CLASSIC") as cdf:
        n_scans = len(scan_time_s)
        n_points = len(mass)
        cdf.createDimension("scan_number", n_scans)
        cdf.createDimension("point_number", n_points)

        v_time = cdf.createVariable("scan_acquisition_time", "f8", ("scan_number",))
        v_mass = cdf.createVariable("mass_values", "f8", ("point_number",))
        v_inten = cdf.createVariable("intensity_values", "f8", ("point_number",))
        v_index = cdf.createVariable("scan_index", "i4", ("scan_number",))
        v_count = cdf.createVariable("point_count", "i4", ("scan_number",))
        v_tic = cdf.createVariable("total_intensity", "f8", ("scan_number",))

        v_time[:] = scan_time_s
        v_mass[:] = mass
        v_inten[:] = intensity
        v_index[:] = scan_index
        v_count[:] = point_count
        v_tic[:] = total_intensity


def _add_channel(
    masses_by_scan: list[list[float]],
    intens_by_scan: list[list[float]],
    time_min: np.ndarray,
    mz: float,
    trace: np.ndarray,
    rng: np.random.Generator,
    *,
    active_fraction: float = 1e-4,
) -> None:
    """Materialise a trace as jittered mass/intensity points per scan."""
    amplitude = float(trace.max()) if trace.size else 0.0
    if amplitude <= 0:
        return
    active = np.where(trace > amplitude * active_fraction)[0]
    for idx in active:
        signal = float(trace[idx])
        noise = float(rng.normal(0.0, 1.5 + 0.012 * signal))
        mass_jitter = float(np.clip(rng.normal(0.0, 0.02), -0.05, 0.05))
        masses_by_scan[idx].append(mz + mass_jitter)
        intens_by_scan[idx].append(max(1.0, signal + noise))


def _background_peaks(
    time_min: np.ndarray, rng: np.random.Generator
) -> list[tuple[float, float, float, float, float]]:
    """Untargeted peaks for a realistic TIC: (mz, rt, amp, sigma, tau)."""
    target_mzs = {
        float(c[key])
        for c in COMPOUNDS
        for key in ("quant", "q1", "q2")
        if c[key] is not None
    }
    target_rts = [float(c["rt"]) for c in COMPOUNDS]
    peaks: list[tuple[float, float, float, float, float]] = []
    attempts = 0
    while len(peaks) < N_BACKGROUND_PEAKS and attempts < 200:
        attempts += 1
        mz = float(rng.uniform(60.0, 350.0))
        rt = float(rng.uniform(1.5, 19.5))
        # Keep the designed QC story intact: no interference on target channels.
        nominal = int(np.floor(mz + 0.5))
        if any(
            int(np.floor(t + 0.5)) == nominal
            and abs(rt - comp_rt) < 0.5
            for t in target_mzs
            for comp_rt in target_rts
        ):
            continue
        amp = float(np.exp(rng.uniform(np.log(300.0), np.log(9000.0))))
        sigma = float(rng.uniform(0.02, 0.06))
        tau = float(rng.uniform(0.0, 0.05))
        peaks.append((mz, rt, amp, sigma, tau))
    return peaks


def build_sample_cdf(
    sample_name: str,
    rt_shift: float,
    quant_scale: float,
    ratio_scale: float,
) -> tuple[np.ndarray, ...]:
    scan_time_s = np.arange(START_S, END_S + DT_S / 2, DT_S, dtype=np.float64)
    time_min = scan_time_s / 60.0
    duration = float(time_min[-1] - time_min[0])

    masses_by_scan: list[list[float]] = [[] for _ in scan_time_s]
    intens_by_scan: list[list[float]] = [[] for _ in scan_time_s]

    rng = np.random.default_rng(abs(hash(sample_name)) % (2**32))

    # Targeted compound channels on a shared per-channel chemical baseline.
    for compound in COMPOUNDS:
        center = (
            float(compound["rt"]) + rt_shift + float(rng.normal(0.0, 0.004))
        )
        compound_scale = quant_scale * float(
            np.clip(rng.normal(1.0, 0.05), 0.5, 1.6)
        )
        base_amp = 2.0e4 * float(compound["amount"]) * compound_scale
        if compound["name"] == "Alanine" and sample_name == "Sample_04_ratio_fail":
            local_ratio_scale = ratio_scale
        else:
            local_ratio_scale = 1.0 if "ratio_fail" in sample_name else ratio_scale

        channel_specs = [
            (float(compound["quant"]), 1.0),
            (float(compound["q1"]), float(compound["q1_ratio"]) * local_ratio_scale),
        ]
        if compound["q2"] is not None:
            channel_specs.append(
                (float(compound["q2"]), float(compound["q2_ratio"]) * local_ratio_scale)
            )

        for mz, relative in channel_specs:
            peak = _emg_trace(
                time_min,
                center,
                base_amp * relative,
                float(compound["sigma"]),
                float(compound["tau"]),
            )
            baseline = _baseline_trace(
                time_min, rng, level=float(rng.uniform(35.0, 90.0))
            )
            _add_channel(
                masses_by_scan,
                intens_by_scan,
                time_min,
                mz,
                peak + baseline,
                rng,
                active_fraction=0.0,
            )

    # Column bleed: always present, rising across the temperature program.
    for bleed_mz, bleed_amp in BLEED_IONS.items():
        ramp = bleed_amp * (0.55 + 0.9 * (time_min - time_min[0]) / duration)
        wobble = 1.0 + 0.06 * np.sin(
            2.0 * np.pi * time_min / rng.uniform(5.0, 11.0)
            + rng.uniform(0.0, 2.0 * np.pi)
        )
        _add_channel(
            masses_by_scan,
            intens_by_scan,
            time_min,
            bleed_mz,
            ramp * wobble,
            rng,
            active_fraction=0.0,
        )

    # Untargeted background compounds so the TIC looks like a real extract.
    for bg_mz, bg_rt, bg_amp, bg_sigma, bg_tau in _background_peaks(time_min, rng):
        trace = _emg_trace(time_min, bg_rt, bg_amp, bg_sigma, max(bg_tau, 0.005))
        _add_channel(masses_by_scan, intens_by_scan, time_min, bg_mz, trace, rng)

    mass_chunks: list[np.ndarray] = []
    inten_chunks: list[np.ndarray] = []
    scan_index = np.zeros(len(scan_time_s), dtype=np.int32)
    point_count = np.zeros(len(scan_time_s), dtype=np.int32)
    total_intensity = np.zeros(len(scan_time_s), dtype=np.float64)

    cursor = 0
    for i, (mzs, ints) in enumerate(zip(masses_by_scan, intens_by_scan)):
        m_arr = np.asarray(mzs, dtype=np.float64)
        i_arr = np.asarray(ints, dtype=np.float64)
        order = np.argsort(m_arr)
        m_arr = m_arr[order]
        i_arr = i_arr[order]
        scan_index[i] = cursor
        point_count[i] = len(m_arr)
        total_intensity[i] = float(i_arr.sum())
        mass_chunks.append(m_arr)
        inten_chunks.append(i_arr)
        cursor += len(m_arr)

    return (
        scan_time_s,
        np.concatenate(mass_chunks),
        np.concatenate(inten_chunks),
        scan_index,
        point_count,
        total_intensity,
    )


def write_compound_list(path: Path) -> None:
    rows = []
    for compound in COMPOUNDS:
        q2 = compound["q2"]
        q2_ratio = compound["q2_ratio"]
        istd_amt = compound["istd_amt"]
        rows.append(
            {
                "name": compound["name"],
                "tR": compound["rt"],
                "lOffset": compound["loffset"],
                "rOffset": compound["roffset"],
                "tR Window": max(compound["loffset"], compound["roffset"]),
                "QIon": compound["quant"],
                "ValIon1": compound["q1"],
                "ValIon2": q2 if q2 is not None else "",
                "Qualifier 1 Ratio": compound["q1_ratio"],
                "Qualifier 1 Tolerance": 0.25,
                "Qualifier 2 Ratio": q2_ratio if q2_ratio is not None else "",
                "Qualifier 2 Tolerance": 0.25 if q2_ratio is not None else "",
                "Amount in StdMix": compound["amount"],
                "Int Std amount": istd_amt if istd_amt is not None else "",
                "MM Files": "MM_*",
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def write_readme(path: Path) -> None:
    path.write_text(
        """# Synthetic unlabelled dataset

Generated by `scripts/generate_unlabelled_synthetic_data.py`. The
chromatograms mimic a real run: tailing peaks (exponentially modified
Gaussians), signal-dependent shot noise, upward-drifting silicone column
bleed (m/z 73/147/207/281), wavy chemical baselines on every target channel,
and untargeted background peaks in the TIC.

## How to load in MANIC

1. Start MANIC and choose **Unlabelled targeted analysis**.
2. **File → Load Compounds/Parameter List** → select `compounds.csv`.
3. **File → Load Raw Data (CDF)** → select this folder.
4. Set **scyllo-Inositol** as the internal standard if you want relative /
   semi-quantitative amounts.
5. Inspect EICs, then **File → Export Data...**.

## What to expect

| Sample | Purpose |
|---|---|
| `Sample_01`–`Sample_03` | Peaks within QC limits; identity supported |
| `Sample_04_ratio_fail` | Alanine qualifier ratios deliberately high → review |
| `Sample_05_rt_shift` | RT shifted +0.09 min (near Alanine tolerance) |
| `MM_01`, `MM_02` | Standard-mix files matched by `MM_*` |

Reference ion ratios in `compounds.csv` are fractional tolerances (±25%).

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

    for sample_name, rt_shift, quant_scale, ratio_scale, _note in SAMPLES:
        (
            scan_time_s,
            mass,
            intensity,
            scan_index,
            point_count,
            total_intensity,
        ) = build_sample_cdf(sample_name, rt_shift, quant_scale, ratio_scale)
        _write_cdf(
            OUT_DIR / f"{sample_name}.cdf",
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
