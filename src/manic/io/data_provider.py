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
        self._cache_valid: bool = False

    def set_use_legacy_integration(self, use_legacy: bool) -> None:
        if self.use_legacy_integration != use_legacy:
            self.use_legacy_integration = use_legacy
            self.invalidate_cache()

    def invalidate_cache(self) -> None:
        self._mrrf_cache.clear()
        self._background_ratios_cache.clear()
        self._bulk_sample_data_cache.clear()
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
        if self._cache_valid and self._bulk_sample_data_cache:
            logger.debug("Using cached bulk sample data")
            return self._bulk_sample_data_cache

        logger.info("Loading all sample data in bulk...")
        bulk_data: Dict[str, Dict[str, List[float]]] = {}

        with get_connection() as conn:
            samples = [row['sample_name'] for row in conn.execute(
                "SELECT sample_name FROM samples WHERE deleted=0 ORDER BY sample_name"
            )]

            compounds_query = (
                "SELECT compound_name, label_atoms, retention_time, loffset, roffset "
                "FROM compounds WHERE deleted=0 ORDER BY compound_name"
            )
            compounds = {row['compound_name']: row for row in conn.execute(compounds_query)}

            for s in samples:
                bulk_data[s] = {}

            raw_eic_query = (
                "SELECT e.sample_name, e.compound_name, e.x_axis, e.y_axis "
                "FROM eic e JOIN compounds c ON e.compound_name = c.compound_name "
                "WHERE e.deleted = 0 AND c.deleted = 0 AND c.label_atoms = 0 "
                "ORDER BY e.sample_name, e.compound_name"
            )
            corrected_eic_query = (
                "SELECT ec.sample_name, ec.compound_name, ec.x_axis, ec.y_axis_corrected "
                "FROM eic_corrected ec JOIN compounds c ON ec.compound_name = c.compound_name "
                "WHERE ec.deleted = 0 AND c.deleted = 0 AND c.label_atoms > 0 "
                "ORDER BY ec.sample_name, ec.compound_name"
            )

            for row in conn.execute(raw_eic_query):
                sample_name = row['sample_name']
                compound_name = row['compound_name']
                if sample_name not in bulk_data:
                    continue
                compound_info = compounds.get(compound_name)
                if not compound_info:
                    continue
                time_data = np.frombuffer(zlib.decompress(row['x_axis']), dtype=np.float64)
                intensity_data = np.frombuffer(zlib.decompress(row['y_axis']), dtype=np.float64)
                areas = calculate_peak_areas(
                    time_data,
                    intensity_data,
                    compound_info['label_atoms'],
                    compound_info['retention_time'],
                    compound_info['loffset'],
                    compound_info['roffset'],
                    use_legacy=self.use_legacy_integration,
                )
                bulk_data[sample_name][compound_name] = areas

            for row in conn.execute(corrected_eic_query):
                sample_name = row['sample_name']
                compound_name = row['compound_name']
                if sample_name not in bulk_data:
                    continue
                compound_info = compounds.get(compound_name)
                if not compound_info:
                    continue
                time_data = np.frombuffer(zlib.decompress(row['x_axis']), dtype=np.float64)
                intensity_data = np.frombuffer(zlib.decompress(row['y_axis_corrected']), dtype=np.float64)
                areas = calculate_peak_areas(
                    time_data,
                    intensity_data,
                    compound_info['label_atoms'],
                    compound_info['retention_time'],
                    compound_info['loffset'],
                    compound_info['roffset'],
                    use_legacy=self.use_legacy_integration,
                )
                bulk_data[sample_name][compound_name] = areas

        self._bulk_sample_data_cache = bulk_data
        self._cache_valid = True
        logger.info(f"Loaded data for {len(bulk_data)} samples, {len(compounds)} compounds")
        return bulk_data

    def get_sample_raw_data(self, sample_name: str) -> Dict[str, List[float]]:
        sample_data: Dict[str, List[float]] = {}
        with get_connection() as conn:
            eic_query = (
                "SELECT e.compound_name, e.x_axis, e.y_axis, c.label_atoms, c.retention_time, c.loffset, c.roffset "
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
                )
                sample_data[compound_name] = areas
        return sample_data

    def get_sample_corrected_data(self, sample_name: str) -> Dict[str, List[float]]:
        bulk = self.load_bulk_sample_data()
        return bulk.get(sample_name, {})

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
