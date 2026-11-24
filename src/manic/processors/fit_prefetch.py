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
import threading
from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor
from multiprocessing import get_context, parent_process

from manic.io.compound_reader import read_compound_with_session, read_compounds_with_session
from manic.processors import chromatographic_peak_deconvolution as deconv
from manic.processors.display_deconvolution import plot_display
from manic.processors.eic_processing import get_eics_for_compound

logger = logging.getLogger(__name__)

_FITS = {
    fit.__name__: fit
    for fit in (deconv._fit_single_from_bytes, deconv._fit_joint_from_bytes)
}
_CACHED_FITS = {
    deconv._fit_single_from_bytes.__name__: deconv._fit_single_component_model_cached,
    deconv._fit_joint_from_bytes.__name__: deconv._fit_joint_component_model_cached,
}
_pool: ProcessPoolExecutor | None = None
_pool_lock = threading.Lock()
_bg_lock = threading.Lock()
_bg_futures: dict[tuple, Future] = {}


def _compute(key: tuple) -> tuple[bool, object]:
    name, *args = key
    try:
        return True, _FITS[name](*args)
    except Exception:
        # The GUI thread repeats this fit, so it raises and handles it as before.
        return False, None


def _noop() -> None:
    return None


def _exit_with_parent() -> None:
    """Runs in each worker: a crashed or force-quit app must not leave its workers behind."""

    def wait() -> None:
        parent_process().join()
        os._exit(0)

    threading.Thread(target=wait, daemon=True).start()


def pool_worker_count() -> int:
    return min(os.cpu_count() or 1, 8)


def start_pool() -> ProcessPoolExecutor:
    """Start the workers early so their imports overlap with other work."""
    global _pool
    with _pool_lock:
        if _pool is None:
            workers = pool_worker_count()
            _pool = ProcessPoolExecutor(
                max_workers=workers,
                mp_context=get_context("spawn"),
                initializer=_exit_with_parent,
            )
            for _ in range(workers):
                _pool.submit(_noop)
        return _pool


def reset_pool(broken_pool: ProcessPoolExecutor) -> None:
    """Drop a broken shared pool so the next caller starts a fresh one."""
    global _pool
    with _pool_lock:
        if _pool is broken_pool:
            _pool = None


def _seed_lru_from_result(key: tuple, ok: bool, fitted: object) -> None:
    if not ok:
        return
    name, *args = key
    cached_fn = _CACHED_FITS.get(name)
    if cached_fn is None:
        return
    deconv._local_prefetched.entry = (key, fitted)
    try:
        cached_fn(*args)
    finally:
        deconv._local_prefetched.entry = None


def _on_bg_done(key: tuple, future: Future) -> None:
    try:
        if not future.cancelled():
            ok, fitted = future.result()
            _seed_lru_from_result(key, ok, fitted)
    except Exception:
        pass
    finally:
        with _bg_lock:
            if _bg_futures.get(key) is future:
                _bg_futures.pop(key, None)


def cancel_background_prefetch(keep_keys: set[tuple] | None = None) -> None:
    """Cancel pending look-ahead fits not needed by ``keep_keys``."""
    with _bg_lock:
        to_cancel = [
            (key, future)
            for key, future in _bg_futures.items()
            if keep_keys is None or key not in keep_keys
        ]
    # Call future.cancel() outside _bg_lock: cancelling invokes done callbacks
    # synchronously on this thread, and _on_bg_done acquires _bg_lock.
    for key, future in to_cancel:
        if future.cancel():
            with _bg_lock:
                if _bg_futures.get(key) is future:
                    _bg_futures.pop(key, None)


def _probe_missing_keys(render: Callable[[], object]) -> list[tuple]:
    deconv._probe.keys = []
    try:
        render()
    except Exception:
        return []
    finally:
        missing = list(dict.fromkeys(deconv._probe.keys))
        deconv._probe.keys = None
    return missing


def prefetch_fits(render: Callable[[], object]) -> None:
    """Compute in parallel every fit ``render`` would compute one at a time."""
    missing = _probe_missing_keys(render)
    if not missing:
        return

    needed = set(missing)
    cancel_background_prefetch(keep_keys=needed)

    inflight: dict[tuple, Future] = {}
    to_submit: list[tuple] = []
    with _bg_lock:
        for key in missing:
            fut = _bg_futures.get(key)
            if fut is not None and not fut.cancelled():
                inflight[key] = fut
            else:
                to_submit.append(key)

    if len(to_submit) < 2 and not inflight:
        return

    pool = None
    computed: dict[tuple, tuple[bool, object]] = {}
    if to_submit:
        try:
            pool = start_pool()
            workers = pool_worker_count()
            chunksize = max(1, min(16, len(to_submit) // max(1, workers * 2)))
            results = list(pool.map(_compute, to_submit, chunksize=chunksize))
            for key, res in zip(to_submit, results):
                computed[key] = res
        except Exception:
            # The render computes the fits itself, so a broken pool only costs time.
            logger.warning("Parallel fit prefetch failed; fitting in-process", exc_info=True)
            if pool is not None:
                reset_pool(pool)
            return

    for key, fut in inflight.items():
        try:
            computed[key] = fut.result()
        except Exception:
            pass

    with deconv._prefetched_lock:
        for key, (ok, fitted) in computed.items():
            if ok:
                deconv._prefetched[key] = fitted


def prefetch_display_fits(
    compound_name: str,
    samples: list[str],
    *,
    use_corrected: bool,
    eics=None,
) -> None:
    """Prefetch the fits behind a compound's tile grid.

    Peak verdicts, identity checks, and side charts fit the same windows, so
    they read these fits from the cache too.
    """
    try:
        if eics is None:
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


def prefetch_display_fits_async(
    compound_name: str,
    samples: list[str],
    *,
    use_corrected: bool,
) -> None:
    """Queue missing fits for an upcoming compound on the shared worker pool."""
    if not compound_name or not samples:
        return
    try:
        eics = get_eics_for_compound(compound_name, samples, use_corrected=False)
        compounds_by_sample = read_compounds_with_session(
            compound_name, [eic.sample_name for eic in eics]
        )
        pairs = [
            (eic, compounds_by_sample[eic.sample_name])
            for eic in eics
            if eic.sample_name in compounds_by_sample
        ]
    except Exception:
        return
    missing = _probe_missing_keys(
        lambda: [
            plot_display(eic.time, eic.intensity, compound, use_corrected=use_corrected)
            for eic, compound in pairs
        ]
    )
    if len(missing) < 2:
        return
    pool = None
    submitted: list[tuple[tuple, Future]] = []
    try:
        pool = start_pool()
        with _bg_lock:
            for key in missing:
                if key in _bg_futures:
                    continue
                fut = pool.submit(_compute, key)
                _bg_futures[key] = fut
                submitted.append((key, fut))
    except Exception:
        logger.debug("Background look-ahead fit prefetch failed", exc_info=True)
        if pool is not None:
            reset_pool(pool)
    finally:
        # Attach callbacks outside _bg_lock even after a partial submit failure
        # so completed futures always leave _bg_futures.
        for key, fut in submitted:
            fut.add_done_callback(lambda f, k=key: _on_bg_done(k, f))


def discard_prefetched() -> None:
    with deconv._prefetched_lock:
        deconv._prefetched.clear()
