from types import SimpleNamespace

import numpy as np
import pytest

from manic.processors.chromatographic_peak_deconvolution import (
    deconvolve_channel_matrix,
    deconvolve_for_display,
)
from manic.processors.display_deconvolution import (
    display_y_max,
    integrated_display_areas,
    plot_display,
)
from manic.processors.integration import calculate_peak_areas, integrate_bundle_areas

FIT = dict(
    retention_time=7.0,
    loffset=4.0,
    roffset=4.0,
    stringency="4",
    fit_type="auto",
    noise_gate="balanced",
)


def _gaussian(time, center, width, height):
    return height * np.exp(-0.5 * ((time - center) / width) ** 2)


def _raw_labelled_pair():
    time = np.linspace(0.0, 10.0, 201)
    m0 = _gaussian(time, 4.0, 0.25, 10.0) + _gaussian(time, 7.0, 0.25, 6.0)
    m1 = _gaussian(time, 4.0, 0.25, 3.0) + _gaussian(time, 7.0, 0.25, 2.0)
    return time, np.vstack([m0, m1])


def _noise_row(time, seed=0):
    rng = np.random.default_rng(seed)
    return np.clip(rng.normal(20.0, 8.0, time.size), 0.0, None)


def _selected_stack(bundle):
    return np.vstack(
        [
            np.asarray(channel.result.selected, dtype=np.float64).reshape(-1)
            for channel in bundle.channels
        ]
    )


def test_nic_preview_keeps_overlay_decision_from_the_raw_fit():
    time, raw = _raw_labelled_pair()
    noisy_m1 = np.vstack([raw[0], _noise_row(time)])

    raw_view = deconvolve_for_display(time, raw, **FIT)
    preview = deconvolve_for_display(
        time, raw, apply_correction=lambda matrix: noisy_m1, **FIT
    )

    assert raw_view.bundle.shows_model_overlays(independent_channels=False)
    assert not deconvolve_channel_matrix(
        time, noisy_m1, **FIT
    ).shows_model_overlays(independent_channels=False)
    assert preview.bundle.shows_model_overlays(independent_channels=False)


def test_nic_preview_keeps_the_same_selected_component():
    time, raw = _raw_labelled_pair()
    noisy_m1 = np.vstack([raw[0], _noise_row(time)])

    raw_view = deconvolve_for_display(time, raw, **FIT)
    preview = deconvolve_for_display(
        time, raw, apply_correction=lambda matrix: noisy_m1, **FIT
    )

    raw_centers = [channel.result.selected_center for channel in raw_view.bundle.channels]
    preview_centers = [
        channel.result.selected_center for channel in preview.bundle.channels
    ]
    assert raw_centers == pytest.approx([7.0, 7.0], abs=0.15)
    assert preview_centers == raw_centers
    for raw_channel, preview_channel in zip(
        raw_view.bundle.channels, preview.bundle.channels
    ):
        assert preview_channel.result.model is not None
        assert np.array_equal(
            np.asarray(preview_channel.result.selected_mask, dtype=bool),
            np.asarray(raw_channel.result.selected_mask, dtype=bool),
        )


def test_nic_preview_heights_are_correction_of_the_raw_selected_component():
    time, raw = _raw_labelled_pair()

    def scale_m1(matrix):
        out = np.asarray(matrix, dtype=np.float64).copy()
        out[1] *= 0.4
        return out

    preview = deconvolve_for_display(time, raw, apply_correction=scale_m1, **FIT)
    expected = scale_m1(_selected_stack(preview.bundle))

    assert preview.bundle.shows_model_overlays(independent_channels=False)
    assert preview.intensity == pytest.approx(expected)


def test_noisy_raw_stays_overlay_off_when_preview_is_on():
    time, raw = _raw_labelled_pair()
    noisy_raw = np.vstack([raw[0], _noise_row(time)])

    def make_both_ions_fittable(matrix):
        return np.vstack(
            [
                _gaussian(time, 7.0, 0.25, 8.0),
                _gaussian(time, 7.0, 0.25, 3.0),
            ]
        )

    raw_view = deconvolve_for_display(time, noisy_raw, **FIT)
    preview = deconvolve_for_display(
        time, noisy_raw, apply_correction=make_both_ions_fittable, **FIT
    )

    assert not raw_view.bundle.shows_model_overlays(independent_channels=False)
    assert not preview.bundle.shows_model_overlays(independent_channels=False)
    assert preview.intensity == pytest.approx(make_both_ions_fittable(noisy_raw))
    assert deconvolve_channel_matrix(
        time, make_both_ions_fittable(noisy_raw), **FIT
    ).shows_model_overlays(independent_channels=False)


def _plot_compound():
    return SimpleNamespace(
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
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


def test_preview_omits_the_raw_underlay():
    time, raw = _raw_labelled_pair()
    compound = _plot_compound()
    raw_view = plot_display(time, raw, compound, use_corrected=False)
    preview = plot_display(time, raw, compound, use_corrected=True)

    assert raw_view.display.bundle.shows_model_overlays(independent_channels=False)
    assert preview.display.bundle.shows_model_overlays(independent_channels=False)
    assert raw_view.includes_raw_underlay
    assert not preview.includes_raw_underlay


def test_y_max_follows_the_displayed_trace_not_the_raw_neighbour():
    time, raw = _raw_labelled_pair()
    preview = deconvolve_for_display(time, raw, apply_correction=lambda matrix: matrix, **FIT)

    assert preview.bundle.shows_model_overlays(independent_channels=False)
    assert display_y_max(raw) == pytest.approx(10.0, abs=0.2)
    assert display_y_max(preview.intensity) < 9.0
    assert display_y_max(preview.intensity) == pytest.approx(6.0, abs=0.3)


def test_preview_areas_do_not_refit_a_corrected_matrix(monkeypatch):
    time, raw = _raw_labelled_pair()
    noisy_m1 = np.vstack([raw[0], _noise_row(time)])

    def scale_m1(matrix):
        out = np.asarray(matrix, dtype=np.float64).copy()
        out[1] *= 0.4
        return out

    monkeypatch.setattr(
        "manic.processors.display_deconvolution.make_time_series_corrector",
        lambda _compound: scale_m1,
    )
    compound = _plot_compound()
    areas = integrated_display_areas(
        time, raw, compound, use_corrected=True
    )
    preview = deconvolve_for_display(time, raw, apply_correction=scale_m1, **FIT)
    _, expected = integrate_bundle_areas(
        time,
        preview.bundle,
        raw,
        correct_time_series=scale_m1,
        baseline_correction=False,
        use_legacy=False,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        label_atoms=1,
        channel_count=2,
    )
    old_path = calculate_peak_areas(
        time,
        noisy_m1.ravel(),
        label_atoms=1,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        channel_count=2,
        baseline_correction=False,
        chromatographic_peak_deconvolution_stringency="4",
        chromatographic_peak_deconvolution_fit_type="auto",
        chromatographic_peak_deconvolution_noise_gate="balanced",
    )

    assert areas == pytest.approx(expected)
    assert areas != pytest.approx(old_path)
