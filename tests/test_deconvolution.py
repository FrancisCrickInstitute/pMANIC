import numpy as np
import pytest

from manic.processors.deconvolution import deconvolve_eic
from manic.processors.integration import calculate_peak_areas


def _gaussian(time, center, width, height):
    return height * np.exp(-0.5 * ((time - center) / width) ** 2)


def test_deconvolution_selects_component_closest_to_retention_time():
    time = np.linspace(0.0, 10.0, 201)
    early_peak = _gaussian(time, 4.0, 0.25, 10.0)
    target_peak = _gaussian(time, 7.0, 0.25, 6.0)
    intensity = early_peak + target_peak

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        stringency="medium",
    )

    assert result.selected_center == 7.0
    assert len(result.excluded) == 1
    assert np.any(result.selected_mask[time < 5.0])
    assert np.trapezoid(result.selected, time) < np.trapezoid(intensity, time)
    assert np.trapezoid(result.selected, time) == pytest.approx(
        np.trapezoid(target_peak, time), rel=1e-4
    )


def test_deconvolution_uses_shared_components_for_isotopologues():
    time = np.linspace(0.0, 10.0, 201)
    m0 = _gaussian(time, 4.0, 0.25, 10.0) + _gaussian(time, 7.0, 0.25, 6.0)
    m1 = _gaussian(time, 4.0, 0.25, 3.0) + _gaussian(time, 7.0, 0.25, 2.0)
    intensity = np.vstack([m0, m1])

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        stringency="medium",
    )

    assert result.selected.shape == intensity.shape
    assert len(result.excluded) == 2
    assert result.component_centers == [4.0, 7.0]
    assert np.trapezoid(result.selected[0], time) == pytest.approx(
        np.trapezoid(_gaussian(time, 7.0, 0.25, 6.0), time), rel=1e-4
    )
    assert np.trapezoid(result.selected[1], time) == pytest.approx(
        np.trapezoid(_gaussian(time, 7.0, 0.25, 2.0), time), rel=1e-4
    )


def test_deconvolution_detects_trace_specific_shoulders():
    time = np.linspace(8.30, 8.70, 201)
    blue = _gaussian(time, 8.53, 0.012, 3.0) + _gaussian(time, 8.59, 0.015, 7.0)
    orange = _gaussian(time, 8.60, 0.012, 18.0)
    intensity = np.vstack([blue, orange])

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=8.54,
        loffset=0.18,
        roffset=0.18,
        stringency="medium",
    )

    assert 8.52 < result.selected_center < 8.55
    assert len(result.excluded) == 1
    assert np.trapezoid(result.selected[0], time) < np.trapezoid(blue, time)
    assert np.trapezoid(result.selected[1], time) == pytest.approx(
        np.trapezoid(orange, time)
    )


def test_calculate_peak_areas_can_use_deconvolved_selected_component():
    time = np.linspace(0.0, 10.0, 201)
    early_peak = _gaussian(time, 4.0, 0.25, 10.0)
    target_peak = _gaussian(time, 7.0, 0.25, 6.0)
    intensity = early_peak + target_peak

    unchanged = calculate_peak_areas(
        time,
        intensity,
        label_atoms=0,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        deconvolution_stringency="off",
    )
    deconvolved = calculate_peak_areas(
        time,
        intensity,
        label_atoms=0,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        deconvolution_stringency="medium",
    )

    assert deconvolved[0] < unchanged[0]
    assert deconvolved[0] == pytest.approx(np.trapezoid(target_peak, time), rel=1e-4)


def test_baseline_correction_uses_selected_component_support_after_deconvolution():
    time = np.linspace(0.0, 10.0, 201)
    baseline = np.full_like(time, 5.0)
    early_peak = _gaussian(time, 4.0, 0.25, 10.0)
    target_peak = _gaussian(time, 7.0, 0.25, 6.0)
    intensity = baseline + early_peak + target_peak

    without_baseline = calculate_peak_areas(
        time,
        intensity,
        label_atoms=0,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        baseline_correction=False,
        deconvolution_stringency="medium",
    )
    with_baseline = calculate_peak_areas(
        time,
        intensity,
        label_atoms=0,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        baseline_correction=True,
        deconvolution_stringency="medium",
    )

    assert 0 < with_baseline[0] < without_baseline[0]
