"""Parity, fallback, and FFI safety tests for the Rust peak-fitting backend (#322)."""

from __future__ import annotations

import os
from types import SimpleNamespace

import numpy as np
import pytest

from manic.processors import chromatographic_peak_deconvolution as deconv
from manic.processors import rust_fitter


def _clear_caches() -> None:
    deconv._fit_single_component_model_cached.cache_clear()
    deconv._fit_joint_component_model_cached.cache_clear()


@pytest.mark.parametrize("shape_model", ["gaussian", "bi_gaussian", "emg"])
@pytest.mark.parametrize("channels", [1, 2])
def test_rust_and_scipy_fit_shape_candidate_match(shape_model, channels, monkeypatch):
    if not rust_fitter.is_available():
        pytest.skip("Rust peak-fitter library not built")

    pts = 91
    x_rel = np.linspace(0.0, 0.9, pts, dtype=np.float64)
    p1 = 1000.0 * np.exp(-0.5 * ((x_rel - 0.36) / 0.04) ** 2)
    p2 = 600.0 * np.exp(-0.5 * ((x_rel - 0.52) / 0.05) ** 2)
    if channels == 1:
        y = (15.0 + p1 + p2).reshape(1, -1)
    else:
        y = np.vstack([15.0 + p1 + p2, 8.0 + 0.4 * p1 + 0.25 * p2])
    params = deconv.STRINGENCY_PRESETS["7"]

    # Check solver status and raw parameter vector directly on the well-conditioned problem.
    channel_scale = np.maximum(
        np.percentile(y, 95, axis=1) - np.percentile(y, 10, axis=1),
        max(float(y.max()) * 1e-6, np.finfo(float).eps),
    )
    initial, lower, upper = [], [], []
    for c in (0.35, 0.53):
        initial.extend(deconv._initial_shape_params(shape_model, c, 0.045))
        lo, hi = deconv._shape_param_bounds(shape_model, x_rel, 0.01, 0.25)
        lower.extend(lo)
        upper.extend(hi)
    rust_raw = rust_fitter.fit_shape_candidate_rust(
        x_rel,
        y,
        channel_scale,
        shape_model,
        np.array(initial),
        np.array(lower),
        np.array(upper),
        2,
        params.max_nfev,
    )
    assert rust_raw is not None
    rust_x, rust_status = rust_raw
    assert rust_status > 0

    rust_fit = deconv._fit_shape_candidate(
        x_rel, y, [0.35, 0.53], shape_model, 0.01, 0.25, 0.045, float(y.max()), params
    )
    assert rust_fit is not None

    monkeypatch.setattr(rust_fitter, "is_available", lambda: False)
    scipy_fit = deconv._fit_shape_candidate(
        x_rel, y, [0.35, 0.53], shape_model, 0.01, 0.25, 0.045, float(y.max()), params
    )
    assert scipy_fit is not None

    np.testing.assert_allclose(rust_fit.shape_params, scipy_fit.shape_params, rtol=1e-6, atol=1e-7)
    np.testing.assert_allclose(rust_fit.centers, scipy_fit.centers, rtol=1e-7, atol=1e-8)
    np.testing.assert_allclose(rust_fit.components, scipy_fit.components, rtol=1e-5, atol=1e-4)
    assert rust_fit.bic == pytest.approx(scipy_fit.bic, rel=1e-6, abs=1e-5)


@pytest.mark.parametrize("level", ["4", "7"])
def test_rust_and_scipy_deconvolve_eic_match_on_overlapping_emg(level, monkeypatch):
    if not rust_fitter.is_available():
        pytest.skip("Rust peak-fitter library not built")

    time = np.linspace(4.5, 5.5, 121, dtype=np.float64)
    from scipy.special import erfcx

    def emg(t, mu, sigma, tau):
        u = (t - mu) / sigma
        z = (sigma / tau - u) / np.sqrt(2.0)
        raw = np.exp(-0.5 * u**2) * erfcx(np.maximum(z, 0.0))
        return raw / np.max(raw)

    trace = 20.0 + 1200.0 * emg(time, 4.98, 0.025, 0.04) + 500.0 * np.exp(
        -0.5 * ((time - 5.14) / 0.03) ** 2
    )

    _clear_caches()
    rust_res = deconv.deconvolve_eic(
        time, trace, retention_time=5.0, loffset=0.2, roffset=0.2, stringency=level
    )

    _clear_caches()
    monkeypatch.setattr(rust_fitter, "is_available", lambda: False)
    scipy_res = deconv.deconvolve_eic(
        time, trace, retention_time=5.0, loffset=0.2, roffset=0.2, stringency=level
    )

    assert rust_res.model is not None and scipy_res.model is not None
    assert rust_res.model.shape_model == scipy_res.model.shape_model
    assert rust_res.model.n_components == scipy_res.model.n_components
    rust_area = float(np.trapezoid(rust_res.selected, time))
    scipy_area = float(np.trapezoid(scipy_res.selected, time))
    assert rust_area == pytest.approx(scipy_area, rel=1e-6)


def test_rust_fitter_returns_status_zero_when_max_nfev_exhausted():
    if not rust_fitter.is_available():
        pytest.skip("Rust peak-fitter library not built")

    x_rel = np.linspace(0.0, 1.0, 81, dtype=np.float64)
    y = (1000.0 * np.exp(-0.5 * ((x_rel - 0.5) / 0.04) ** 2)).reshape(1, -1)
    out = rust_fitter.fit_shape_candidate_rust(
        x_rel,
        y,
        np.array([950.0]),
        "gaussian",
        np.array([0.35, 0.09]),
        np.array([0.0, 0.01]),
        np.array([1.0, 0.3]),
        component_count=1,
        max_nfev=1,
    )
    assert out is not None
    _x, status = out
    assert status == 0


def test_rust_fitter_rejects_invalid_inputs_and_validates_ffi_lengths():
    if not rust_fitter.is_available():
        pytest.skip("Rust peak-fitter library not built")

    x_rel = np.linspace(0.0, 1.0, 21, dtype=np.float64)
    y = np.ones((1, 21), dtype=np.float64)
    scale = np.array([1.0])

    # Unknown shape model returns None.
    assert (
        rust_fitter.fit_shape_candidate_rust(
            x_rel, y, scale, "unknown", np.array([0.5, 0.1]), np.array([0.0, 0.01]), np.array([1.0, 0.3]), 1, 10
        )
        is None
    )
    # Inverted bounds (lower >= upper) return None.
    assert (
        rust_fitter.fit_shape_candidate_rust(
            x_rel, y, scale, "gaussian", np.array([0.5, 0.1]), np.array([1.0, 0.01]), np.array([0.5, 0.3]), 1, 10
        )
        is None
    )
    # Non-finite initial value returns None.
    assert (
        rust_fitter.fit_shape_candidate_rust(
            x_rel, y, scale, "gaussian", np.array([np.nan, 0.1]), np.array([0.0, 0.01]), np.array([1.0, 0.3]), 1, 10
        )
        is None
    )
    # Shape mismatches raise RustFitterError before crossing the C ABI boundary.
    with pytest.raises(rust_fitter.RustFitterError, match="x_rel"):
        rust_fitter.fit_shape_candidate_rust(
            x_rel[:-1], y, scale, "gaussian", np.array([0.5, 0.1]), np.array([0.0, 0.01]), np.array([1.0, 0.3]), 1, 10
        )
    with pytest.raises(rust_fitter.RustFitterError, match="channel_scale"):
        rust_fitter.fit_shape_candidate_rust(
            x_rel, y, np.array([1.0, 2.0]), "gaussian", np.array([0.5, 0.1]), np.array([0.0, 0.01]), np.array([1.0, 0.3]), 1, 10
        )
    with pytest.raises(rust_fitter.RustFitterError, match="initial/lower/upper"):
        rust_fitter.fit_shape_candidate_rust(
            x_rel, y, scale, "gaussian", np.array([0.5]), np.array([0.0]), np.array([1.0]), 1, 10
        )
    with pytest.raises(rust_fitter.RustFitterError, match="max_nfev"):
        rust_fitter.fit_shape_candidate_rust(
            x_rel, y, scale, "gaussian", np.array([0.5, 0.1]), np.array([0.0, 0.01]), np.array([1.0, 0.3]), 1, 0
        )


@pytest.mark.parametrize("level", ["4", "7"])
def test_rust_panic_propagates_through_deconvolve_eic(level, monkeypatch):
    fake_lib = SimpleNamespace(manic_fit_shape_candidate=lambda *_args: -1)
    monkeypatch.setattr(rust_fitter, "_load_library", lambda: fake_lib)
    _clear_caches()

    time = np.linspace(4.5, 5.5, 81, dtype=np.float64)
    peak = 1000.0 * np.exp(-0.5 * ((time - 5.0) / 0.04) ** 2)
    with pytest.raises(rust_fitter.RustFitterError, match="panicked"):
        deconv.deconvolve_eic(
            time, peak, retention_time=5.0, loffset=0.2, roffset=0.2, stringency=level
        )


def test_candidate_paths_prefers_newer_mtime(tmp_path, monkeypatch):
    pkg_dir = tmp_path / "src" / "manic" / "processors"
    cargo_dir = tmp_path / "rust" / "manic_fitter" / "target" / "release"
    pkg_dir.mkdir(parents=True)
    cargo_dir.mkdir(parents=True)

    lib_name = rust_fitter._library_filename()
    stale = pkg_dir / lib_name
    fresh = cargo_dir / lib_name
    stale.write_bytes(b"old")
    fresh.write_bytes(b"new")
    os.utime(stale, (1000, 1000))
    os.utime(fresh, (2000, 2000))

    monkeypatch.setattr(rust_fitter, "__file__", str(pkg_dir / "rust_fitter.py"))
    assert rust_fitter._candidate_paths()[0] == fresh


def test_frozen_load_failure_raises_rust_fitter_error(tmp_path, monkeypatch):
    fake_lib = tmp_path / rust_fitter._library_filename()
    fake_lib.write_bytes(b"not a real shared library")
    monkeypatch.setattr(rust_fitter, "_candidate_paths", lambda: [fake_lib])
    monkeypatch.setattr(rust_fitter.sys, "frozen", True, raising=False)
    rust_fitter.reset_loader()
    try:
        with pytest.raises(rust_fitter.RustFitterError, match="failed to load"):
            rust_fitter.is_available()
    finally:
        rust_fitter.reset_loader()


def test_missing_symbol_falls_back_in_dev_and_raises_when_frozen(tmp_path, monkeypatch):
    fake_lib = tmp_path / rust_fitter._library_filename()
    fake_lib.write_bytes(b"placeholder")
    monkeypatch.setattr(rust_fitter, "_candidate_paths", lambda: [fake_lib])
    monkeypatch.setattr(rust_fitter.ctypes, "CDLL", lambda _path: SimpleNamespace())

    rust_fitter.reset_loader()
    try:
        assert not rust_fitter.is_available()
        monkeypatch.setattr(rust_fitter.sys, "frozen", True, raising=False)
        rust_fitter.reset_loader()
        with pytest.raises(rust_fitter.RustFitterError, match="failed to load"):
            rust_fitter.is_available()
    finally:
        rust_fitter.reset_loader()


def test_export_changelog_records_active_peak_fitter_backend(tmp_path, monkeypatch):
    from manic.io.changelog_writer import generate_changelog

    export_a = tmp_path / "run_a" / "out.xlsx"
    export_a.parent.mkdir()
    generate_changelog(
        str(export_a),
        internal_standard=None,
        use_legacy_integration=False,
        mass_tolerance=0.2,
        min_peak_area_ratio=0.05,
    )
    text_a = next(export_a.parent.glob("changelog_*.md")).read_text(encoding="utf-8")
    expected_a = "Rust" if rust_fitter.is_available() else "SciPy"
    assert f"- **Peak Fitter Backend:** {expected_a}" in text_a

    monkeypatch.setenv("MANIC_DISABLE_RUST_FITTER", "1")
    rust_fitter.reset_loader()
    try:
        export_b = tmp_path / "run_b" / "out.xlsx"
        export_b.parent.mkdir()
        generate_changelog(
            str(export_b),
            internal_standard=None,
            use_legacy_integration=False,
            mass_tolerance=0.2,
            min_peak_area_ratio=0.05,
        )
        text_b = next(export_b.parent.glob("changelog_*.md")).read_text(encoding="utf-8")
        assert "- **Peak Fitter Backend:** SciPy" in text_b
    finally:
        monkeypatch.delenv("MANIC_DISABLE_RUST_FITTER", raising=False)
        rust_fitter.reset_loader()


def test_missing_library_raises_in_frozen_build(monkeypatch):
    monkeypatch.setattr(rust_fitter, "_candidate_paths", lambda: [])
    monkeypatch.setattr(rust_fitter.sys, "frozen", True, raising=False)
    rust_fitter.reset_loader()
    try:
        with pytest.raises(rust_fitter.RustFitterError, match="missing"):
            rust_fitter.is_available()
        time = np.linspace(0.0, 1.0, 61, dtype=np.float64)
        peak = 500.0 * np.exp(-0.5 * ((time - 0.5) / 0.04) ** 2)
        _clear_caches()
        with pytest.raises(rust_fitter.RustFitterError, match="missing"):
            deconv.deconvolve_eic(
                time, peak, retention_time=0.5, loffset=0.2, roffset=0.2, stringency="4"
            )
        monkeypatch.setenv("MANIC_DISABLE_RUST_FITTER", "1")
        rust_fitter.reset_loader()
        assert not rust_fitter.is_available()
        assert rust_fitter.backend_name() == "SciPy"
    finally:
        monkeypatch.delenv("MANIC_DISABLE_RUST_FITTER", raising=False)
        rust_fitter.reset_loader()


def test_env_flag_forces_scipy_fallback(monkeypatch):
    monkeypatch.setenv("MANIC_DISABLE_RUST_FITTER", "1")
    rust_fitter.reset_loader()
    try:
        assert not rust_fitter.is_available()
        time = np.linspace(0.0, 1.0, 61, dtype=np.float64)
        peak = 500.0 * np.exp(-0.5 * ((time - 0.5) / 0.04) ** 2)
        _clear_caches()
        res = deconv.deconvolve_eic(
            time, peak, retention_time=0.5, loffset=0.2, roffset=0.2, stringency="4"
        )
        assert res.model is not None
    finally:
        monkeypatch.delenv("MANIC_DISABLE_RUST_FITTER", raising=False)
        rust_fitter.reset_loader()
