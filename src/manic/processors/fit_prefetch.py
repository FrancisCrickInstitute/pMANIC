"""Run a render's missing curve fits on worker processes before the GUI needs them.

A render first runs with the fit caches in probe mode, which records the key of
every fit it would compute and skips it. The missing fits then run in parallel
on a pool of spawn workers, and the results seed the caches, so the real render
reads every fit from memory. Workers run the same fit function on the same
bytes, so the fitted models are identical to computing them in the GUI thread.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context

from manic.io.compound_reader import read_compound_with_session
from manic.processors import chromatographic_peak_deconvolution as deconv
from manic.processors.display_deconvolution import plot_display
from manic.processors.eic_processing import get_eics_for_compound

logger = logging.getLogger(__name__)

_FITS = {
    fit.__name__: fit
    for fit in (deconv._fit_single_from_bytes, deconv._fit_joint_from_bytes)
}
_pool: ProcessPoolExecutor | None = None


def _compute(key: tuple) -> tuple[bool, object]:
    name, *args = key
    try:
        return True, _FITS[name](*args)
    except Exception:
        # The GUI thread repeats this fit, so it raises and handles it as before.
        return False, None


def _noop() -> None:
    return None


def start_pool() -> ProcessPoolExecutor:
    """Start the workers early so their imports overlap with other work."""
    global _pool
    if _pool is None:
        workers = min(os.cpu_count() or 1, 8)
        _pool = ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn"))
        for _ in range(workers):
            _pool.submit(_noop)
    return _pool


def prefetch_fits(render: Callable[[], object]) -> None:
    """Compute in parallel every fit ``render`` would compute one at a time."""
    global _pool
    deconv._probe.keys = []
    try:
        render()
    except Exception:
        # The real render meets the same error and reports it.
        return
    finally:
        missing = list(dict.fromkeys(deconv._probe.keys))
        deconv._probe.keys = None
    if len(missing) < 2:
        return
    try:
        results = list(start_pool().map(_compute, missing))
    except Exception:
        # The render computes the fits itself, so a broken pool only costs time.
        logger.warning("Parallel fit prefetch failed; fitting in-process", exc_info=True)
        _pool = None
        return
    deconv._prefetched.update(
        (key, fitted) for key, (ok, fitted) in zip(missing, results) if ok
    )


def prefetch_display_fits(compound_name: str, samples: list[str], *, use_corrected: bool) -> None:
    """Prefetch the fits behind a compound's tile grid.

    Peak verdicts, identity checks, and side charts fit the same windows, so
    they read these fits from the cache too.
    """
    try:
        eics = get_eics_for_compound(compound_name, samples, use_corrected=False)
        compounds = [
            read_compound_with_session(eic.compound_name, eic.sample_name) for eic in eics
        ]
    except Exception:
        # Only a speed-up: the real render meets the same error and reports it.
        return
    prefetch_fits(
        lambda: [
            plot_display(eic.time, eic.intensity, compound, use_corrected=use_corrected)
            for eic, compound in zip(eics, compounds)
        ]
    )


def discard_prefetched() -> None:
    deconv._prefetched.clear()
