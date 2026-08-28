from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from manic.processors.chromatographic_peak_deconvolution import (
    ChannelDeconvolutionBundle,
    DEFAULT_NOISE_GATE,
    _as_trace_matrix,
    _restore_shape,
    chromatographic_peak_deconvolution_enabled,
    deconvolve_channel_matrix,
)
from manic.processors.eic_correction_manager import make_time_series_corrector
from manic.processors.integration import calculate_peak_areas, integrate_bundle_areas


@dataclass(frozen=True)
class DisplayDeconvolution:
    bundle: ChannelDeconvolutionBundle
    intensity: np.ndarray


def deconvolve_for_display(
    time_data: np.ndarray,
    raw_intensity: np.ndarray,
    *,
    retention_time: float | None,
    loffset: float | None = None,
    roffset: float | None = None,
    stringency: str | None = "off",
    fit_type: str | None = "auto",
    noise_gate: str | None = DEFAULT_NOISE_GATE,
    apply_correction=None,
    independent_channels: bool = False,
) -> DisplayDeconvolution:
    raw = np.asarray(raw_intensity, dtype=np.float64)
    bundle = deconvolve_channel_matrix(
        time_data,
        raw,
        retention_time=retention_time,
        loffset=loffset,
        roffset=roffset,
        stringency=stringency,
        fit_type=fit_type,
        noise_gate=noise_gate,
    )
    if apply_correction is None:
        return DisplayDeconvolution(bundle=bundle, intensity=raw)

    matrix, was_1d = _as_trace_matrix(raw)
    if bundle.shows_model_overlays(independent_channels=independent_channels):
        source = bundle.selected_scan_stack()
    else:
        source = bundle.scan_stack(matrix)
    corrected = np.asarray(apply_correction(source), dtype=np.float64)
    return DisplayDeconvolution(
        bundle=bundle,
        intensity=_restore_shape(corrected, was_1d),
    )


@dataclass(frozen=True)
class PlotDisplay:
    display: DisplayDeconvolution | None
    intensity: np.ndarray
    includes_raw_underlay: bool

    def baseline_intensity(self) -> np.ndarray:
        if self.display is not None and self.includes_raw_underlay:
            return self.display.bundle.selected_scan_stack()
        return self.intensity


def plot_display(time, raw_intensity, compound, *, use_corrected: bool) -> PlotDisplay:
    raw = np.asarray(raw_intensity, dtype=np.float64)
    apply_correction = (
        make_time_series_corrector(compound)
        if use_corrected and raw.ndim > 1
        else None
    )
    display = None
    if chromatographic_peak_deconvolution_enabled(
        getattr(compound, "deconvolution_level", "off")
    ):
        display = deconvolve_for_display(
            time,
            raw,
            retention_time=compound.retention_time,
            loffset=compound.loffset,
            roffset=compound.roffset,
            stringency=getattr(compound, "deconvolution_level", "off"),
            fit_type=getattr(compound, "deconvolution_fit_type", "auto"),
            noise_gate=getattr(compound, "deconvolution_noise_gate", "balanced"),
            apply_correction=apply_correction,
            independent_channels=getattr(compound, "is_unlabelled_target", False),
        )

    intensity = display.intensity if display is not None else raw
    if display is None and apply_correction is not None:
        intensity = apply_correction(raw)

    overlays = False
    if display is not None:
        overlays = display.bundle.shows_model_overlays(
            independent_channels=getattr(compound, "is_unlabelled_target", False)
        )
    return PlotDisplay(
        display=display,
        intensity=np.asarray(intensity, dtype=np.float64),
        includes_raw_underlay=bool(overlays and apply_correction is None),
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
