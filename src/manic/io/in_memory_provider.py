from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np

from manic.processors.natural_abundance_correction import NaturalAbundanceCorrector

logger = logging.getLogger(__name__)


class InMemoryDataProvider:
    """
    Minimal provider that serves data from in-memory compounds and raw values.

    compounds: List[dict] with fields used by sheet generators and calibration
    raw_data: Dict[sample][compound] = [areas per isotopologue]
    """

    def __init__(self, compounds: List[dict], samples: List[str], raw_data: Dict[str, Dict[str, List[float]]], *, use_legacy_integration: bool = False):
        self._compounds = compounds
        self._samples = samples
        self._raw = raw_data
        self.use_legacy_integration = use_legacy_integration
        self._corrected_cache: Dict[str, Dict[str, List[float]]] = {}
        self._corrector = NaturalAbundanceCorrector()
        self._mrrf_cache: Dict[str, Dict[str, float]] = {}
        self._bg_cache: Dict[str, Dict[str, float]] = {}

    def get_all_compounds(self) -> List[dict]:
        return self._compounds

    def get_all_samples(self) -> List[str]:
        return list(self._samples)

    def get_sample_raw_data(self, sample_name: str) -> Dict[str, List[float]]:
        return self._raw.get(sample_name, {})

    def get_sample_corrected_data(self, sample_name: str) -> Dict[str, List[float]]:
        # Compute lazily per sample
        if sample_name in self._corrected_cache:
            return self._corrected_cache[sample_name]

        corrected: Dict[str, List[float]] = {}
        raw_map = self.get_sample_raw_data(sample_name)
        # Pre-compute per-compound correction matrices
        for comp in self._compounds:
            name = comp['compound_name']
            areas = raw_map.get(name)
            if not areas:
                continue
            label_atoms = int(comp.get('label_atoms') or 0)
            if label_atoms <= 0:
                corrected[name] = [float(areas[0])] if areas else [0.0]
                continue
            # Build 2D vector with a single time point for reuse of corrector
            vec = np.array(areas, dtype=float).reshape(label_atoms + 1, 1)
            # Force direct-solve path when numerically suitable to match DB-corrected behavior
            cm, cond, use_direct = self._corrector._get_cached_correction_matrix(
                comp.get('formula') or '',
                comp.get('label_type') or 'C',
                label_atoms,
                int(comp.get('tbdms') or 0),
                int(comp.get('meox') or 0),
                int(comp.get('me') or 0),
            )
            if use_direct:
                corr2d = self._corrector._correct_vectorized_direct(vec, cm)
                corr_vec = corr2d[:, 0]
            else:
                corr = self._corrector.correct_time_series(
                    vec,
                    comp.get('formula') or '',
                    comp.get('label_type') or 'C',
                    label_atoms,
                    int(comp.get('tbdms') or 0),
                    int(comp.get('meox') or 0),
                    int(comp.get('me') or 0),
                )
                corr_vec = corr[:, 0]

            # Log if the approximate correction yields near-zero while raw has signal
            raw_total = float(np.sum(vec))
            corr_total = float(np.sum(corr_vec))
            if raw_total > 1e-6 and corr_total <= 1e-9:
                logger.debug(
                    f"UpdateOldData: corrected total ~0 for {name} in {sample_name} (raw_total={raw_total:.6g}). "
                    "This can occur in approximate mode when correcting integrated vectors."
                )

            corrected[name] = corr_vec.astype(float).tolist()

        self._corrected_cache[sample_name] = corrected
        return corrected

    def resolve_mm_samples(self, mm_files_field: Optional[str]) -> List[str]:
        if not mm_files_field:
            return []
        tokens = [t.strip().replace('*', '') for t in mm_files_field.split(',') if t.strip()]
        if not tokens:
            return []
        matched = set()
        for s in self._samples:
            low = s.lower()
            for t in tokens:
                if t.lower() in low:
                    matched.add(s)
                    break
        return sorted(matched)

    def get_background_ratios(self, compounds: List[dict]) -> Dict[str, float]:
        from manic.processors.calibration import calculate_background_ratios
        key = f"bg_{len(compounds)}"
        if key in self._bg_cache:
            return self._bg_cache[key]
        vals = calculate_background_ratios(self, compounds)
        self._bg_cache[key] = vals
        return vals

    def get_mrrf_values(self, compounds: List[dict], internal_standard_compound: str) -> Dict[str, float]:
        # Compute MRRF using only in-memory compounds and corrected data (no DB)
        key = f"mrrf_{len(compounds)}_{internal_standard_compound}"
        if key in self._mrrf_cache:
            return self._mrrf_cache[key]

        # Helper to read fields from dict-like rows
        def _get(row, key, default=None):
            try:
                return row[key]
            except Exception:
                return row.get(key, default) if isinstance(row, dict) else default

        # Lookup internal standard metadata
        intstd_row = next((r for r in compounds if _get(r, 'compound_name') == internal_standard_compound), None)
        internal_std_concentration = _get(intstd_row, 'amount_in_std_mix', 1.0) if intstd_row else 1.0
        internal_std_mm_field = _get(intstd_row, 'mm_files', None) if intstd_row else None
        internal_std_mm_samples = self.resolve_mm_samples(internal_std_mm_field)

        mrrf_values: Dict[str, float] = {}

        for comp_row in compounds:
            cmp_name = _get(comp_row, 'compound_name')
            if cmp_name == internal_standard_compound:
                mrrf_values[cmp_name] = 1.0
                continue

            comp_mm_field = _get(comp_row, 'mm_files', '') or ''
            comp_mm_samples = self.resolve_mm_samples(comp_mm_field)
            if not comp_mm_samples or not internal_std_mm_samples:
                mrrf_values[cmp_name] = 1.0
                continue

            # Numerator: mean metabolite signal over its own MM set
            metabolite_std_conc = _get(comp_row, 'amount_in_std_mix', 1.0) or 1.0
            metabolite_signals: list[float] = []
            for s in comp_mm_samples:
                sd = self.get_sample_corrected_data(s)
                sig = float(sum(sd.get(cmp_name, [])))
                metabolite_signals.append(sig)

            # Denominator: mean internal std signal over its own MM set
            internal_std_signals: list[float] = []
            for s in internal_std_mm_samples:
                sd = self.get_sample_corrected_data(s)
                sig = float(sum(sd.get(internal_standard_compound, [])))
                internal_std_signals.append(sig)

            if metabolite_signals and internal_std_signals and internal_std_concentration > 0 and metabolite_std_conc > 0:
                mean_met = sum(metabolite_signals) / len(metabolite_signals)
                mean_is = sum(internal_std_signals) / len(internal_std_signals)
                if mean_is > 0:
                    mrrf = (mean_met / metabolite_std_conc) / (mean_is / internal_std_concentration)
                    mrrf_values[cmp_name] = mrrf
                    continue

            mrrf_values[cmp_name] = 1.0

        self._mrrf_cache[key] = mrrf_values
        return mrrf_values
