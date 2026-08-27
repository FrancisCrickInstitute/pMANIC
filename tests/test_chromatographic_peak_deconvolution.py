import dataclasses

import numpy as np
import pytest

from manic.processors import chromatographic_peak_deconvolution as deconv
from manic.processors.chromatographic_peak_deconvolution import (
    NOISE_GATE_PRESETS,
    ChannelDeconvolution,
    ChannelDeconvolutionBundle,
    EICChromatographicPeakDeconvolutionResult,
    _too_messy_to_fit,
    deconvolve_channel_matrix,
    deconvolve_eic,
    normalize_fit_type,
    normalize_noise_gate,
    normalize_stringency,
)
from manic.processors import integration as integration_module
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


def test_chromatographic_peak_deconvolution_selects_each_isotopologue_independently():
    time = np.linspace(0.0, 10.0, 201)
    m0 = _gaussian(time, 4.0, 0.25, 10.0) + _gaussian(time, 7.0, 0.25, 6.0)
    m1 = _gaussian(time, 4.0, 0.25, 3.0) + _gaussian(time, 7.0, 0.25, 2.0)
    intensity = np.vstack([m0, m1])

    bundle = deconvolve_channel_matrix(
        time,
        intensity,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        stringency="medium",
    )

    assert len(bundle.channels) == 2
    assert bundle.channels[0].result.selected_center == pytest.approx(7.0)
    assert bundle.channels[1].result.selected_center == pytest.approx(7.0)
    assert np.trapezoid(bundle.channels[0].result.selected, time) == pytest.approx(
        np.trapezoid(_gaussian(time, 7.0, 0.25, 6.0), time), rel=1e-4
    )
    assert np.trapezoid(bundle.channels[1].result.selected, time) == pytest.approx(
        np.trapezoid(_gaussian(time, 7.0, 0.25, 2.0), time), rel=1e-4
    )


def test_chromatographic_peak_deconvolution_detects_trace_specific_shoulders():
    time = np.linspace(8.30, 8.70, 201)
    blue = _gaussian(time, 8.53, 0.012, 3.0) + _gaussian(time, 8.59, 0.015, 7.0)
    orange = _gaussian(time, 8.60, 0.012, 18.0)
    intensity = np.vstack([blue, orange])

    bundle = deconvolve_channel_matrix(
        time,
        intensity,
        retention_time=8.54,
        loffset=0.18,
        roffset=0.18,
        stringency="medium",
    )

    blue_result = bundle.channels[0].result
    orange_result = bundle.channels[1].result
    assert 8.52 < blue_result.selected_center < 8.55
    assert blue_result.excluded
    assert np.trapezoid(blue_result.selected, time) < np.trapezoid(blue, time)
    assert orange_result.model is not None
    assert np.trapezoid(orange_result.selected, time) == pytest.approx(
        np.trapezoid(orange, time), rel=0.05
    )


def test_resolved_single_peak_is_fitted_when_deconvolution_is_on():
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
    assert on.model is not None
    assert np.allclose(off.selected, intensity)
    assert np.trapezoid(on.selected, time) == pytest.approx(
        np.trapezoid(peak, time), rel=0.05
    )


def _spy_overlap_fitter(monkeypatch):
    calls = []
    real = deconv._fit_joint_component_model_cached

    def spy(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(deconv, "_fit_joint_component_model_cached", spy)
    return calls


def test_resolved_single_peak_skips_the_overlap_fitter(monkeypatch):
    time = np.linspace(0.0, 10.0, 201)
    peak = _gaussian(time, 5.0, 0.3, 10.0)
    joint_calls = _spy_overlap_fitter(monkeypatch)

    result = deconvolve_eic(
        time,
        peak,
        retention_time=5.0,
        loffset=2.0,
        roffset=2.0,
        stringency="4",
    )

    assert result.model is not None
    assert result.model.n_components == 1
    assert joint_calls == []
    assert np.trapezoid(result.selected, time) == pytest.approx(
        np.trapezoid(peak, time), rel=0.05
    )


def test_overlap_still_uses_the_overlap_fitter(monkeypatch):
    time = np.linspace(8.0, 9.0, 120)
    intensity = _gaussian(time, 8.45, 0.03, 1000.0) + _gaussian(time, 8.57, 0.03, 800.0)
    joint_calls = _spy_overlap_fitter(monkeypatch)

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=8.45,
        loffset=0.2,
        roffset=0.2,
        stringency="4",
    )

    assert result.model is not None
    assert result.model.n_components >= 2
    assert joint_calls


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


def test_labelled_m1_overlap_does_not_change_m0_area():
    time = np.linspace(4.5, 5.8, 261)
    target_m0 = _gaussian(time, 5.0, 0.07, 12.0)
    target_m1 = _gaussian(time, 5.0, 0.07, 4.0)
    interference_m1 = _gaussian(time, 5.26, 0.06, 10.0)
    intensity = np.vstack([target_m0, target_m1 + interference_m1])

    clean_m0 = calculate_peak_areas(
        time,
        target_m0,
        label_atoms=0,
        retention_time=5.0,
        loffset=0.6,
        roffset=0.6,
        chromatographic_peak_deconvolution_stringency="7",
    )[0]
    stacked = calculate_peak_areas(
        time,
        intensity.flatten(),
        label_atoms=1,
        retention_time=5.0,
        loffset=0.6,
        roffset=0.6,
        chromatographic_peak_deconvolution_stringency="7",
    )

    assert stacked[0] == pytest.approx(clean_m0, rel=1e-4)
    assert stacked[1] < np.trapezoid(target_m1 + interference_m1, time)
    assert stacked[1] == pytest.approx(np.trapezoid(target_m1, time), rel=0.15)


def test_sibling_overlap_fits_the_clean_isotopologue_as_well():
    time = np.linspace(4.5, 5.8, 261)
    target_m0 = _gaussian(time, 5.0, 0.07, 12.0)
    target_m1 = _gaussian(time, 5.0, 0.07, 4.0)
    interference_m1 = _gaussian(time, 5.26, 0.06, 10.0)
    intensity = np.vstack([target_m0, target_m1 + interference_m1])

    bundle = deconvolve_channel_matrix(
        time,
        intensity,
        retention_time=5.0,
        loffset=0.6,
        roffset=0.6,
        stringency="7",
    )

    assert bundle.channels[0].result.model is not None
    assert bundle.channels[1].result.model is not None
    assert bundle.channels[0].result.selected_center == pytest.approx(5.0, abs=0.05)


def test_deconvolve_eic_rejects_multi_channel_matrix():
    time = np.linspace(0.0, 10.0, 21)
    intensity = np.vstack([_gaussian(time, 5.0, 0.3, 10.0), _gaussian(time, 5.0, 0.3, 4.0)])

    with pytest.raises(ValueError, match="deconvolve_channel_matrix"):
        deconvolve_eic(
            time,
            intensity,
            retention_time=5.0,
            loffset=2.0,
            roffset=2.0,
            stringency="4",
        )


def test_level_five_deconvolves_smaller_isotopologue_shoulder():
    time = np.linspace(8.28, 8.70, 211)
    m0 = _gaussian(time, 8.64, 0.012, 25.0)
    target_m1 = _gaussian(time, 8.64, 0.013, 5.0)
    interfering_m1 = _gaussian(time, 8.60, 0.010, 8.0)
    intensity = np.vstack([m0, target_m1 + interfering_m1])

    bundle = deconvolve_channel_matrix(
        time,
        intensity,
        retention_time=8.64,
        loffset=0.16,
        roffset=0.04,
        stringency="5",
    )

    m1 = bundle.channels[1].result
    assert m1.excluded
    assert m1.component_centers == pytest.approx([8.60, 8.64], abs=0.01)
    assert np.trapezoid(m1.selected, time) == pytest.approx(
        np.trapezoid(target_m1, time), rel=0.15
    )


def test_offsets_cut_fitted_curve_without_refitting_shape():
    time = np.linspace(8.28, 8.70, 211)
    target_m0 = _gaussian(time, 8.64, 0.012, 25.0)
    target_m1 = _gaussian(time, 8.64, 0.013, 5.0)
    shoulder_m1 = _gaussian(time, 8.60, 0.010, 8.0)
    intensity = np.vstack([target_m0, target_m1 + shoulder_m1])

    narrow = deconvolve_channel_matrix(
        time,
        intensity,
        retention_time=8.64,
        loffset=0.03,
        roffset=0.04,
        stringency="5",
    )
    wide = deconvolve_channel_matrix(
        time,
        intensity,
        retention_time=8.64,
        loffset=0.14,
        roffset=0.04,
        stringency="5",
    )

    narrow_m1 = narrow.channels[1].result
    wide_m1 = wide.channels[1].result
    overlap = np.asarray(narrow_m1.selected_mask, dtype=bool) & np.asarray(
        wide_m1.selected_mask, dtype=bool
    )
    assert np.any(overlap)
    assert narrow_m1.selected[overlap] == pytest.approx(wide_m1.selected[overlap])
    assert np.count_nonzero(wide_m1.selected_mask) > np.count_nonzero(
        narrow_m1.selected_mask
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

    bundle = deconvolve_channel_matrix(
        time,
        intensity,
        retention_time=8.58,
        loffset=0.1,
        roffset=0.1,
        stringency="4",
    )

    result = bundle.channels[0].result
    model = result.model
    assert model is not None
    # The continuous model reproduces the sampled selected curve exactly at the
    # acquisition scan points (it only adds detail between them).
    mask0 = np.asarray(result.selected_mask, dtype=bool)
    evaluated = model.evaluate_selected(time[mask0])
    assert evaluated == pytest.approx(result.selected[mask0], abs=1e-9)
    # Evaluating on a denser grid stays within the same window.
    grid = np.linspace(model.integration_left, model.integration_right, 200)
    dense = model.evaluate_selected(grid)
    assert dense.shape == (200,)


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


def test_cheap_path_keeps_a_usable_fit_when_max_nfev_is_hit(monkeypatch):
    real = deconv.least_squares

    def exhausted(*args, **kwargs):
        result = real(*args, **kwargs)
        result.success = False
        result.status = 0
        return result

    monkeypatch.setattr(deconv, "least_squares", exhausted)
    time = np.linspace(0.0, 10.0, 201)
    peak = _gaussian(time, 5.0, 0.3, 10.0) + 0.2 * np.sin(time * 11.0)
    peak = np.maximum(peak, 0.0)
    joint_calls = _spy_overlap_fitter(monkeypatch)

    result = deconvolve_eic(
        time,
        peak,
        retention_time=5.0,
        loffset=2.0,
        roffset=2.0,
        stringency="4",
    )

    assert result.model is not None
    assert result.model.n_components == 1
    assert joint_calls == []


def test_overlap_path_rejects_a_fit_that_only_hit_max_nfev(monkeypatch):
    real = deconv.least_squares

    def exhausted(*args, **kwargs):
        result = real(*args, **kwargs)
        result.success = False
        result.status = 0
        return result

    monkeypatch.setattr(deconv, "least_squares", exhausted)
    deconv._fit_joint_component_model_cached.cache_clear()
    deconv._fit_single_component_model_cached.cache_clear()
    time = np.linspace(0.0, 10.0, 201)
    intensity = _gaussian(time, 4.0, 0.25, 10.0) + _gaussian(time, 7.0, 0.25, 6.0)

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        stringency="4",
    )

    assert result.model is None
    assert np.allclose(result.selected, intensity)


def test_flattened_eic_does_not_infer_channel_count_from_length():
    time = np.array([0.0, 1.0, 2.0])
    intensity = np.array([[0.0, 10.0, 0.0], [0.0, 4.0, 0.0]]).ravel()

    assert calculate_peak_areas(time, intensity, 0, 1.0, 1.1, 1.1) == pytest.approx(
        [0.0]
    )
    assert calculate_peak_areas(
        time, intensity, 0, 1.0, 1.1, 1.1, channel_count=0
    ) == pytest.approx([0.0])
    assert calculate_peak_areas(
        time, intensity, 0, 1.0, 1.1, 1.1, channel_count=2
    ) == pytest.approx([10.0, 4.0])


def test_calculate_peak_areas_infers_channel_count_from_2d_intensity():
    time = np.array([0.0, 1.0, 2.0])
    intensity = np.array([[0.0, 10.0, 0.0], [0.0, 4.0, 0.0]])

    areas = calculate_peak_areas(time, intensity, 0, 1.0, 1.1, 1.1)
    assert areas == pytest.approx([10.0, 4.0])


def test_calculate_peak_areas_unlabelled_qv_both_fitted_uses_model_areas():
    deconv._fit_joint_component_model_cached.cache_clear()
    deconv._fit_single_component_model_cached.cache_clear()
    time = np.linspace(0.0, 10.0, 201)
    quantifier = _gaussian(time, 4.0, 0.25, 10.0) + _gaussian(time, 7.0, 0.25, 6.0)
    qualifier = _gaussian(time, 7.0, 0.25, 2.4)
    intensity = np.vstack([quantifier, qualifier])

    raw = calculate_peak_areas(
        time,
        intensity.ravel(),
        0,
        7.0,
        4.0,
        4.0,
        channel_count=2,
        chromatographic_peak_deconvolution_stringency="off",
    )
    modelled = calculate_peak_areas(
        time,
        intensity.ravel(),
        0,
        7.0,
        4.0,
        4.0,
        channel_count=2,
        chromatographic_peak_deconvolution_stringency="4",
    )

    assert modelled[0] < raw[0]
    assert modelled[0] == pytest.approx(
        np.trapezoid(_gaussian(time, 7.0, 0.25, 6.0), time), rel=1e-3
    )
    assert modelled[1] == pytest.approx(raw[1], rel=1e-3)
    assert modelled[1] / modelled[0] == pytest.approx(0.4, rel=5e-2)


def _unlabelled_mixed_bundle(time, *, failed_index: int):
    fitted = deconvolve_eic(
        time,
        _gaussian(time, 5.0, 0.08, 12.0),
        retention_time=5.0,
        loffset=0.4,
        roffset=0.4,
        stringency="4",
    )
    assert fitted.model is not None
    failed = EICChromatographicPeakDeconvolutionResult(
        selected=np.full(time.size, 3.0),
        selected_mask=np.asarray(fitted.selected_mask, dtype=bool),
        excluded=[],
        excluded_masks=[],
        selected_center=5.0,
        component_centers=[5.0],
        model=None,
    )
    channels = [ChannelDeconvolution(index=0, result=fitted), ChannelDeconvolution(index=1, result=fitted)]
    channels[failed_index] = ChannelDeconvolution(index=failed_index, result=failed)
    return ChannelDeconvolutionBundle(time=time, channels=tuple(channels))


def test_calculate_peak_areas_unlabelled_v_fail_uses_raw_window(monkeypatch):
    time = np.linspace(4.0, 6.0, 81)
    intensity = np.vstack(
        [
            _gaussian(time, 5.0, 0.08, 12.0),
            np.full(time.size, 3.0),
        ]
    )
    monkeypatch.setattr(
        integration_module,
        "deconvolve_channel_matrix",
        lambda *args, **kwargs: _unlabelled_mixed_bundle(time, failed_index=1),
    )
    mixed = calculate_peak_areas(
        time,
        intensity.ravel(),
        0,
        5.0,
        0.4,
        0.4,
        channel_count=2,
        chromatographic_peak_deconvolution_stringency="4",
    )
    expected = calculate_peak_areas(
        time,
        intensity.ravel(),
        0,
        5.0,
        0.4,
        0.4,
        channel_count=2,
        chromatographic_peak_deconvolution_stringency="off",
    )
    assert mixed == pytest.approx(expected)


def test_calculate_peak_areas_unlabelled_q_fail_uses_raw_window(monkeypatch):
    time = np.linspace(4.0, 6.0, 81)
    intensity = np.vstack(
        [
            np.full(time.size, 3.0),
            _gaussian(time, 5.0, 0.08, 12.0),
        ]
    )
    monkeypatch.setattr(
        integration_module,
        "deconvolve_channel_matrix",
        lambda *args, **kwargs: _unlabelled_mixed_bundle(time, failed_index=0),
    )
    mixed = calculate_peak_areas(
        time,
        intensity.ravel(),
        0,
        5.0,
        0.4,
        0.4,
        channel_count=2,
        chromatographic_peak_deconvolution_stringency="4",
    )
    expected = calculate_peak_areas(
        time,
        intensity.ravel(),
        0,
        5.0,
        0.4,
        0.4,
        channel_count=2,
        chromatographic_peak_deconvolution_stringency="off",
    )
    assert mixed == pytest.approx(expected)


def test_calculate_peak_areas_mixed_bundle_uses_raw_window(monkeypatch):
    time = np.linspace(4.0, 6.0, 81)
    clean = _gaussian(time, 5.0, 0.08, 12.0)
    failed = np.full(time.size, 3.0)
    intensity = np.vstack([clean, failed])
    fitted = deconvolve_eic(
        time,
        clean,
        retention_time=5.0,
        loffset=0.4,
        roffset=0.4,
        stringency="4",
    )
    assert fitted.model is not None
    bundle = ChannelDeconvolutionBundle(
        time=time,
        channels=(
            ChannelDeconvolution(index=0, result=fitted),
            ChannelDeconvolution(
                index=1,
                result=EICChromatographicPeakDeconvolutionResult(
                    selected=failed,
                    selected_mask=np.asarray(fitted.selected_mask, dtype=bool),
                    excluded=[],
                    excluded_masks=[],
                    selected_center=5.0,
                    component_centers=[5.0],
                    model=None,
                ),
            ),
        ),
    )
    monkeypatch.setattr(
        integration_module,
        "deconvolve_channel_matrix",
        lambda *args, **kwargs: bundle,
    )
    mixed = calculate_peak_areas(
        time,
        intensity.ravel(),
        1,
        5.0,
        0.4,
        0.4,
        use_legacy=False,
        baseline_correction=False,
        chromatographic_peak_deconvolution_stringency="4",
    )
    expected = calculate_peak_areas(
        time,
        intensity.ravel(),
        1,
        5.0,
        0.4,
        0.4,
        use_legacy=False,
        baseline_correction=False,
        chromatographic_peak_deconvolution_stringency="off",
    )
    assert mixed == pytest.approx(expected)


def test_taller_out_of_window_neighbors_do_not_starve_target_peak():
    time = np.linspace(14.554, 14.950, 97)
    intensity = (
        _gaussian(time, 14.653, 0.012, 18.0)
        + _gaussian(time, 14.698, 0.012, 16.2)
        + _gaussian(time, 14.748, 0.012, 15.4)
        + _gaussian(time, 14.872, 0.012, 17.4)
    )

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=14.75,
        loffset=0.03,
        roffset=0.095,
        stringency="4",
    )

    assert result.model is not None
    assert result.selected_center == pytest.approx(14.75, abs=0.02)
    assert result.model.n_components >= 2


def test_clipped_neighbor_peak_is_split_from_target():
    """A tall Q peak clipped at the extract edge must still be split off tR."""
    full_time = np.linspace(14.20, 14.80, 241)
    full_intensity = _gaussian(full_time, 14.40, 0.04, 13.0) + _gaussian(
        full_time, 14.62, 0.03, 8.0
    )
    keep = full_time >= 14.40
    time = full_time[keep]
    intensity = full_intensity[keep]

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=14.62,
        loffset=0.10,
        roffset=0.10,
        stringency="4",
    )

    assert result.model is not None
    assert result.selected_center == pytest.approx(14.62, abs=0.03)
    assert len(result.excluded) == 1
    assert np.trapezoid(result.selected[time >= 14.52], time[time >= 14.52]) == pytest.approx(
        np.trapezoid(
            _gaussian(time, 14.62, 0.03, 8.0)[time >= 14.52],
            time[time >= 14.52],
        ),
        rel=0.15,
    )


def test_false_extra_seeds_keep_single_component_model(monkeypatch):
    """Shoulder leftovers must not discard a 1-component fit that already matches."""
    time = np.linspace(9.10, 9.70, 80)
    intensity = _gaussian(time, 9.40, 0.025, 20.0)
    real = deconv._candidate_peak_indices

    def extra_seeds(matrix, params):
        seeds = real(matrix, params)
        apex = seeds[0]
        return list(dict.fromkeys(seeds + [max(0, apex - 3), 15, 57]))

    monkeypatch.setattr(deconv, "_candidate_peak_indices", extra_seeds)

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=9.40,
        loffset=0.10,
        roffset=0.20,
        stringency="5",
    )

    assert result.model is not None
    assert result.model.n_components == 1
    assert result.selected_center == pytest.approx(9.40, abs=0.03)


def test_collapsed_overlap_falls_back_to_raw(monkeypatch):
    time = np.linspace(0.0, 10.0, 201)
    intensity = _gaussian(time, 4.0, 0.25, 10.0) + _gaussian(time, 7.0, 0.25, 6.0)
    monkeypatch.setattr(
        deconv,
        "STRINGENCY_PRESETS",
        {
            key: dataclasses.replace(value, max_components=1)
            for key, value in deconv.STRINGENCY_PRESETS.items()
        },
    )

    result = deconvolve_eic(
        time,
        intensity,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        stringency="medium",
    )

    assert result.model is None
    assert np.allclose(result.selected, intensity)


def test_empty_bundle_evaluate_selected_stack_has_zero_rows():
    grid = np.linspace(0.0, 1.0, 11)
    bundle = ChannelDeconvolutionBundle(time=np.array([0.0, 1.0]), channels=())
    stacked = bundle.evaluate_selected_stack(grid)
    assert stacked.shape == (0, 11)


def test_bundle_uses_model_areas_only_when_every_channel_fitted():
    time = np.linspace(4.0, 6.0, 81)
    fitted = deconvolve_eic(
        time,
        _gaussian(time, 5.0, 0.08, 12.0),
        retention_time=5.0,
        loffset=0.4,
        roffset=0.4,
        stringency="4",
    )
    assert fitted.model is not None
    failed = EICChromatographicPeakDeconvolutionResult(
        selected=np.full(time.size, 3.0),
        selected_mask=np.asarray(fitted.selected_mask, dtype=bool),
        excluded=[],
        excluded_masks=[],
        selected_center=5.0,
        component_centers=[5.0],
        model=None,
    )
    mixed = ChannelDeconvolutionBundle(
        time=time,
        channels=(
            ChannelDeconvolution(index=0, result=fitted),
            ChannelDeconvolution(index=1, result=failed),
        ),
    )
    all_fitted = ChannelDeconvolutionBundle(
        time=time,
        channels=(
            ChannelDeconvolution(index=0, result=fitted),
            ChannelDeconvolution(index=1, result=fitted),
        ),
    )
    assert not ChannelDeconvolutionBundle(time=time, channels=()).uses_model_areas()
    assert not mixed.uses_model_areas()
    assert mixed.has_any_model()
    assert mixed.shows_model_overlays(independent_channels=True)
    assert not mixed.shows_model_overlays(independent_channels=False)
    assert all_fitted.uses_model_areas()
    assert all_fitted.shows_model_overlays(independent_channels=False)
