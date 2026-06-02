import numpy as np
import pytest

from manic.processors.chromatographic_peak_deconvolution import (
    deconvolve_eic,
    normalize_stringency,
)
from manic.processors.integration import calculate_peak_areas


def _gaussian(time, center, width, height):
    return height * np.exp(-0.5 * ((time - center) / width) ** 2)


def test_chromatographic_peak_deconvolution_selects_component_closest_to_retention_time():
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

    assert result.selected_center == pytest.approx(7.0)
    assert len(result.excluded) == 1
    assert np.any(result.selected_mask[time < 5.0])
    assert np.trapezoid(result.selected, time) < np.trapezoid(intensity, time)
    assert np.trapezoid(result.selected, time) == pytest.approx(
        np.trapezoid(target_peak, time), rel=1e-4
    )


def test_chromatographic_peak_deconvolution_uses_shared_components_for_isotopologues():
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
    assert len(result.excluded) == 1
    assert result.component_centers == pytest.approx([4.0, 7.0])
    assert np.trapezoid(result.selected[0], time) == pytest.approx(
        np.trapezoid(_gaussian(time, 7.0, 0.25, 6.0), time), rel=1e-4
    )
    assert np.trapezoid(result.selected[1], time) == pytest.approx(
        np.trapezoid(_gaussian(time, 7.0, 0.25, 2.0), time), rel=1e-4
    )


def test_chromatographic_peak_deconvolution_detects_trace_specific_shoulders():
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
    assert result.excluded
    assert np.trapezoid(result.selected[0], time) < np.trapezoid(blue, time)
    assert np.trapezoid(result.selected[1], time) < np.trapezoid(orange, time)


def test_chromatographic_peak_deconvolution_fits_single_peak_when_enabled():
    time = np.linspace(0.0, 10.0, 201)
    peak = _gaussian(time, 5.0, 0.3, 10.0)
    deterministic_noise = 0.15 * np.sin(time * 8.0)
    intensity = np.maximum(peak + deterministic_noise, 0.0)

    off = deconvolve_eic(
        time,
        intensity,
        retention_time=5.0,
        loffset=2.0,
        roffset=2.0,
        stringency="off",
    )
    on = deconvolve_eic(
        time,
        intensity,
        retention_time=5.0,
        loffset=2.0,
        roffset=2.0,
        stringency="4",
    )

    assert not on.excluded
    assert np.allclose(off.selected, intensity)
    assert not np.allclose(on.selected, intensity)
    assert np.trapezoid(on.selected, time) == pytest.approx(
        np.trapezoid(peak, time), rel=0.05
    )


def test_chromatographic_peak_deconvolution_accepts_numeric_resolution_levels():
    assert normalize_stringency("off") == "off"
    assert normalize_stringency("low") == "2"
    assert normalize_stringency("medium") == "4"
    assert normalize_stringency("high") == "6"
    assert normalize_stringency("7") == "7"


def test_joint_model_uses_isotopologue_specific_component_evidence():
    time = np.linspace(4.5, 5.8, 261)
    target_m0 = _gaussian(time, 5.0, 0.07, 12.0)
    target_m1 = _gaussian(time, 5.0, 0.07, 4.0)
    interference_m1 = _gaussian(time, 5.26, 0.06, 10.0)
    intensity = np.vstack([target_m0, target_m1 + interference_m1])

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=5.0,
        loffset=0.6,
        roffset=0.6,
        stringency="7",
    )

    assert 4.98 < result.selected_center < 5.02
    assert result.excluded
    assert np.trapezoid(result.selected[0], time) == pytest.approx(
        np.trapezoid(target_m0, time), rel=0.05
    )
    assert np.trapezoid(result.selected[1], time) < np.trapezoid(
        target_m1 + interference_m1, time
    )


def test_level_five_deconvolves_smaller_isotopologue_shoulder():
    time = np.linspace(8.28, 8.70, 211)
    m0 = _gaussian(time, 8.64, 0.012, 25.0)
    target_m1 = _gaussian(time, 8.64, 0.013, 5.0)
    interfering_m1 = _gaussian(time, 8.60, 0.010, 8.0)
    intensity = np.vstack([m0, target_m1 + interfering_m1])

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=8.64,
        loffset=0.16,
        roffset=0.04,
        stringency="5",
    )

    assert result.excluded
    assert result.component_centers == pytest.approx([8.60, 8.64], abs=0.01)
    assert np.trapezoid(result.selected[1], time) == pytest.approx(
        np.trapezoid(target_m1, time), rel=0.15
    )


def test_offsets_cut_fitted_curve_without_refitting_shape():
    time = np.linspace(8.28, 8.70, 211)
    target_m0 = _gaussian(time, 8.64, 0.012, 25.0)
    target_m1 = _gaussian(time, 8.64, 0.013, 5.0)
    shoulder_m1 = _gaussian(time, 8.60, 0.010, 8.0)
    intensity = np.vstack([target_m0, target_m1 + shoulder_m1])

    narrow = deconvolve_eic(
        time,
        intensity,
        retention_time=8.64,
        loffset=0.03,
        roffset=0.04,
        stringency="5",
    )
    wide = deconvolve_eic(
        time,
        intensity,
        retention_time=8.64,
        loffset=0.14,
        roffset=0.04,
        stringency="5",
    )

    overlap = np.asarray(narrow.selected_mask[1], dtype=bool) & np.asarray(
        wide.selected_mask[1], dtype=bool
    )
    assert np.any(overlap)
    assert narrow.selected[1, overlap] == pytest.approx(wide.selected[1, overlap])
    assert np.count_nonzero(wide.selected_mask[1]) > np.count_nonzero(
        narrow.selected_mask[1]
    )


def test_integration_offsets_do_not_define_deconvolution_fit_region():
    time = np.linspace(8.28, 8.70, 211)
    target_m0 = _gaussian(time, 8.64, 0.012, 25.0)
    target_m1 = _gaussian(time, 8.64, 0.013, 5.0)
    shoulder_m1 = _gaussian(time, 8.60, 0.010, 8.0)
    intensity = np.vstack([target_m0, target_m1 + shoulder_m1])

    areas = calculate_peak_areas(
        time,
        intensity.flatten(),
        label_atoms=1,
        retention_time=8.64,
        loffset=0.03,
        roffset=0.04,
        chromatographic_peak_deconvolution_stringency="5",
    )

    offset_mask = (time > 8.64 - 0.03) & (time < 8.64 + 0.04)
    assert areas[1] == pytest.approx(np.trapezoid(target_m1[offset_mask], time[offset_mask]), rel=0.2)
    assert areas[1] < np.trapezoid((target_m1 + shoulder_m1)[offset_mask], time[offset_mask])


def test_deconvolved_baseline_correction_excludes_excluded_components():
    time = np.linspace(8.28, 8.70, 211)
    baseline = np.full_like(time, 5.0)
    target_m0 = _gaussian(time, 8.64, 0.012, 25.0)
    target_m1 = _gaussian(time, 8.64, 0.013, 5.0)
    shoulder_m1 = _gaussian(time, 8.60, 0.010, 8.0)
    intensity = np.vstack([baseline + target_m0, baseline + target_m1 + shoulder_m1])

    corrected = calculate_peak_areas(
        time,
        intensity.flatten(),
        label_atoms=1,
        retention_time=8.64,
        loffset=0.06,
        roffset=0.04,
        baseline_correction=True,
        chromatographic_peak_deconvolution_stringency="5",
    )

    offset_mask = (time > 8.64 - 0.06) & (time < 8.64 + 0.04)
    expected = np.trapezoid(target_m1[offset_mask], time[offset_mask])
    assert corrected[1] == pytest.approx(expected, rel=0.25)
    assert corrected[1] > expected * 0.5


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
        chromatographic_peak_deconvolution_stringency="off",
    )
    deconvolved = calculate_peak_areas(
        time,
        intensity,
        label_atoms=0,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        chromatographic_peak_deconvolution_stringency="medium",
    )

    assert deconvolved[0] < unchanged[0]
    assert deconvolved[0] == pytest.approx(np.trapezoid(target_peak, time), rel=1e-4)


def test_baseline_correction_uses_selected_component_support_after_chromatographic_peak_deconvolution():
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
        chromatographic_peak_deconvolution_stringency="medium",
    )
    with_baseline = calculate_peak_areas(
        time,
        intensity,
        label_atoms=0,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        baseline_correction=True,
        chromatographic_peak_deconvolution_stringency="medium",
    )

    assert 0 < with_baseline[0] < without_baseline[0]
