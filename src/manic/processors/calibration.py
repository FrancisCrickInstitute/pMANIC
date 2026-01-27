from __future__ import annotations

import logging
from typing import Dict, List, Optional

from manic.models.database import get_connection

logger = logging.getLogger(__name__)


def calculate_background_ratios(provider, compounds: List[dict]) -> Dict[str, float]:
    """
    Calculate background ratios from MM files (standard mixture samples).

    Background ratio is computed as the mean of per-sample ratios:
        background = mean( labelled_sum_i / m0_i ) over matched MM files i

    This mirrors MATLAB GVISO's mean(backgrounds) behavior (not ratio of means).
    """
    background_ratios: Dict[str, float] = {}

    for compound_row in compounds:
        compound_name = compound_row["compound_name"]
        mm_files_field = (
            compound_row["mm_files"] if compound_row["mm_files"] is not None else ""
        )

        # Resolve samples from possibly multiple mm_files patterns
        mm_samples = provider.resolve_mm_samples(mm_files_field)

        if not mm_samples:
            logger.warning(
                f"No MM files found for compound {compound_name} with patterns '{mm_files_field}'"
            )
            background_ratios[compound_name] = 0.0
            continue

        logger.info(
            f"Found {len(mm_samples)} MM files for {compound_name} with patterns '{mm_files_field}': {mm_samples}"
        )

        # IMPORTANT: Background correction logic is defined per compound using matched MM files
        # We aggregate per-sample labelled/M0 ratios via mean (MATLAB GVISO-compatible)

        # Track per-sample background ratios to compute mean(labeled/unlabeled)
        per_sample_backgrounds: List[float] = []

        for mm_sample in mm_samples:
            sample_data = provider.get_sample_corrected_data(mm_sample)
            # For label_atoms=0, get all available isotopologues
            isotopologue_data = sample_data.get(compound_name, [0.0])

            if len(isotopologue_data) > 1:
                unlabeled_signal = float(isotopologue_data[0])
                labeled_signal = float(sum(isotopologue_data[1:]))
                if unlabeled_signal > 0:
                    per_sample_backgrounds.append(labeled_signal / unlabeled_signal)

        if per_sample_backgrounds:
            background_ratio = sum(per_sample_backgrounds) / len(per_sample_backgrounds)
            background_ratios[compound_name] = background_ratio
            logger.debug(
                f"Background ratio for {compound_name} (mean of per-sample ratios): {background_ratio:.6f}"
            )
        else:
            background_ratios[compound_name] = 0.0

    return background_ratios


def calculate_mrrf_values(
    provider,
    compounds: List[dict],
    internal_standard_compound: str,
    *,
    internal_standard_isotope_index: int = 0,
) -> Dict[str, float]:
    """
    Calculate MRRF values using MM files.

    Internal standard signal uses the configured reference peak (M+N).
    """
    mrrf_values: Dict[str, float] = {}

    # Get internal standard concentration from compound metadata
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT amount_in_std_mix FROM compounds WHERE compound_name = ? AND deleted = 0",
            (internal_standard_compound,),
        )
        row = cursor.fetchone()
        try:
            internal_std_concentration = (
                row["amount_in_std_mix"]
                if row and row["amount_in_std_mix"] is not None
                else 1.0
            )
        except (KeyError, TypeError):
            internal_std_concentration = 1.0
            logger.debug(
                f"amount_in_std_mix not found for internal standard {internal_standard_compound}, using default 1.0"
            )

    # Resolve internal standard's MM sample set once
    internal_std_mm_field: Optional[str] = None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT mm_files FROM compounds WHERE compound_name = ? AND deleted = 0",
            (internal_standard_compound,),
        ).fetchone()
        if row is not None:
            try:
                internal_std_mm_field = row["mm_files"]
            except Exception:
                internal_std_mm_field = None
    internal_std_mm_samples = provider.resolve_mm_samples(internal_std_mm_field)

    for compound_row in compounds:
        compound_name = compound_row["compound_name"]

        if compound_name == internal_standard_compound:
            mrrf_values[compound_name] = 1.0
            continue

        compound_mm_field = (
            compound_row["mm_files"] if compound_row["mm_files"] is not None else ""
        )
        if not compound_mm_field:
            logger.warning(
                f"No MM files pattern specified for compound {compound_name}"
            )
            mrrf_values[compound_name] = 1.0
            continue

        compound_mm_samples = provider.resolve_mm_samples(compound_mm_field)
        if not compound_mm_samples:
            logger.warning(
                f"No MM files found for compound {compound_name} with patterns '{compound_mm_field}'"
            )
            mrrf_values[compound_name] = 1.0
            continue

        metabolite_signals: List[float] = []
        for mm_sample in compound_mm_samples:
            sample_data = provider.get_sample_corrected_data(mm_sample)
            isotopologue_data = sample_data.get(compound_name, [0.0])
            total_signal = float(sum(isotopologue_data))
            metabolite_signals.append(total_signal)

        internal_std_signals: List[float] = []
        for mm_sample in internal_std_mm_samples:
            sample_data = provider.get_sample_corrected_data(mm_sample)
            iso_data = sample_data.get(internal_standard_compound, [0.0])
            # Use configured internal standard reference peak (M+N)
            idx = int(internal_standard_isotope_index)
            if 0 <= idx < len(iso_data):
                ref_signal = float(iso_data[idx])
            else:
                ref_signal = 0.0
            internal_std_signals.append(ref_signal)

        mean_metabolite_signal = (
            float(sum(metabolite_signals) / len(metabolite_signals))
            if metabolite_signals
            else 0.0
        )
        mean_internal_std_signal = (
            float(sum(internal_std_signals) / len(internal_std_signals))
            if internal_std_signals
            else 0.0
        )

        try:
            amount_in_std_mix = compound_row["amount_in_std_mix"]
            metabolite_std_concentration = (
                amount_in_std_mix if amount_in_std_mix is not None else 1.0
            )
        except (KeyError, IndexError):
            metabolite_std_concentration = 1.0
            logger.debug(
                f"amount_in_std_mix not found for {compound_name}, using default 1.0"
            )

        if (
            mean_metabolite_signal > 0
            and metabolite_std_concentration > 0
            and mean_internal_std_signal > 0
            and internal_std_concentration > 0
        ):
            mrrf = (mean_metabolite_signal / metabolite_std_concentration) / (
                mean_internal_std_signal / internal_std_concentration
            )
            mrrf_values[compound_name] = mrrf
            logger.debug(f"MRRF for {compound_name}: {mrrf:.6f} (using MEANS)")
        else:
            mrrf_values[compound_name] = 1.0
            logger.warning(
                f"Could not calculate MRRF for {compound_name}, using 1.0. "
                f"mean_metabolite_signal={mean_metabolite_signal:.3f}, "
                f"metabolite_std_concentration={metabolite_std_concentration}, "
                f"mean_internal_std_signal={mean_internal_std_signal:.3f}, "
                f"internal_std_concentration={internal_std_concentration}"
            )

    return mrrf_values
