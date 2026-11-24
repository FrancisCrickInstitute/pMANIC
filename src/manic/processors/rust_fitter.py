"""Optional Rust backend for the inner chromatographic peak-shape TRF solver.

Loads the compiled ``manic_fitter`` shared library via ``ctypes`` when present
and falls back cleanly to SciPy's ``least_squares`` otherwise. Set
``MANIC_DISABLE_RUST_FITTER=1`` to force the Python/SciPy solver.
"""

from __future__ import annotations

import ctypes
import functools
import logging
import os
import sys
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class RustFitterError(RuntimeError):
    """Raised when the Rust peak-fitting backend fails an internal invariant or panics."""


_SHAPE_SPEC = {
    "gaussian": (0, 2),
    "bi_gaussian": (1, 3),
    "emg": (2, 3),
}


def _library_filename() -> str:
    if sys.platform == "darwin":
        return "libmanic_fitter.dylib"
    if sys.platform == "win32":
        return "manic_fitter.dll"
    return "libmanic_fitter.so"


def _candidate_paths() -> list[Path]:
    filename = _library_filename()
    here = Path(__file__).resolve().parent
    candidates = [here / filename]
    # Dev checkout: pick whichever of the installed copy or fresh cargo release
    # build is newer so a stale gitignored binary never shadows a rebuild.
    repo_root = here.parent.parent.parent
    cargo_release = repo_root / "rust" / "manic_fitter" / "target" / "release" / filename
    if cargo_release not in candidates:
        candidates.append(cargo_release)
    existing = [p for p in candidates if p.is_file()]
    existing.sort(key=lambda p: p.stat().st_mtime_ns, reverse=True)
    return existing


@functools.cache
def _load_library():
    if os.environ.get("MANIC_DISABLE_RUST_FITTER") == "1":
        logger.info("Peak fitter backend: SciPy (MANIC_DISABLE_RUST_FITTER=1)")
        return None
    for path in _candidate_paths():
        try:
            lib = ctypes.CDLL(str(path))
            fn = lib.manic_fit_shape_candidate
            fn.argtypes = [
                ctypes.POINTER(ctypes.c_double),  # x_rel
                ctypes.c_size_t,  # points
                ctypes.POINTER(ctypes.c_double),  # y
                ctypes.c_size_t,  # channels
                ctypes.POINTER(ctypes.c_double),  # channel_scale
                ctypes.c_int,  # shape_model_code
                ctypes.POINTER(ctypes.c_double),  # initial
                ctypes.POINTER(ctypes.c_double),  # lower
                ctypes.POINTER(ctypes.c_double),  # upper
                ctypes.c_size_t,  # component_count
                ctypes.c_size_t,  # max_nfev
                ctypes.POINTER(ctypes.c_double),  # out_x
                ctypes.POINTER(ctypes.c_int),  # out_status
            ]
            fn.restype = ctypes.c_int
            logger.info("Peak fitter backend: Rust (%s)", path)
            return lib
        except (OSError, AttributeError) as exc:
            if getattr(sys, "frozen", False):
                raise RustFitterError(
                    f"Bundled Rust peak fitter failed to load from {path}: {exc}"
                ) from exc
            logger.warning("Could not load Rust peak fitter from %s", path, exc_info=True)
    logger.info("Peak fitter backend: SciPy (Rust library not present)")
    return None


def reset_loader() -> None:
    """Clear cached library handle (used by tests toggling the backend)."""
    _load_library.cache_clear()


def is_available() -> bool:
    return _load_library() is not None


def backend_name() -> str:
    """Human-readable name of the active peak-fitting backend for logs and changelogs."""
    return "Rust" if is_available() else "SciPy"


def fit_shape_candidate_rust(
    x_rel: np.ndarray,
    y: np.ndarray,
    channel_scale: np.ndarray,
    shape_model: str,
    initial: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    component_count: int,
    max_nfev: int,
) -> tuple[np.ndarray, int] | None:
    """Run the Rust TRF solver; returns ``(x, status)`` or ``None`` on failure."""
    lib = _load_library()
    if lib is None:
        return None
    spec = _SHAPE_SPEC.get(shape_model)
    if spec is None:
        return None
    shape_code, param_count = spec

    x_arr = np.ascontiguousarray(x_rel, dtype=np.float64)
    y_arr = np.ascontiguousarray(y, dtype=np.float64)
    scale_arr = np.ascontiguousarray(channel_scale, dtype=np.float64)
    init_arr = np.ascontiguousarray(initial, dtype=np.float64)
    lower_arr = np.ascontiguousarray(lower, dtype=np.float64)
    upper_arr = np.ascontiguousarray(upper, dtype=np.float64)

    if y_arr.ndim != 2:
        raise RustFitterError(
            f"y must be 2-D (channels, points), got shape {y_arr.shape}"
        )
    channels, points = y_arr.shape
    if x_arr.ndim != 1 or x_arr.size != points:
        raise RustFitterError(
            f"x_rel must be 1-D of length {points}, got shape {x_arr.shape}"
        )
    if scale_arr.ndim != 1 or scale_arr.size != channels:
        raise RustFitterError(
            f"channel_scale must be 1-D of length {channels}, got shape {scale_arr.shape}"
        )
    if max_nfev <= 0:
        raise RustFitterError(f"max_nfev must be positive, got {max_nfev}")
    expected_n = component_count * param_count
    if (
        init_arr.ndim != 1
        or init_arr.size != expected_n
        or lower_arr.shape != init_arr.shape
        or upper_arr.shape != init_arr.shape
    ):
        raise RustFitterError(
            f"initial/lower/upper must be 1-D of length {expected_n}, "
            f"got {init_arr.shape}, {lower_arr.shape}, {upper_arr.shape}"
        )

    out_x = np.empty(expected_n, dtype=np.float64)
    out_status = ctypes.c_int(-1)

    c_dbl_p = ctypes.POINTER(ctypes.c_double)
    ok = lib.manic_fit_shape_candidate(
        x_arr.ctypes.data_as(c_dbl_p),
        points,
        y_arr.ctypes.data_as(c_dbl_p),
        channels,
        scale_arr.ctypes.data_as(c_dbl_p),
        shape_code,
        init_arr.ctypes.data_as(c_dbl_p),
        lower_arr.ctypes.data_as(c_dbl_p),
        upper_arr.ctypes.data_as(c_dbl_p),
        component_count,
        max_nfev,
        out_x.ctypes.data_as(c_dbl_p),
        ctypes.byref(out_status),
    )
    if ok == -1:
        raise RustFitterError("Rust peak fitter panicked inside manic_fit_shape_candidate")
    if ok != 1:
        return None
    return out_x, int(out_status.value)
