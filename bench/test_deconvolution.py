from __future__ import annotations

import numpy as np
import pytest

from manic.processors.chromatographic_peak_deconvolution import (
    _fit_joint_component_model_cached,
    _fit_single_component_model_cached,
    deconvolve_channel_matrix,
)
from manic.processors.integration import integrate_bundle_areas

# Level 4 / balanced gate is the shipped default. Level 7 with the gate off is
# the most expensive configuration and runs only with --bench-full.
LEVELS = {"4": ("auto", "balanced"), "7": ("auto", "off")}


def _clear_fit_caches() -> None:
    _fit_single_component_model_cached.cache_clear()
    _fit_joint_component_model_cached.cache_clear()


def _deconvolve_all(corpus, level: str) -> list[list[float]]:
    fit_type, noise_gate = LEVELS[level]
    _clear_fit_caches()
    out = []
    for compound, eic in corpus:
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
        areas, _corrected = integrate_bundle_areas(
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
        out.append([float(a) for a in areas])
    return out


@pytest.mark.parametrize("level", list(LEVELS))
def test_deconvolve_hard_windows(case, corpus, full, level, benchmark, repeat):
    if level == "7" and not full:
        pytest.skip("level 7 runs with --bench-full")
    areas = benchmark.pedantic(_deconvolve_all, args=(corpus, level), rounds=repeat)
    assert len(areas) == len(corpus)
    for (compound, eic), cell in zip(corpus, areas):
        channels = eic.intensity.shape[0] if eic.intensity.ndim > 1 else 1
        assert len(cell) == channels, compound.name
        assert all(np.isfinite(cell)) and all(a >= 0 for a in cell), compound.name
