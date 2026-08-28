from types import SimpleNamespace

import numpy as np
import pytest

from manic.io.data_provider import DataProvider
from manic.processors.chromatographic_peak_deconvolution import (
    deconvolve_channel_matrix,
)
from manic.processors.display_deconvolution import integrated_display_areas


def _gaussian(time, center, width, height):
    return height * np.exp(-0.5 * ((time - center) / width) ** 2)


def _compound(**overrides):
    values = dict(
        retention_time=7.0,
        loffset=0.4,
        roffset=0.4,
        baseline_correction=0,
        deconvolution_level="4",
        deconvolution_fit_type="auto",
        deconvolution_noise_gate="balanced",
        is_unlabelled_target=False,
        formula="C6H12O6",
        label_atoms=1,
        label_type="C",
        tbdms=0,
        meox=0,
        me=0,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _row(compound):
    return {
        "label_atoms": compound.label_atoms,
        "retention_time": compound.retention_time,
        "loffset": compound.loffset,
        "roffset": compound.roffset,
        "formula": compound.formula,
        "label_type": compound.label_type,
        "tbdms": compound.tbdms,
        "meox": compound.meox,
        "me": compound.me,
        "deconvolution_level": compound.deconvolution_level,
        "deconvolution_fit_type": compound.deconvolution_fit_type,
        "deconvolution_noise_gate": compound.deconvolution_noise_gate,
    }


def _export_corrected(time, intensity, compound):
    bundle = deconvolve_channel_matrix(
        time,
        intensity,
        retention_time=compound.retention_time,
        loffset=compound.loffset,
        roffset=compound.roffset,
        stringency=compound.deconvolution_level,
        fit_type=compound.deconvolution_fit_type,
        noise_gate=compound.deconvolution_noise_gate,
    )
    _, corrected = DataProvider()._areas_from_deconvolved(
        time,
        bundle,
        _row(compound),
        intensity,
        use_legacy=False,
        baseline_correction=bool(compound.baseline_correction),
    )
    return bundle, corrected


def test_export_corrected_areas_match_preview_plot_areas():
    time = np.linspace(0.0, 10.0, 201)
    intensity = np.vstack(
        [
            _gaussian(time, 7.0, 0.25, 10.0),
            _gaussian(time, 7.0, 0.25, 3.0),
        ]
    )
    compound = _compound()
    _, export_areas = _export_corrected(time, intensity, compound)
    plot_areas = integrated_display_areas(
        time, intensity, compound, use_corrected=True
    )
    assert export_areas == pytest.approx(plot_areas)


def test_neighbour_outside_offsets_does_not_own_corrected_areas():
    time = np.linspace(14.40, 14.90, 251)
    intensity = np.vstack(
        [
            np.zeros_like(time),
            np.zeros_like(time),
            np.zeros_like(time),
            np.zeros_like(time),
            _gaussian(time, 14.73, 0.02, 1000.0),
        ]
    )
    compound = _compound(
        retention_time=14.661,
        loffset=0.05,
        roffset=0.02,
        label_atoms=4,
    )
    _, export_areas = _export_corrected(time, intensity, compound)
    plot_areas = integrated_display_areas(
        time, intensity, compound, use_corrected=True
    )
    assert export_areas == pytest.approx([0.0] * 5, abs=1e-6)
    assert plot_areas == pytest.approx([0.0] * 5, abs=1e-6)
    assert export_areas == pytest.approx(plot_areas)
