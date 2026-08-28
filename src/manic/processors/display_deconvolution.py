from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from manic.processors.chromatographic_peak_deconvolution import (
    DisplayDeconvolution,
    chromatographic_peak_deconvolution_enabled,
    deconvolve_for_display,
)
from manic.processors.eic_correction_manager import make_time_series_corrector
from manic.processors.integration import calculate_peak_areas, integrate_bundle_areas


@dataclass(frozen=True)
class PlotDisplay:
    display: DisplayDeconvolution | None
    intensity: np.ndarray
    includes_raw_underlay: bool


def deconvolution_for_plot(time, raw_intensity, compound, *, use_corrected: bool):
    if not chromatographic_peak_deconvolution_enabled(
        getattr(compound, "deconvolution_level", "off")
    ):
        return None
    apply_correction = (
        make_time_series_corrector(compound) if use_corrected else None
    )
    return deconvolve_for_display(
        time,
        raw_intensity,
        retention_time=compound.retention_time,
        loffset=compound.loffset,
        roffset=compound.roffset,
        stringency=getattr(compound, "deconvolution_level", "off"),
        fit_type=getattr(compound, "deconvolution_fit_type", "auto"),
        noise_gate=getattr(compound, "deconvolution_noise_gate", "balanced"),
        apply_correction=apply_correction,
        independent_channels=getattr(compound, "is_unlabelled_target", False),
    )


def display_intensity_for_plot(raw_intensity, compound, display, *, use_corrected: bool):
    if display is not None:
        return display.intensity
    if use_corrected:
        apply_correction = make_time_series_corrector(compound)
        if apply_correction is not None and np.asarray(raw_intensity).ndim > 1:
            return apply_correction(raw_intensity)
    return raw_intensity


def plot_display(time, raw_intensity, compound, *, use_corrected: bool) -> PlotDisplay:
    display = deconvolution_for_plot(
        time, raw_intensity, compound, use_corrected=use_corrected
    )
    intensity = display_intensity_for_plot(
        raw_intensity, compound, display, use_corrected=use_corrected
    )
    overlays = False
    if display is not None:
        overlays = display.bundle.shows_model_overlays(
            independent_channels=getattr(compound, "is_unlabelled_target", False)
        )
    return PlotDisplay(
        display=display,
        intensity=np.asarray(intensity, dtype=np.float64),
        includes_raw_underlay=bool(overlays and not use_corrected),
    )


def display_y_max(intensity) -> float:
    arr = np.asarray(intensity, dtype=np.float64)
    if arr.size == 0:
        return 0.0
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return 0.0
    return float(np.max(finite))


def integrated_display_areas(
    time,
    raw_intensity,
    compound,
    *,
    use_corrected: bool,
    use_legacy: bool = False,
) -> list[float]:
    raw = np.asarray(raw_intensity, dtype=np.float64)
    if raw.ndim > 1:
        channel_count = int(raw.shape[0])
        label_atoms = channel_count - 1
    else:
        channel_count = 1
        label_atoms = 0

    common = dict(
        retention_time=compound.retention_time,
        loffset=compound.loffset,
        roffset=compound.roffset,
        channel_count=channel_count,
        use_legacy=use_legacy,
        baseline_correction=bool(getattr(compound, "baseline_correction", 0)),
        chromatographic_peak_deconvolution_fit_type=getattr(
            compound, "deconvolution_fit_type", "auto"
        ),
        chromatographic_peak_deconvolution_noise_gate=getattr(
            compound, "deconvolution_noise_gate", "balanced"
        ),
    )
    prepared = plot_display(time, raw, compound, use_corrected=use_corrected)
    if prepared.display is not None:
        apply_correction = make_time_series_corrector(compound)
        _raw_areas, corrected_areas = integrate_bundle_areas(
            time,
            prepared.display.bundle,
            raw,
            correct_time_series=apply_correction,
            baseline_correction=bool(getattr(compound, "baseline_correction", 0)),
            use_legacy=use_legacy,
            retention_time=compound.retention_time,
            loffset=compound.loffset,
            roffset=compound.roffset,
            label_atoms=label_atoms,
            channel_count=channel_count,
        )
        if use_corrected and apply_correction is not None:
            return corrected_areas
        return _raw_areas
    if use_corrected and make_time_series_corrector(compound) is not None:
        return calculate_peak_areas(
            time,
            np.asarray(prepared.intensity, dtype=np.float64).ravel(),
            label_atoms,
            chromatographic_peak_deconvolution_stringency="off",
            **common,
        )
    return calculate_peak_areas(
        time,
        raw.ravel(),
        label_atoms,
        chromatographic_peak_deconvolution_stringency=getattr(
            compound, "deconvolution_level", "off"
        ),
        **common,
    )
