from __future__ import annotations

import logging
import zlib
from typing import Dict, List, Optional

import numpy as np

from manic.models.database import get_connection
from manic.processors.integration import calculate_peak_areas

logger = logging.getLogger(__name__)


class DataProvider:
    """
    Centralizes database access, data loading, and caching for exports.
    """

    def __init__(self, *, use_legacy_integration: bool = False):
        self.use_legacy_integration = use_legacy_integration
        self._mrrf_cache: Dict[str, Dict[str, float]] = {}
        self._background_ratios_cache: Dict[str, Dict[str, float]] = {}
        self._bulk_sample_data_cache: Dict[str, Dict[str, List[float]]] = {}
        self._bulk_raw_sample_data_cache: Dict[str, Dict[str, List[float]]] = {}
        self._cache_valid: bool = False

    def set_use_legacy_integration(self, use_legacy: bool) -> None:
        if self.use_legacy_integration != use_legacy:
            self.use_legacy_integration = use_legacy
            self.invalidate_cache()

    def invalidate_cache(self) -> None:
        self._mrrf_cache.clear()
        self._background_ratios_cache.clear()
        self._bulk_sample_data_cache.clear()
        self._bulk_raw_sample_data_cache.clear()
        self._cache_valid = False

    def get_total_sample_count(self) -> int:
        with get_connection() as conn:
            result = conn.execute("SELECT COUNT(*) FROM samples WHERE deleted=0").fetchone()
            return int(result[0]) if result else 0

    def get_all_compounds(self) -> List[dict]:
        with get_connection() as conn:
            sql = (
                "SELECT compound_name, label_atoms, mass0, retention_time, loffset, roffset, "
                "amount_in_std_mix, int_std_amount, mm_files, formula "
                "FROM compounds WHERE deleted=0 ORDER BY id"
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

    def load_bulk_sample_data(self) -> Dict[str, Dict[str, List[float]]]:
        """
        Load all sample data at once for improved performance during exports.
        
        This method pre-loads mixed data (corrected for labeled compounds, raw for unlabeled)
        for all samples and compounds in a single database query, avoiding the overhead of 
        repeated database calls during export operations.
        
        Returns:
            Dictionary mapping sample names to compound data dictionaries.
            Each compound dictionary maps compound names to lists of isotopologue peak areas.
        """
        if self._cache_valid:
            logger.debug("Using cached bulk sample data (corrected)")
            return self._bulk_sample_data_cache

        logger.info("Loading all sample data in bulk (corrected)...")
        raw_data: Dict[str, Dict[str, List[float]]] = {}
        corrected_data: Dict[str, Dict[str, List[float]]] = {}

        with get_connection() as conn:
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
                       COALESCE(sa.retention_time, c.retention_time) as retention_time,
                       COALESCE(sa.loffset, c.loffset) as loffset,
                       COALESCE(sa.roffset, c.roffset) as roffset,
                       c.baseline_correction as baseline_correction
                FROM eic e 
                JOIN compounds c ON e.compound_name = c.compound_name
                LEFT JOIN session_activity sa 
                    ON e.compound_name = sa.compound_name 
                    AND e.sample_name = sa.sample_name 
                    AND sa.sample_deleted = 0
                WHERE e.deleted = 0 AND c.deleted = 0
                ORDER BY e.sample_name, e.compound_name
            """

            # Load raw data
            for row in conn.execute(raw_eic_query):
                sample_name = row['sample_name']
                compound_name = row['compound_name']
                if sample_name not in raw_data:
                    continue

                time_data = np.frombuffer(zlib.decompress(row['x_axis']), dtype=np.float64)
                intensity_data = np.frombuffer(zlib.decompress(row['y_axis']), dtype=np.float64)
                baseline_flag = bool(row['baseline_correction']) if row['baseline_correction'] else False
                areas = calculate_peak_areas(
                    time_data,
                    intensity_data,
                    row['label_atoms'],
                    row['retention_time'],
                    row['loffset'],
                    row['roffset'],
                    use_legacy=self.use_legacy_integration,
                    baseline_correction=baseline_flag,
                )
                raw_data[sample_name][compound_name] = areas

            # Always load corrected data for labeled compounds
            corrected_eic_query = """
                SELECT ec.sample_name, ec.compound_name, ec.x_axis, ec.y_axis_corrected,
                       c.label_atoms,
                       COALESCE(sa.retention_time, c.retention_time) as retention_time,
                       COALESCE(sa.loffset, c.loffset) as loffset,
                       COALESCE(sa.roffset, c.roffset) as roffset,
                       c.baseline_correction as baseline_correction
                FROM eic_corrected ec 
                JOIN compounds c ON ec.compound_name = c.compound_name
                LEFT JOIN session_activity sa 
                    ON ec.compound_name = sa.compound_name 
                    AND ec.sample_name = sa.sample_name 
                    AND sa.sample_deleted = 0
                WHERE ec.deleted = 0 AND c.deleted = 0
                ORDER BY ec.sample_name, ec.compound_name
            """

            corrected_rows = list(conn.execute(corrected_eic_query))
            logger.debug(f"Found {len(corrected_rows)} corrected EIC rows in database")
            
            for row in corrected_rows:
                sample_name = row['sample_name']
                compound_name = row['compound_name']
                if sample_name not in corrected_data:
                    continue

                label_atoms = row['label_atoms'] or 0
                if label_atoms <= 0:
                    # Unlabeled compounds do not need corrected values; keep raw signal
                    logger.debug(f"Skipping unlabeled compound '{compound_name}' in corrected data")
                    continue

                logger.debug(f"Loading corrected data for labeled compound '{compound_name}' (label_atoms={label_atoms})")
                time_data = np.frombuffer(zlib.decompress(row['x_axis']), dtype=np.float64)
                intensity_data = np.frombuffer(zlib.decompress(row['y_axis_corrected']), dtype=np.float64)
                baseline_flag = bool(row['baseline_correction']) if row['baseline_correction'] else False
                areas = calculate_peak_areas(
                    time_data,
                    intensity_data,
                    label_atoms,
                    row['retention_time'],
                    row['loffset'],
                    row['roffset'],
                    use_legacy=self.use_legacy_integration,
                    baseline_correction=baseline_flag,
                )
                corrected_data[sample_name][compound_name] = areas

            # For compounds without corrected data, fall back to their raw integrated areas
            # 
            # IMPORTANT: This fallback exists for two scenarios:
            # 1. Unlabeled compounds (label_atoms=0): These legitimately use raw data
            # 2. Labeled compounds missing corrections: This should NOT happen in normal use
            #    because export_data() ensures all corrections are applied before export
            #
            # If you see warnings about labeled compounds using raw data as fallback,
            # this indicates the correction application step failed or was bypassed.
            for sample_name, compounds_map in raw_data.items():
                corrected_map = corrected_data.setdefault(sample_name, {})
                for compound_name, areas in compounds_map.items():
                    if compound_name not in corrected_map:
                        # Check if this is a labeled compound by looking up label_atoms
                        with get_connection() as conn:
                            label_atoms = conn.execute(
                                "SELECT label_atoms FROM compounds WHERE compound_name = ? AND deleted = 0",
                                (compound_name,)
                            ).fetchone()
                            is_labeled = label_atoms and label_atoms[0] > 0 if label_atoms else False
                        
                        if is_labeled:
                            # Labeled compound without corrected data - this should not happen
                            # if export was triggered through the UI (which applies corrections first)
                            logger.warning(
                                f"Labeled compound '{compound_name}' in sample '{sample_name}' "
                                f"has no corrected data available. Using raw data as fallback. "
                                f"This may indicate the correction step was skipped or failed."
                            )
                        # For both labeled and unlabeled compounds, fall back to raw data
                        corrected_map[compound_name] = areas

        self._bulk_raw_sample_data_cache = raw_data
        self._bulk_sample_data_cache = corrected_data
        self._cache_valid = True
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
                "c.loffset, c.roffset, c.baseline_correction "
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
                    use_legacy=self.use_legacy_integration,
                    baseline_correction=baseline_flag,
                )
                sample_data[compound_name] = areas
        return sample_data

    def get_sample_corrected_data(self, sample_name: str) -> Dict[str, List[float]]:
        bulk = self.load_bulk_sample_data()
        return bulk.get(sample_name, {})

    def get_compound_total_area(self, sample_name: str, compound_name: str) -> float:
        """
        Get the sum of all isotopologue peak areas for a compound in a sample.
        
        This returns the total integrated area across all isotopologues (M0, M1, M2, etc.)
        for the specified compound. The areas are already integrated using the compound's
        own retention time and offset boundaries (respecting session overrides).
        
        Args:
            sample_name: Name of the sample to query
            compound_name: Name of the compound to query
            
        Returns:
            Total area (sum of all isotopologue areas), or 0.0 if compound not found
            
        Example:
            If compound has isotopologue areas [100.0, 50.0, 25.0], returns 175.0
        """
        sample_data = self.get_sample_corrected_data(sample_name)
        areas = sample_data.get(compound_name, [])
        return float(sum(areas)) if areas else 0.0

    def validate_peak_area(
        self, 
        sample_name: str, 
        compound_name: str,
        internal_standard: str, 
        min_ratio: float
    ) -> bool:
        """
        Validate if a compound's total peak area meets the minimum threshold.
        
        The validation compares the compound's total area (sum of all isotopologues)
        against a threshold calculated as: internal_standard_total × min_ratio.
        
        This ensures peaks are large enough relative to the internal standard to be
        considered reliable for quantification.
        
        Args:
            sample_name: Name of the sample
            compound_name: Name of the compound to validate
            internal_standard: Name of the internal standard compound
            min_ratio: Minimum ratio threshold (e.g., 0.05 for 5%)
            
        Returns:
            True if compound total area >= (internal standard total × min_ratio)
            True if validation is disabled (min_ratio <= 0 or no internal standard)
            True if internal standard has no signal (cannot validate)
            False otherwise (compound fails validation)
            
        Example:
            Compound total = 17.5, IS total = 200.0, ratio = 0.05
            Threshold = 200.0 × 0.05 = 10.0
            17.5 >= 10.0 → Returns True (valid)
        """
        if min_ratio <= 0 or not internal_standard:
            return True
        
        compound_total = self.get_compound_total_area(sample_name, compound_name)
        is_total = self.get_compound_total_area(sample_name, internal_standard)
        
        if is_total <= 0:
            return True
        
        threshold = is_total * min_ratio
        return compound_total >= threshold

    def get_sample_peak_metrics(
        self, 
        sample_name: str, 
        internal_standard: str
    ) -> Dict[str, Dict[str, float]]:
        """
        Get total area metrics for all compounds in a sample for validation.
        
        Returns a dictionary mapping each compound to its total area and the
        internal standard's total area. Useful for batch validation or export.
        
        Args:
            sample_name: Name of the sample
            internal_standard: Name of the internal standard compound
            
        Returns:
            Dictionary of {compound_name: {"compound_total": float, "internal_standard_total": float}}
            
        Example:
            {
                "Pyruvate": {"compound_total": 175.0, "internal_standard_total": 550.0},
                "Lactate": {"compound_total": 125.0, "internal_standard_total": 550.0}
            }
        """
        sample_data = self.get_sample_corrected_data(sample_name)
        is_total = self.get_compound_total_area(sample_name, internal_standard)
        
        metrics = {}
        for compound_name, areas in sample_data.items():
            compound_total = float(sum(areas)) if areas else 0.0
            metrics[compound_name] = {
                "compound_total": compound_total,
                "internal_standard_total": is_total
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

    def get_mrrf_values(self, compounds: List[dict], internal_standard_compound: str) -> Dict[str, float]:
        from manic.processors.calibration import calculate_mrrf_values
        cache_key = f"mrrf_{len(compounds)}_{internal_standard_compound}_{self.use_legacy_integration}"
        if cache_key in self._mrrf_cache:
            logger.debug("Using cached MRRF values")
            return self._mrrf_cache[cache_key]
        values = calculate_mrrf_values(self, compounds, internal_standard_compound)
        self._mrrf_cache[cache_key] = values
        return values
