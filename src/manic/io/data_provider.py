from __future__ import annotations

import functools
import logging
import os
import threading
import time
import zlib
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing import get_context
from typing import Dict, List, Optional

import numpy as np

from manic.models.database import get_connection
from manic.processors.chromatographic_peak_deconvolution import (
    chromatographic_peak_deconvolution_enabled,
    deconvolve_eic,
    get_deconvolution_fit_cache_info,
)
from manic.processors.integration import (
    _integrate_deconvolved_trace,
    calculate_peak_areas,
)
from manic.processors.natural_abundance_correction import NaturalAbundanceCorrector

logger = logging.getLogger(__name__)

# Minimum number of integration tasks before a process pool is worth its
# spawn/pickle startup cost; below this the bulk export stays on threads.
_PROCESS_POOL_MIN_TASKS = 64

# Per-worker-process DataProvider, created once by the pool initializer and
# reused for every task in that process. It carries no shared mutable state
# beyond a (per-process) natural-abundance corrector, so a fresh instance is
# equivalent to the main one for integration purposes.
_WORKER_PROVIDER: Optional["DataProvider"] = None


def _init_export_worker(use_legacy: bool) -> None:
    """ProcessPoolExecutor initializer: build this process's DataProvider once."""
    global _WORKER_PROVIDER
    _WORKER_PROVIDER = DataProvider(use_legacy_integration=use_legacy)


def _run_integration(provider: "DataProvider", use_legacy: bool, task) -> tuple:
    """Integrate one (sample, compound) task using ``provider``.

    Shared by the thread path (``provider`` is the main instance) and the
    process path (``provider`` is the per-process worker instance), so the
    integration/deconvolution logic lives in exactly one place. ``task`` carries
    only picklable data: the kind, the row as a plain dict, and the compressed
    intensity blob.
    """
    kind, row, y_blob = task
    time_data = np.frombuffer(zlib.decompress(row['x_axis']), dtype=np.float64)
    intensity_data = np.frombuffer(zlib.decompress(y_blob), dtype=np.float64)
    baseline_flag = bool(row['baseline_correction']) if row['baseline_correction'] else False
    corrected_areas = None
    if kind == "raw_and_corrected_deconvolved":
        areas, corrected_areas = (
            provider._calculate_raw_and_corrected_areas_from_raw_component(
                time_data,
                intensity_data,
                row,
                use_legacy=use_legacy,
                baseline_correction=baseline_flag,
            )
        )
    else:
        areas = calculate_peak_areas(
            time_data,
            intensity_data,
            row['label_atoms'] or 0,
            row['retention_time'],
            row['loffset'],
            row['roffset'],
            channel_count=row.get('channel_count'),
            use_legacy=use_legacy,
            baseline_correction=baseline_flag,
            chromatographic_peak_deconvolution_stringency=row['deconvolution_level'],
            chromatographic_peak_deconvolution_fit_type=row['deconvolution_fit_type'],
            chromatographic_peak_deconvolution_noise_gate=row['deconvolution_noise_gate'],
        )
    return kind, row['sample_name'], row['compound_name'], areas, corrected_areas


def _integrate_task(task) -> tuple:
    """Module-level worker entry for ProcessPoolExecutor (must be picklable)."""
    provider = _WORKER_PROVIDER
    return _run_integration(provider, provider.use_legacy_integration, task)


class DataProvider:
    """
    Centralizes database access, data loading, and caching for exports.
    """

    def __init__(
        self,
        *,
        use_legacy_integration: bool = False,
    ):
        self.use_legacy_integration = use_legacy_integration
        self._mrrf_cache: Dict[str, Dict[str, float]] = {}
        self._mrrf_assumed_cache: Dict[str, set] = {}
        self._background_ratios_cache: Dict[str, Dict[str, float]] = {}
        self._bulk_sample_data_cache: Dict[str, Dict[str, List[float]]] = {}
        self._bulk_raw_sample_data_cache: Dict[str, Dict[str, List[float]]] = {}
        self._targeted_area_cache: Dict[tuple, List[float]] = {}
        self._corrector_local = threading.local()
        self._cache_valid: bool = False

    def set_use_legacy_integration(self, use_legacy: bool) -> None:
        if self.use_legacy_integration != use_legacy:
            self.use_legacy_integration = use_legacy
            self.invalidate_cache()

    def invalidate_cache(self) -> None:
        self._mrrf_cache.clear()
        self._mrrf_assumed_cache.clear()
        self._background_ratios_cache.clear()
        self._bulk_sample_data_cache.clear()
        self._bulk_raw_sample_data_cache.clear()
        self._targeted_area_cache.clear()
        self._cache_valid = False

    def get_total_sample_count(self) -> int:
        with get_connection() as conn:
            result = conn.execute("SELECT COUNT(*) FROM samples WHERE deleted=0").fetchone()
            return int(result[0]) if result else 0

    def get_all_compounds(self) -> List[dict]:
        with get_connection() as conn:
            sql = (
                "SELECT c.compound_name, c.label_atoms, c.mass0, c.retention_time, c.loffset, c.roffset, "
                "amount_in_std_mix, int_std_amount, mm_files, formula, baseline_correction "
                ", COALESCE((SELECT COUNT(*) FROM compound_ions ci "
                "WHERE ci.compound_name = c.compound_name), c.label_atoms + 1) AS channel_count "
                "FROM compounds c WHERE c.deleted=0 ORDER BY c.id"
            )
            return list(conn.execute(sql))

    def get_all_samples(self) -> List[str]:
        with get_connection() as conn:
            return [row["sample_name"] for row in conn.execute(
                "SELECT sample_name FROM samples WHERE deleted=0 ORDER BY sample_name"
            )]

    def resolve_mm_samples(self, mm_files_field: Optional[str]) -> List[str]:
        """Resolve MM sample patterns to concrete sample names.

        Robust handling:
        - Accept comma/semicolon/whitespace separated tokens
        - Support '*' wildcards anywhere, translating to SQL LIKE '%'
        - Escape SQL LIKE special chars ('%', '_') in literal tokens
        - Case-insensitive matching via COLLATE NOCASE
        - Deduplicate results
        """
        if not mm_files_field:
            return []

        # Split by common delimiters and normalize tokens
        raw = mm_files_field.replace(';', ',').replace('\n', ',').replace('\t', ',')
        raw_tokens = [t.strip() for t in raw.split(',') if t.strip()]
        if not raw_tokens:
            return []

        def escape_like(s: str) -> str:
            # Escape SQL LIKE special chars, then convert '*' to '%'
            s = s.replace('\\', '\\\\')  # escape backslash first
            s = s.replace('%', '\\%').replace('_', '\\_')
            s = s.replace('*', '%')
            return s

        patterns = []
        for tok in raw_tokens:
            # If token still contains '*' at ends or middle, convert to '%' directly
            # If no '*', do a contains match by wrapping with % ... %
            if '*' in tok:
                p = escape_like(tok)
                # ensure we didn't remove all wildcards; leave '%' as-is
                patterns.append(p)
            else:
                p = escape_like(tok)
                if not p.startswith('%'):
                    p = '%' + p
                if not p.endswith('%'):
                    p = p + '%'
                patterns.append(p)

        matched: set = set()
        with get_connection() as conn:
            for like in patterns:
                sql = (
                    "SELECT sample_name FROM samples "
                    "WHERE deleted=0 AND sample_name LIKE ? ESCAPE '\\' COLLATE NOCASE"
                )
                for row in conn.execute(sql, (like,)):
                    matched.add(row["sample_name"])
        return sorted(matched)

    def load_bulk_sample_data(
        self, progress_callback=None
    ) -> Dict[str, Dict[str, List[float]]]:
        """
        Load all sample data at once for improved performance during exports.
        
        This method pre-loads mixed data (corrected for labeled compounds, raw for unlabeled)
        for all samples and compounds in a single database query, avoiding the overhead of 
        repeated database calls during export operations.

        Args:
            progress_callback: Optional callable invoked with an integer 0-100 as
                integration/deconvolution of the dataset proceeds. This phase runs
                before the export's sheet-writing progress, so callers can surface
                it instead of appearing to hang.

        Returns:
            Dictionary mapping sample names to compound data dictionaries.
            Each compound dictionary maps compound names to lists of isotopologue peak areas.
        """
        if self._cache_valid:
            logger.debug("Using cached bulk sample data (corrected)")
            if progress_callback:
                progress_callback(100)
            return self._bulk_sample_data_cache

        load_start = time.perf_counter()
        logger.info("Loading all sample data in bulk (corrected)...")
        raw_data: Dict[str, Dict[str, List[float]]] = {}
        corrected_data: Dict[str, Dict[str, List[float]]] = {}

        with get_connection() as conn:
            query_start = time.perf_counter()
            samples = [row['sample_name'] for row in conn.execute(
                "SELECT sample_name FROM samples WHERE deleted=0 ORDER BY sample_name"
            )]

            for sample_name in samples:
                raw_data[sample_name] = {}
                corrected_data[sample_name] = {}

            # Always load raw data first (needed for both scenarios)
            raw_eic_query = """
                SELECT e.sample_name, e.compound_name, e.x_axis, e.y_axis,
                       c.label_atoms,
                       COALESCE((SELECT COUNT(*) FROM compound_ions ci
                                 WHERE ci.compound_name = c.compound_name),
                                c.label_atoms + 1) AS channel_count,
                       COALESCE(sa.retention_time, c.retention_time) as retention_time,
                       COALESCE(sa.loffset, c.loffset) as loffset,
                       COALESCE(sa.roffset, c.roffset) as roffset,
                       c.baseline_correction as baseline_correction,
                       c.deconvolution_level as deconvolution_level,
                       c.deconvolution_fit_type as deconvolution_fit_type,
                       c.deconvolution_noise_gate as deconvolution_noise_gate,
                       c.formula as formula,
                       c.label_type as label_type,
                       c.tbdms as tbdms,
                       c.meox as meox,
                       c.me as me
                FROM eic e 
                JOIN compounds c ON e.compound_name = c.compound_name
                LEFT JOIN session_activity sa 
                    ON e.compound_name = sa.compound_name 
                    AND e.sample_name = sa.sample_name 
                    AND sa.sample_deleted = 0
                WHERE e.deleted = 0 AND c.deleted = 0
                ORDER BY e.sample_name, e.compound_name
            """

            corrected_eic_query = """
                SELECT ec.sample_name, ec.compound_name, ec.x_axis, ec.y_axis_corrected,
                       c.label_atoms,
                       c.label_atoms + 1 AS channel_count,
                       COALESCE(sa.retention_time, c.retention_time) as retention_time,
                       COALESCE(sa.loffset, c.loffset) as loffset,
                       COALESCE(sa.roffset, c.roffset) as roffset,
                       c.baseline_correction as baseline_correction,
                       c.deconvolution_level as deconvolution_level,
                       c.deconvolution_fit_type as deconvolution_fit_type,
                       c.deconvolution_noise_gate as deconvolution_noise_gate
                FROM eic_corrected ec 
                JOIN compounds c ON ec.compound_name = c.compound_name
                LEFT JOIN session_activity sa 
                    ON ec.compound_name = sa.compound_name 
                    AND ec.sample_name = sa.sample_name 
                    AND sa.sample_deleted = 0
                WHERE ec.deleted = 0 AND c.deleted = 0
                ORDER BY ec.sample_name, ec.compound_name
            """

            # Load all rows up front (cheap), then integrate/deconvolve them in
            # parallel. Each row is integrated with that compound's own settings,
            # so results are identical to the sequential path - this only spreads
            # the work (mainly the curve fits, which release the GIL) across cores.
            raw_rows = list(conn.execute(raw_eic_query))
            corrected_rows = list(conn.execute(corrected_eic_query))
            query_time = time.perf_counter() - query_start

            # Cache each compound's label_atoms so the corrected-data fallback can
            # look it up without opening a fresh DB connection per compound.
            compound_labels: Dict[str, int] = {}

            task_start = time.perf_counter()
            tasks: list[tuple] = []
            corrected_from_raw_keys: set[tuple[str, str]] = set()
            # Count only the tasks that actually run a (CPU-heavy) curve fit, so
            # the process-pool decision is based on real fitting work rather than
            # the total task count. A large but deconvolution-off export is cheap
            # trapezoid integration and should stay on threads.
            deconv_task_count = 0
            for row in raw_rows:
                sample_name = row['sample_name']
                compound_name = row['compound_name']
                label_atoms = row['label_atoms'] or 0
                compound_labels[compound_name] = label_atoms
                if (
                    sample_name in corrected_data
                    and label_atoms > 0
                    and chromatographic_peak_deconvolution_enabled(
                        row['deconvolution_level']
                    )
                ):
                    tasks.append(("raw_and_corrected_deconvolved", dict(row), row['y_axis']))
                    corrected_from_raw_keys.add((sample_name, compound_name))
                    deconv_task_count += 1
                elif sample_name in raw_data:
                    tasks.append(("raw", dict(row), row['y_axis']))
                    if chromatographic_peak_deconvolution_enabled(row['deconvolution_level']):
                        deconv_task_count += 1
            for row in corrected_rows:
                key = (row['sample_name'], row['compound_name'])
                if (
                    row['sample_name'] in corrected_data
                    and (row['label_atoms'] or 0) > 0
                    and key not in corrected_from_raw_keys
                ):
                    tasks.append(("corrected", dict(row), row['y_axis_corrected']))
                    if chromatographic_peak_deconvolution_enabled(row['deconvolution_level']):
                        deconv_task_count += 1

            task_counts = Counter(task[0] for task in tasks)
            task_time = time.perf_counter() - task_start
            total = max(1, len(tasks))
            use_legacy = self.use_legacy_integration

            def consume(executor, worker) -> None:
                processed = 0
                for (
                    kind,
                    sample_name,
                    compound_name,
                    areas,
                    corrected_areas,
                ) in executor.map(worker, tasks):
                    if kind == "raw":
                        raw_data[sample_name][compound_name] = areas
                    elif kind == "raw_and_corrected_deconvolved":
                        raw_data[sample_name][compound_name] = areas
                        corrected_data[sample_name][compound_name] = corrected_areas or []
                    else:
                        corrected_data[sample_name][compound_name] = areas
                    processed += 1
                    if progress_callback and processed % 25 == 0:
                        progress_callback(int(processed / total * 100))

            max_workers = min(os.cpu_count() or 1, 8)
            integration_start = time.perf_counter()
            fit_cache_before = get_deconvolution_fit_cache_info()

            # The per-window curve fit is GIL-bound (a Python residual driving
            # scipy.least_squares), so threads barely parallelise it. When there
            # is enough *deconvolution* work we fan the fits out to worker
            # processes for true multicore scaling; otherwise (few/no fits, or a
            # deconvolution-off export) the spawn/pickle overhead is not worth it
            # so we stay on threads. (Worker processes do not share the in-memory
            # fit LRU cache, but export windows are mostly distinct anyway.)
            #
            # Force the "spawn" start method explicitly: it matches the frozen
            # build and avoids the fork+threads/Qt deadlock hazard on Linux.
            ran_with_processes = False
            if deconv_task_count >= _PROCESS_POOL_MIN_TASKS:
                try:
                    with ProcessPoolExecutor(
                        max_workers=max_workers,
                        mp_context=get_context("spawn"),
                        initializer=_init_export_worker,
                        initargs=(use_legacy,),
                    ) as executor:
                        consume(executor, _integrate_task)
                    ran_with_processes = True
                except Exception:
                    # Never let a process-pool problem (spawn/pickle/broken pool)
                    # block an export: fall back to the in-process thread path,
                    # which recomputes everything and overwrites idempotently.
                    logger.warning(
                        "Process-pool export integration failed; "
                        "falling back to threads",
                        exc_info=True,
                    )
            if not ran_with_processes:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    consume(executor, functools.partial(_run_integration, self, use_legacy))
            integration_time = time.perf_counter() - integration_start
            fit_cache_after = get_deconvolution_fit_cache_info()
            logger.info(
                "Bulk export integration used %s (workers=%d, tasks=%d) in %.2fs",
                "processes" if ran_with_processes else "threads",
                max_workers,
                len(tasks),
                integration_time,
            )

            # For compounds without corrected data, fall back to their raw integrated areas
            # 
            # IMPORTANT: This fallback exists for two scenarios:
            # 1. Unlabeled compounds (label_atoms=0): These legitimately use raw data
            # 2. Labeled compounds missing corrections: This should NOT happen in normal use
            #    because export_data() ensures all corrections are applied before export
            #
            # If you see warnings about labeled compounds using raw data as fallback,
            # this indicates the correction application step failed or was bypassed.
            fallback_start = time.perf_counter()
            fallback_count = 0
            labeled_fallback_count = 0
            for sample_name, compounds_map in raw_data.items():
                corrected_map = corrected_data.setdefault(sample_name, {})
                for compound_name, areas in compounds_map.items():
                    if compound_name not in corrected_map:
                        # Use the label map captured during the raw load instead of
                        # opening a fresh DB connection per compound.
                        is_labeled = compound_labels.get(compound_name, 0) > 0

                        if is_labeled:
                            labeled_fallback_count += 1
                            # Labeled compound without corrected data - this should not happen
                            # if export was triggered through the UI (which applies corrections first)
                            logger.warning(
                                f"Labeled compound '{compound_name}' in sample '{sample_name}' "
                                f"has no corrected data available. Using raw data as fallback. "
                                f"This may indicate the correction step was skipped or failed."
                            )
                        # For both labeled and unlabeled compounds, fall back to raw data
                        corrected_map[compound_name] = areas
                        fallback_count += 1
            fallback_time = time.perf_counter() - fallback_start

        self._bulk_raw_sample_data_cache = raw_data
        self._bulk_sample_data_cache = corrected_data
        self._cache_valid = True
        if progress_callback:
            progress_callback(100)
        total_time = time.perf_counter() - load_start
        logger.info(
            "Bulk export load completed in %.2fs "
            "(samples=%d, raw_rows=%d, stored_corrected_rows=%d, tasks=%d, "
            "task_counts=%s)",
            total_time,
            len(raw_data),
            len(raw_rows),
            len(corrected_rows),
            len(tasks),
            dict(task_counts),
        )
        logger.info(
            "Bulk export load timing: db_query=%.2fs, task_build=%.2fs, "
            "parallel_integrate=%.2fs, fallback_fill=%.2fs "
            "(fallbacks=%d, labeled_fallbacks=%d, workers=%d)",
            query_time,
            task_time,
            integration_time,
            fallback_time,
            fallback_count,
            labeled_fallback_count,
            max_workers,
        )
        if ran_with_processes:
            # Fits ran in worker processes, each with its own cache, so the
            # parent's before/after counts do not reflect the work done here.
            logger.info(
                "Deconvolution fit cache: fits ran in worker processes "
                "(per-worker caches); parent cache unchanged (%s)",
                fit_cache_after,
            )
        else:
            logger.info(
                "Deconvolution fit cache during bulk load: before=%s after=%s",
                fit_cache_before,
                fit_cache_after,
            )
        logger.info(f"Loaded data for {len(raw_data)} samples (corrected)")
        logger.debug(f"Raw cache compounds per sample: {[(s, len(compounds)) for s, compounds in raw_data.items()]}")
        logger.debug(f"Corrected cache compounds per sample: {[(s, len(compounds)) for s, compounds in corrected_data.items()]}")
        return self._bulk_sample_data_cache

    def get_sample_raw_data(self, sample_name: str) -> Dict[str, List[float]]:
        # Ensure caches are populated to avoid redundant decompression/integration
        self.load_bulk_sample_data()
        if sample_name in self._bulk_raw_sample_data_cache:
            return self._bulk_raw_sample_data_cache[sample_name]

        # Fallback for samples not covered by the bulk load (e.g., deleted mid-run)
        sample_data: Dict[str, List[float]] = {}
        with get_connection() as conn:
            eic_query = (
                "SELECT e.compound_name, e.x_axis, e.y_axis, c.label_atoms, c.retention_time, "
                "c.loffset, c.roffset, c.baseline_correction, "
                "c.deconvolution_level, c.deconvolution_fit_type, "
                "c.deconvolution_noise_gate, "
                "COALESCE((SELECT COUNT(*) FROM compound_ions ci "
                "WHERE ci.compound_name = c.compound_name), c.label_atoms + 1) AS channel_count "
                "FROM eic e JOIN compounds c ON e.compound_name = c.compound_name "
                "WHERE e.sample_name = ? AND e.deleted = 0 AND c.deleted = 0 "
                "ORDER BY e.compound_name"
            )
            for row in conn.execute(eic_query, (sample_name,)):
                compound_name = row['compound_name']
                label_atoms = row['label_atoms']
                retention_time = row['retention_time']
                loffset = row['loffset']
                roffset = row['roffset']
                baseline_flag = bool(row['baseline_correction']) if row['baseline_correction'] else False
                time_data = np.frombuffer(zlib.decompress(row['x_axis']), dtype=np.float64)
                intensity_data = np.frombuffer(zlib.decompress(row['y_axis']), dtype=np.float64)
                areas = calculate_peak_areas(
                    time_data,
                    intensity_data,
                    label_atoms,
                    retention_time,
                    loffset,
                    roffset,
                    channel_count=row["channel_count"],
                    use_legacy=self.use_legacy_integration,
                    baseline_correction=baseline_flag,
                    chromatographic_peak_deconvolution_stringency=row['deconvolution_level'],
                    chromatographic_peak_deconvolution_fit_type=row['deconvolution_fit_type'],
                    chromatographic_peak_deconvolution_noise_gate=row['deconvolution_noise_gate'],
                )
                sample_data[compound_name] = areas
        return sample_data

    def get_sample_corrected_data(self, sample_name: str) -> Dict[str, List[float]]:
        bulk = self.load_bulk_sample_data()
        return bulk.get(sample_name, {})

    def get_compound_total_area(self, sample_name: str, compound_name: str) -> float:
        """
        Get the analytical response used to quantify a compound in a sample.

        Labelled compounds use the sum across M+0...M+n. Unlabelled targeted
        compounds use the Q-ion area only; V ions provide identity evidence and
        must never contribute to the reported response.

        Args:
            sample_name: Name of the sample to query
            compound_name: Name of the compound to query

        Returns:
            Quantification response, or 0.0 if the compound is not found

        Example:
            If compound has isotopologue areas [100.0, 50.0, 25.0], returns 175.0
        """
        # Use the per-compound path (targeted cache) rather than forcing a
        # full-dataset bulk integration for interactive callers.
        areas = self.get_compound_areas(sample_name, compound_name)
        if not areas:
            return 0.0
        with get_connection() as conn:
            has_quantifier = conn.execute(
                "SELECT 1 FROM compound_ions "
                "WHERE compound_name = ? AND role = 'quantifier' LIMIT 1",
                (compound_name,),
            ).fetchone()
        return float(areas[0] if has_quantifier else sum(areas))

    def get_compound_isotope_area(
        self, sample_name: str, compound_name: str, isotope_index: int
    ) -> float:
        """Get the selected isotopologue area (M+isotope_index) for a compound."""
        if isotope_index < 0:
            return 0.0

        sample_data = self.get_sample_corrected_data(sample_name)
        areas = sample_data.get(compound_name, [])
        if not areas or isotope_index >= len(areas):
            return 0.0
        return float(areas[isotope_index])

    def get_compound_m0_area(self, sample_name: str, compound_name: str) -> float:
        """Get the M0 isotopologue area for a compound in a sample."""
        return self.get_compound_isotope_area(sample_name, compound_name, 0)

    def get_compound_areas(
        self, sample_name: str, compound_name: str
    ) -> List[float]:
        """Compute one compound's isotopologue areas for one sample.

        This mirrors the bulk loader's per-compound logic (corrected EIC for
        labeled compounds, raw otherwise; session-override RT/offsets and the
        compound's deconvolution settings) but only for the requested compound.
        It exists so interactive peak-area validation does not have to integrate
        and deconvolve the *entire* dataset just to compare one displayed
        compound against the internal standard. If the full bulk cache happens to
        be populated already, it is reused.
        """
        if self._cache_valid:
            return self._bulk_sample_data_cache.get(sample_name, {}).get(
                compound_name, []
            )

        cache_key = (sample_name, compound_name)
        if cache_key in self._targeted_area_cache:
            return self._targeted_area_cache[cache_key]

        areas = self._compute_compound_areas(sample_name, compound_name)
        self._targeted_area_cache[cache_key] = areas
        return areas

    def assess_unlabelled_identity(self, sample_name: str, compound_name: str):
        """Return RT and qualifier-ratio QC for one targeted compound."""

        from manic.io.compound_reader import read_compound_with_session
        from manic.io.eic_reader import read_eic
        from manic.validation.unlabelled_identity import (
            assess_identity,
            quantifier_apex_time,
        )

        compound = read_compound_with_session(compound_name, sample_name)
        if not compound.is_unlabelled_target:
            raise ValueError(
                f"{compound_name!r} does not have quantifier/qualifier channels"
            )
        eic = read_eic(sample_name, compound, use_corrected=False)
        observed_rt = quantifier_apex_time(
            eic.time,
            eic.intensity,
            compound.channel_count,
            expected_rt=compound.retention_time,
            loffset=compound.loffset,
            roffset=compound.roffset,
        )
        return assess_identity(
            self.get_compound_areas(sample_name, compound_name),
            compound.analysis_channels,
            expected_rt=compound.retention_time,
            observed_rt=observed_rt,
            rt_tolerance=compound.rt_tolerance,
        )

    def _get_corrector(self) -> NaturalAbundanceCorrector:
        corrector = getattr(self._corrector_local, "corrector", None)
        if corrector is None:
            corrector = NaturalAbundanceCorrector()
            self._corrector_local.corrector = corrector
        return corrector

    def _correct_time_series(self, matrix: np.ndarray, row) -> np.ndarray:
        return self._get_corrector().correct_time_series(
            matrix,
            row["formula"],
            row["label_type"],
            row["label_atoms"] or 0,
            row["tbdms"] or 0,
            row["meox"] or 0,
            row["me"] or 0,
        )

    def _calculate_raw_and_corrected_areas_from_raw_component(
        self,
        time_data: np.ndarray,
        raw_intensity_data: np.ndarray,
        row,
        *,
        use_legacy: bool,
        baseline_correction: bool,
    ) -> tuple[List[float], List[float]]:
        """Deconvolve once, then produce both raw and corrected component areas."""
        label_atoms = row["label_atoms"] or 0
        if label_atoms <= 0 or not row["formula"]:
            raw_fallback = calculate_peak_areas(
                time_data,
                raw_intensity_data,
                label_atoms,
                row["retention_time"],
                row["loffset"],
                row["roffset"],
                use_legacy=use_legacy,
                baseline_correction=baseline_correction,
                chromatographic_peak_deconvolution_stringency=row["deconvolution_level"],
                chromatographic_peak_deconvolution_fit_type=row["deconvolution_fit_type"],
                chromatographic_peak_deconvolution_noise_gate=row["deconvolution_noise_gate"],
            )
            # Return a distinct corrected list so downstream consumers can never
            # mutate raw and corrected areas through the same object.
            return raw_fallback, list(raw_fallback)

        n_time_points = len(time_data)
        num_isotopologues = label_atoms + 1
        if raw_intensity_data.size != num_isotopologues * n_time_points:
            return [], []

        raw_matrix = raw_intensity_data.reshape(num_isotopologues, n_time_points)
        deconvolved = deconvolve_eic(
            time_data,
            raw_matrix,
            retention_time=row["retention_time"],
            loffset=row["loffset"],
            roffset=row["roffset"],
            stringency=row["deconvolution_level"],
            fit_type=row["deconvolution_fit_type"],
            noise_gate=row["deconvolution_noise_gate"],
        )
        return self._areas_from_deconvolved(
            time_data,
            deconvolved,
            row,
            use_legacy=use_legacy,
            baseline_correction=baseline_correction,
        )

    def _areas_from_deconvolved(
        self,
        time_data: np.ndarray,
        deconvolved,
        row,
        *,
        use_legacy: bool,
        baseline_correction: bool,
    ) -> tuple[List[float], List[float]]:
        """Integrate raw and corrected areas from a single deconvolution result.

        Both outputs come from the same selected chromatographic component so they
        differ only by the natural-abundance correction. In the time-based model
        path the component is evaluated once on a shared dense grid and raw and
        corrected areas go through the *identical* integration routine; this keeps
        Raw Values and Corrected Values on the same footing (e.g. an unlabeled
        channel integrates to the same number on both export sheets).
        """
        label_atoms = row["label_atoms"] or 0
        num_isotopologues = label_atoms + 1

        if deconvolved.model is not None and not use_legacy:
            model = deconvolved.model
            selected_mask = np.asarray(deconvolved.selected_mask, dtype=bool)
            scans_in_window = max(1, int(np.max(np.sum(selected_mask, axis=1))))
            grid = np.linspace(
                model.integration_left,
                model.integration_right,
                max(65, scans_in_window * 16),
            )
            raw_dense = np.asarray(model.evaluate_selected(grid), dtype=np.float64)
            corrected_dense = self._correct_time_series(raw_dense, row)
            raw_areas = self._integrate_dense_matrix(
                grid, raw_dense, label_atoms, baseline_correction
            )
            corrected_areas = self._integrate_dense_matrix(
                grid, corrected_dense, label_atoms, baseline_correction
            )
            return raw_areas, corrected_areas

        # Raw-trace fallback (model is None): the selected component is the raw
        # matrix restricted to the integration window, so raw and corrected both
        # integrate that same masked support.
        selected_matrix = np.asarray(deconvolved.selected, dtype=np.float64)
        selected_mask = np.asarray(deconvolved.selected_mask, dtype=bool)
        td = np.asarray(time_data, dtype=np.float64)
        raw_areas = [
            _integrate_deconvolved_trace(
                td,
                selected_matrix[i, :],
                selected_mask[i, :],
                use_legacy=use_legacy,
                baseline_correction=baseline_correction,
            )
            for i in range(num_isotopologues)
        ]
        corrected_matrix = self._correct_time_series(selected_matrix, row)
        corrected_areas = calculate_peak_areas(
            time_data,
            corrected_matrix.ravel(),
            label_atoms,
            row["retention_time"],
            row["loffset"],
            row["roffset"],
            use_legacy=use_legacy,
            baseline_correction=baseline_correction,
            chromatographic_peak_deconvolution_stringency="off",
        )
        return raw_areas, corrected_areas

    def _integrate_dense_matrix(
        self,
        grid: np.ndarray,
        matrix: np.ndarray,
        label_atoms: int,
        baseline_correction: bool,
    ) -> List[float]:
        """Integrate every channel of a dense component matrix over ``grid``."""
        return calculate_peak_areas(
            np.asarray(grid, dtype=np.float64),
            np.asarray(matrix, dtype=np.float64).ravel(),
            label_atoms,
            None,
            None,
            None,
            use_legacy=False,
            baseline_correction=baseline_correction,
            chromatographic_peak_deconvolution_stringency="off",
        )

    def _calculate_corrected_areas_from_raw_component(
        self,
        time_data: np.ndarray,
        raw_intensity_data: np.ndarray,
        row,
        *,
        use_legacy: bool,
        baseline_correction: bool,
    ) -> List[float]:
        """Correct and integrate the same chromatographic component selected in raw data.

        Stored ``eic_corrected`` traces are generated from the full raw EIC, before
        chromatographic deconvolution. For labeled compounds with deconvolution
        enabled, downstream corrected values need to follow the component selected
        from the raw isotopologue matrix; otherwise Raw Values can change while
        Corrected Values/Abundances remain tied to the unresolved full trace.
        """
        label_atoms = row["label_atoms"] or 0
        if label_atoms <= 0 or not row["formula"]:
            return calculate_peak_areas(
                time_data,
                raw_intensity_data,
                label_atoms,
                row["retention_time"],
                row["loffset"],
                row["roffset"],
                use_legacy=use_legacy,
                baseline_correction=baseline_correction,
                chromatographic_peak_deconvolution_stringency=row["deconvolution_level"],
                chromatographic_peak_deconvolution_fit_type=row["deconvolution_fit_type"],
                chromatographic_peak_deconvolution_noise_gate=row["deconvolution_noise_gate"],
            )

        n_time_points = len(time_data)
        num_isotopologues = label_atoms + 1
        if raw_intensity_data.size != num_isotopologues * n_time_points:
            return []

        raw_matrix = raw_intensity_data.reshape(num_isotopologues, n_time_points)
        deconvolved = deconvolve_eic(
            time_data,
            raw_matrix,
            retention_time=row["retention_time"],
            loffset=row["loffset"],
            roffset=row["roffset"],
            stringency=row["deconvolution_level"],
            fit_type=row["deconvolution_fit_type"],
            noise_gate=row["deconvolution_noise_gate"],
        )
        _, corrected_areas = self._areas_from_deconvolved(
            time_data,
            deconvolved,
            row,
            use_legacy=use_legacy,
            baseline_correction=baseline_correction,
        )
        return corrected_areas

    def _compute_compound_areas(
        self, sample_name: str, compound_name: str
    ) -> List[float]:
        with get_connection() as conn:
            meta = conn.execute(
                "SELECT c.label_atoms, "
                "COALESCE((SELECT COUNT(*) FROM compound_ions ci "
                "WHERE ci.compound_name = c.compound_name), c.label_atoms + 1) AS channel_count, "
                "COALESCE(sa.retention_time, c.retention_time) as retention_time, "
                "COALESCE(sa.loffset, c.loffset) as loffset, "
                "COALESCE(sa.roffset, c.roffset) as roffset, "
                "c.baseline_correction, c.deconvolution_level, "
                "c.deconvolution_fit_type, c.deconvolution_noise_gate, "
                "c.formula, c.label_type, c.tbdms, c.meox, c.me "
                "FROM compounds c "
                "LEFT JOIN session_activity sa "
                "  ON sa.compound_name = c.compound_name "
                "  AND sa.sample_name = ? AND sa.sample_deleted = 0 "
                "WHERE c.compound_name = ? AND c.deleted = 0",
                (sample_name, compound_name),
            ).fetchone()
            if meta is None:
                return []

            label_atoms = meta["label_atoms"] or 0
            row = None
            use_deconvolved_correction = (
                label_atoms > 0
                and chromatographic_peak_deconvolution_enabled(
                    meta["deconvolution_level"]
                )
            )
            if use_deconvolved_correction:
                row = conn.execute(
                    "SELECT x_axis, y_axis as y FROM eic "
                    "WHERE sample_name = ? AND compound_name = ? AND deleted = 0",
                    (sample_name, compound_name),
                ).fetchone()
            elif label_atoms > 0:
                row = conn.execute(
                    "SELECT x_axis, y_axis_corrected as y FROM eic_corrected "
                    "WHERE sample_name = ? AND compound_name = ? AND deleted = 0",
                    (sample_name, compound_name),
                ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT x_axis, y_axis as y FROM eic "
                    "WHERE sample_name = ? AND compound_name = ? AND deleted = 0",
                    (sample_name, compound_name),
                ).fetchone()
            if row is None:
                return []

            time_data = np.frombuffer(zlib.decompress(row["x_axis"]), dtype=np.float64)
            intensity_data = np.frombuffer(
                zlib.decompress(row["y"]), dtype=np.float64
            )
            baseline_flag = (
                bool(meta["baseline_correction"])
                if meta["baseline_correction"]
                else False
            )
            if use_deconvolved_correction:
                return self._calculate_corrected_areas_from_raw_component(
                    time_data,
                    intensity_data,
                    meta,
                    use_legacy=self.use_legacy_integration,
                    baseline_correction=baseline_flag,
                )
            return calculate_peak_areas(
                time_data,
                intensity_data,
                label_atoms,
                meta["retention_time"],
                meta["loffset"],
                meta["roffset"],
                channel_count=meta["channel_count"],
                use_legacy=self.use_legacy_integration,
                baseline_correction=baseline_flag,
                chromatographic_peak_deconvolution_stringency=meta["deconvolution_level"],
                chromatographic_peak_deconvolution_fit_type=meta["deconvolution_fit_type"],
                chromatographic_peak_deconvolution_noise_gate=meta["deconvolution_noise_gate"],
            )

    def validate_peak_area(
        self,
        sample_name: str,
        compound_name: str,
        internal_standard: str,
        min_ratio: float,
        internal_standard_isotope_index: int = 0,
    ) -> bool:
        """
        Validate if a compound's total peak area meets the minimum threshold.
        
        The validation compares the compound's total area (sum of all isotopologues)
        against a threshold calculated as: internal_standard_reference_peak × min_ratio.
        
        This ensures peaks are large enough relative to the internal standard to be
        considered reliable for quantification.
        
        Args:
            sample_name: Name of the sample
            compound_name: Name of the compound to validate
            internal_standard: Name of the internal standard compound
            min_ratio: Minimum ratio threshold (e.g., 0.05 for 5%)
            
        Returns:
            True if compound total area >= (internal standard reference peak × min_ratio)
            True if validation is disabled (min_ratio <= 0 or no internal standard)
            True if the reference peak has no signal (cannot validate)
            False otherwise (compound fails validation)
            
        Example:
            Compound total = 17.5, IS M0 = 200.0, ratio = 0.05
            Threshold = 200.0 × 0.05 = 10.0
            17.5 >= 10.0 → Returns True (valid)
        """
        if min_ratio <= 0 or not internal_standard:
            return True

        # Compute only the two compounds we actually need (the validated compound
        # and the internal standard) rather than deconvolving the whole dataset.
        # Unlabelled quantification is defined by the Q ion alone. Summing V-ion
        # areas here could let a weak/absent Q ion pass validation merely because
        # an interfering qualifier channel is intense.
        compound_total = self.get_compound_total_area(sample_name, compound_name)

        idx = internal_standard_isotope_index
        is_areas = self.get_compound_areas(sample_name, internal_standard)
        is_ref = (
            float(is_areas[idx]) if is_areas and 0 <= idx < len(is_areas) else 0.0
        )

        if is_ref <= 0:
            return True

        threshold = is_ref * min_ratio
        return compound_total >= threshold

    def get_sample_peak_metrics(
        self,
        sample_name: str,
        internal_standard: str,
        internal_standard_isotope_index: int = 0,
    ) -> Dict[str, Dict[str, float]]:
        """
        Get quantification-response metrics for all compounds in a sample.
        
        Returns a dictionary mapping each compound to its total area and the
        internal standard's reference peak area. Useful for batch validation or export.
        
        Args:
            sample_name: Name of the sample
            internal_standard: Name of the internal standard compound
            
        Returns:
            Dictionary of {compound_name: {"compound_total": float, "internal_standard_reference": float}}

        Example:
            {
                "Pyruvate": {"compound_total": 175.0, "internal_standard_reference": 550.0},
                "Lactate": {"compound_total": 125.0, "internal_standard_reference": 550.0}
            }
        """
        sample_data = self.get_sample_corrected_data(sample_name)
        is_ref = self.get_compound_isotope_area(
            sample_name, internal_standard, internal_standard_isotope_index
        )

        metrics = {}
        for compound_name, areas in sample_data.items():
            compound_total = self.get_compound_total_area(sample_name, compound_name)
            metrics[compound_name] = {
                "compound_total": compound_total,
                "internal_standard_reference": is_ref,
            }
        
        return metrics

    def get_background_ratios(self, compounds: List[dict]) -> Dict[str, float]:
        from manic.processors.calibration import calculate_background_ratios
        cache_key = f"bg_ratios_{len(compounds)}_{self.use_legacy_integration}"
        if cache_key in self._background_ratios_cache:
            logger.debug("Using cached background ratios")
            return self._background_ratios_cache[cache_key]
        values = calculate_background_ratios(self, compounds)
        self._background_ratios_cache[cache_key] = values
        return values

    def get_mrrf_values(
        self,
        compounds: List[dict],
        internal_standard_compound: str,
        internal_standard_isotope_index: int = 0,
        assumed: Optional[set] = None,
    ) -> Dict[str, float]:
        from manic.processors.calibration import calculate_mrrf_values

        cache_key = (
            f"mrrf_{len(compounds)}_{internal_standard_compound}_"
            f"{internal_standard_isotope_index}_{self.use_legacy_integration}"
        )
        if cache_key in self._mrrf_cache:
            logger.debug("Using cached MRRF values")
            if assumed is not None:
                assumed.update(self._mrrf_assumed_cache.get(cache_key, set()))
            return self._mrrf_cache[cache_key]
        assumed_set: set = set()
        values = calculate_mrrf_values(
            self,
            compounds,
            internal_standard_compound,
            internal_standard_isotope_index=internal_standard_isotope_index,
            assumed=assumed_set,
        )
        self._mrrf_cache[cache_key] = values
        self._mrrf_assumed_cache[cache_key] = assumed_set
        if assumed is not None:
            assumed.update(assumed_set)
        return values

