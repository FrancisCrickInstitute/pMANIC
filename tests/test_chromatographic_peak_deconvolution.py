import numpy as np
import pytest

from manic.processors.chromatographic_peak_deconvolution import (
    deconvolve_eic,
    normalize_fit_type,
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


def test_normalize_fit_type_accepts_known_values_and_falls_back():
    assert normalize_fit_type(None) == "auto"
    assert normalize_fit_type("AUTO") == "auto"
    assert normalize_fit_type("gaussian") == "gaussian"
    assert normalize_fit_type("bi_gaussian") == "bi_gaussian"
    assert normalize_fit_type("emg") == "emg"
    assert normalize_fit_type("nonsense") == "auto"


def test_fit_type_forces_single_shape_and_still_resolves_components():
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
        stringency="6",
        fit_type="gaussian",
    )

    assert result.selected_center == pytest.approx(7.0, abs=0.05)
    assert result.excluded
    assert np.trapezoid(result.selected, time) == pytest.approx(
        np.trapezoid(target_peak, time), rel=0.05
    )


def test_calculate_peak_areas_accepts_per_compound_fit_type():
    time = np.linspace(0.0, 10.0, 201)
    early_peak = _gaussian(time, 4.0, 0.25, 10.0)
    target_peak = _gaussian(time, 7.0, 0.25, 6.0)
    intensity = early_peak + target_peak

    areas = calculate_peak_areas(
        time,
        intensity,
        label_atoms=0,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        chromatographic_peak_deconvolution_stringency="4",
        chromatographic_peak_deconvolution_fit_type="gaussian",
    )

    assert areas[0] == pytest.approx(np.trapezoid(target_peak, time), rel=1e-2)


def test_invalid_fit_type_falls_back_to_auto_behaviour():
    time = np.linspace(0.0, 10.0, 201)
    intensity = _gaussian(time, 5.0, 0.3, 10.0)

    forced = deconvolve_eic(
        time, intensity, retention_time=5.0, loffset=2.0, roffset=2.0,
        stringency="4", fit_type="nonsense",
    )
    auto = deconvolve_eic(
        time, intensity, retention_time=5.0, loffset=2.0, roffset=2.0,
        stringency="4", fit_type="auto",
    )

    assert np.allclose(forced.selected, auto.selected)


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


def test_deconvolution_exposes_continuous_model_matching_scan_points():
    time = np.linspace(8.0, 9.0, 80)
    intensity = np.vstack(
        [
            _gaussian(time, 8.58, 0.02, 1000.0) + 5.0,
            _gaussian(time, 8.58, 0.02, 400.0) + 2.0,
        ]
    )

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=8.58,
        loffset=0.1,
        roffset=0.1,
        stringency="4",
    )

    model = result.model
    assert model is not None
    # The continuous model reproduces the sampled selected curve exactly at the
    # acquisition scan points (it only adds detail between them).
    mask0 = np.asarray(result.selected_mask[0], dtype=bool)
    evaluated = model.evaluate_selected(time[mask0])
    assert evaluated[0] == pytest.approx(result.selected[0][mask0], abs=1e-9)
    # Evaluating on a denser grid stays within the same window.
    grid = np.linspace(model.integration_left, model.integration_right, 200)
    dense = model.evaluate_selected(grid)
    assert dense.shape == (2, 200)


def test_dense_model_integration_recovers_true_area_on_sparse_sampling():
    # A peak sampled coarsely so a scan-point trapezoid under-counts the apex.
    time = np.arange(8.50, 8.66, 0.02)
    height = 1000.0
    width = 0.018
    intensity = np.vstack(
        [_gaussian(time, 8.581, width, height), _gaussian(time, 8.581, width, height * 0.4)]
    )

    areas = calculate_peak_areas(
        time,
        intensity.flatten(),
        label_atoms=1,
        retention_time=8.581,
        loffset=0.05,
        roffset=0.05,
        chromatographic_peak_deconvolution_stringency="4",
    )
    raw_areas = calculate_peak_areas(
        time,
        intensity.flatten(),
        label_atoms=1,
        retention_time=8.581,
        loffset=0.05,
        roffset=0.05,
        chromatographic_peak_deconvolution_stringency="off",
    )

    true_area = height * width * np.sqrt(2.0 * np.pi)
    # Dense model integration is closer to the analytic Gaussian area than the
    # coarse raw trapezoid, and preserves the true 2.5:1 isotopologue ratio.
    assert abs(areas[0] - true_area) < abs(raw_areas[0] - true_area)
    assert areas[0] / areas[1] == pytest.approx(2.5, rel=1e-3)


def test_legacy_integration_ignores_dense_model():
    # Legacy (unit-spacing) integration must remain scan-point based, unchanged.
    time = np.linspace(8.0, 9.0, 80)
    intensity = _gaussian(time, 8.58, 0.02, 1000.0) + 5.0

    legacy = calculate_peak_areas(
        time,
        intensity,
        label_atoms=0,
        retention_time=8.58,
        loffset=0.1,
        roffset=0.1,
        use_legacy=True,
        chromatographic_peak_deconvolution_stringency="4",
    )
    assert legacy[0] > 0
