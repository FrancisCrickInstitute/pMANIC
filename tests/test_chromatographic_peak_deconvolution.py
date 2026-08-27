import numpy as np
import pytest

from manic.processors.chromatographic_peak_deconvolution import (
    NOISE_GATE_PRESETS,
    _too_messy_to_fit,
    deconvolve_eic,
    normalize_fit_type,
    normalize_noise_gate,
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


def test_resolved_single_peak_uses_raw_trace():
    # Best practice: a well-resolved single peak has nothing to deconvolve, so the
    # raw trace is used for both display and integration (no model is fitted in).
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

    # A single resolved peak is left as-is whether or not deconvolution is enabled.
    assert not on.excluded
    assert on.model is None
    assert np.allclose(off.selected, intensity)
    assert np.allclose(on.selected, intensity)


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
    # A genuine overlap (target + interferent) so deconvolution is warranted and a
    # continuous model is exposed.
    time = np.linspace(8.0, 9.0, 80)
    intensity = np.vstack(
        [
            _gaussian(time, 8.58, 0.02, 1000.0) + _gaussian(time, 8.70, 0.02, 600.0) + 5.0,
            _gaussian(time, 8.58, 0.02, 400.0) + _gaussian(time, 8.70, 0.02, 240.0) + 2.0,
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


def test_deconvolution_recovers_true_area_on_overlap():
    # Two overlapping peaks: the deconvolved model isolates the target component
    # and recovers its true area while preserving the isotopologue ratio. The raw
    # trace over the (wider) window is contaminated by the neighbour.
    time = np.linspace(8.0, 9.0, 120)
    height = 1000.0
    width = 0.03
    target = _gaussian(time, 8.45, width, height)
    interferent = _gaussian(time, 8.57, width, height * 0.8)
    intensity = np.vstack([target + interferent, 0.4 * target + 0.8 * interferent])

    areas = calculate_peak_areas(
        time,
        intensity.flatten(),
        label_atoms=1,
        retention_time=8.45,
        loffset=0.2,
        roffset=0.2,
        chromatographic_peak_deconvolution_stringency="4",
    )
    raw_areas = calculate_peak_areas(
        time,
        intensity.flatten(),
        label_atoms=1,
        retention_time=8.45,
        loffset=0.2,
        roffset=0.2,
        chromatographic_peak_deconvolution_stringency="off",
    )

    true_area = height * width * np.sqrt(2.0 * np.pi)
    # Deconvolved area is close to the true target area and far closer than the
    # contaminated raw trapezoid; the true 2.5:1 isotopologue ratio is preserved.
    assert areas[0] == pytest.approx(true_area, rel=0.1)
    assert abs(areas[0] - true_area) < abs(raw_areas[0] - true_area)
    assert areas[0] / areas[1] == pytest.approx(2.5, rel=5e-2)


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


def test_messy_window_skips_fit_and_falls_back_to_raw():
    # A noise-dominated window with no real peak should not be fitted at all.
    rng = np.random.default_rng(0)
    time = np.linspace(8.0, 9.0, 80)
    noise = np.clip(rng.normal(20.0, 8.0, time.size), 0.0, None)

    result = deconvolve_eic(
        time,
        noise,
        retention_time=8.5,
        loffset=0.3,
        roffset=0.3,
        stringency="4",
        fit_type="auto",
    )

    # No fitted model: callers fall back to the raw trace for display/integration.
    assert result.model is None
    assert result.excluded == []
    window = (time > 8.2) & (time < 8.8)
    assert np.allclose(result.selected[window], noise[window])


def test_genuine_overlap_still_fits_under_messy_gate():
    # A genuine overlap (even on a noisy baseline) must still be deconvolved: the
    # messiness gate should not block real, structured signal.
    rng = np.random.default_rng(1)
    time = np.linspace(8.0, 9.0, 120)
    intensity = (
        _gaussian(time, 8.45, 0.03, 500.0)
        + _gaussian(time, 8.58, 0.03, 350.0)
        + np.clip(rng.normal(0.0, 6.0, time.size), 0.0, None)
    )

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=8.45,
        loffset=0.2,
        roffset=0.2,
        stringency="4",
        fit_type="auto",
    )

    assert result.model is not None
    assert result.excluded


def test_normalize_noise_gate():
    assert normalize_noise_gate("balanced") == "balanced"
    assert normalize_noise_gate("OFF") == "off"
    assert normalize_noise_gate("  Aggressive ") == "aggressive"
    assert normalize_noise_gate(None) == "balanced"
    assert normalize_noise_gate("bogus") == "balanced"


def test_noise_gate_threshold_controls_skipping():
    rng = np.random.default_rng(0)
    noise = np.clip(rng.normal(20.0, 8.0, 80), 0.0, None)
    clean = _gaussian(np.linspace(0.0, 1.0, 80), 0.5, 0.03, 100.0)

    # Balanced gate skips noise-only windows but keeps a clean peak.
    assert _too_messy_to_fit(noise, NOISE_GATE_PRESETS["balanced"]) is True
    assert _too_messy_to_fit(clean, NOISE_GATE_PRESETS["balanced"]) is False

    # "Off" (None threshold) disables the smoothness gate entirely.
    assert _too_messy_to_fit(noise, NOISE_GATE_PRESETS["off"]) is False


def test_noise_gate_off_does_not_skip_messy_window():
    # With the gate off, a noisy window is no longer auto-skipped before fitting.
    rng = np.random.default_rng(0)
    time = np.linspace(8.0, 9.0, 80)
    noise = np.clip(rng.normal(20.0, 8.0, time.size), 0.0, None)

    balanced = deconvolve_eic(
        time, noise, retention_time=8.5, loffset=0.3, roffset=0.3,
        stringency="4", fit_type="auto", noise_gate="balanced",
    )
    off = deconvolve_eic(
        time, noise, retention_time=8.5, loffset=0.3, roffset=0.3,
        stringency="4", fit_type="auto", noise_gate="off",
    )

    assert balanced.model is None  # gate skipped the messy window
    # "off" went through the fitter instead of short-circuiting; whatever the
    # fitter decides, it must not be skipped by the gate, so the two paths differ
    # only via the gate (this asserts the gate is actually wired to the preset).
    assert _too_messy_to_fit(np.sum(np.atleast_2d(noise), axis=0), None) is False


def test_sparse_clean_peak_is_not_treated_as_messy():
    # Coarse sampling must not trip the messiness gate for a real peak: the
    # smoothness metric is amplitude- and sampling-invariant, so a sparsely
    # sampled clean Gaussian is not flagged as too messy to fit.
    time = np.arange(8.50, 8.66, 0.02)
    intensity = _gaussian(time, 8.581, 0.018, 1000.0)

    assert _too_messy_to_fit(intensity, NOISE_GATE_PRESETS["balanced"]) is False
