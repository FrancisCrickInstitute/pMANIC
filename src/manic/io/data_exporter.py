"""
Excel data export functionality for MANIC.

Exports mass spectrometry data to Excel with 5 worksheets:
1. Raw Values - Direct instrument signals (uncorrected peak areas)
2. Corrected Values - Natural isotope abundance corrected signals
3. Isotope Ratios - Normalized corrected values (sum to 1.0)
4. % Label Incorporation - Percentage of experimental label incorporation
5. Abundances - Absolute metabolite concentrations via internal standard calibration (final sheet)

Uses streaming approach for optimal memory usage and performance.
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import xlsxwriter

from manic.io.changelog_writer import generate_changelog
from manic.io.data_provider import DataProvider
from manic.sheet_generators import (
    abundances as sheet_abundances,
)
from manic.sheet_generators import (
    carbon_enrichment as sheet_carbon_enrichment,
)
from manic.sheet_generators import (
    corrected_values as sheet_corrected_values,
)
from manic.sheet_generators import (
    isotope_ratios as sheet_isotope_ratios,
)
from manic.sheet_generators import (
    label_incorporation as sheet_label_incorporation,
)
from manic.sheet_generators import (
    raw_values as sheet_raw_values,
)

logger = logging.getLogger(__name__)


def validate_internal_standard_metadata(
    provider: DataProvider, internal_standard_compound: Optional[str]
) -> tuple[bool, list[str]]:
    """Validate internal standard metadata required for calibrated exports.

    Returns:
        (ok, problems)

    Notes:
        The internal standard requires:
        - int_std_amount > 0 (amount added to biological samples)
        - amount_in_std_mix > 0 (concentration in standard mixture / MM files)

        If either field is missing or 0, the export UI can fall back to Peak Area mode.
    """

    if not internal_standard_compound:
        return True, []

    compounds = provider.get_all_compounds()
    intstd_rows = [
        c for c in compounds if c["compound_name"] == internal_standard_compound
    ]

    if not intstd_rows:
        return (
            False,
            [
                (
                    f"Internal standard '{internal_standard_compound}' not found in compound list"
                )
            ],
        )

    intstd_row = intstd_rows[0]

    problems: list[str] = []

    int_std_amount_val = intstd_row["int_std_amount"]
    if int_std_amount_val is None or float(int_std_amount_val) <= 0:
        problems.append("Missing or zero 'int_std_amount'")

    amount_in_std_mix_val = intstd_row["amount_in_std_mix"]
    if amount_in_std_mix_val is None or float(amount_in_std_mix_val) <= 0:
        problems.append("Missing or zero 'amount_in_std_mix'")

    return (len(problems) == 0), problems


class DataExporter:
    """
    Streaming Excel exporter for mass spectrometry data.

    Processes data in small batches to minimize RAM usage while maintaining
    high performance through direct database queries and efficient calculations.
    """

    def __init__(self):
        """Initialize the data exporter."""
        self.internal_standard_compound = None  # Set by UI before export
        # Time-based by default (matches app/UI defaults and docs)
        self.use_legacy_integration = False
        # Centralized data provider for DB access and caching
        self._provider = DataProvider(
            use_legacy_integration=self.use_legacy_integration
        )
        # Minimum peak area ratio for validation highlighting
        self.min_peak_area_ratio = 0.05

        # Which isotopologue peak (M+N) to use as the internal standard reference peak
        # across validation + abundance + MRRF. Default is 0 (M0).
        self.internal_standard_reference_isotope = 0

    def _resolve_mm_samples(self, mm_files_field: Optional[str]) -> List[str]:
        """Delegate to provider to resolve MM sample patterns."""
        return self._provider.resolve_mm_samples(mm_files_field)

    def set_internal_standard(self, compound_name: Optional[str]):
        """Set the internal standard compound for abundance calculations."""
        if self.internal_standard_compound != compound_name:
            self.internal_standard_compound = compound_name
            self._invalidate_cache()

    def set_use_legacy_integration(self, use_legacy: bool):
        """Set whether to use legacy MATLAB-compatible unit-spacing integration."""
        if self.use_legacy_integration != use_legacy:
            self.use_legacy_integration = use_legacy
            self._provider.set_use_legacy_integration(use_legacy)
            self._invalidate_cache()

    def set_min_peak_area_ratio(self, ratio: float):
        """Set the minimum peak area ratio for validation highlighting."""
        self.min_peak_area_ratio = ratio

    def set_internal_standard_reference_isotope(self, isotope_index: int) -> None:
        """Set internal standard reference isotopologue (M+N).

        This value is used for:
        - validation threshold reference peak
        - internal standard normalization in Abundances
        - MRRF calculation
        """
        isotope_index_int = int(isotope_index)
        if isotope_index_int < 0:
            isotope_index_int = 0

        if self.internal_standard_reference_isotope != isotope_index_int:
            self.internal_standard_reference_isotope = isotope_index_int
            self._invalidate_cache()

    def _invalidate_cache(self):
        """Invalidate all caches when parameters change."""
        self._provider.invalidate_cache()

    def _compute_validation_data(
        self, samples: List[str], compounds: List[dict]
    ) -> Dict[str, Dict[str, bool]]:
        """
        Compute validation data for all sample/compound combinations.

        Returns:
            Dict mapping sample_name -> {compound_name: is_valid}
        """
        # Change: Validation (area ratio vs standard) cannot be performed without an internal standard
        if not self.internal_standard_compound or self.min_peak_area_ratio <= 0:
            return {}

        validation_data = {}
        for sample in samples:
            validation_data[sample] = {}
            for compound in compounds:
                compound_name = compound["compound_name"]
                is_valid = self._provider.validate_peak_area(
                    sample,
                    compound_name,
                    self.internal_standard_compound,
                    self.min_peak_area_ratio,
                    internal_standard_isotope_index=self.internal_standard_reference_isotope,
                )
                validation_data[sample][compound_name] = is_valid

        return validation_data

    def _integrate_peak(
        self, intensity_data: np.ndarray, time_data: Optional[np.ndarray] = None
    ) -> float:
        """Delegates to processors.integration.integrate_peak (backward-compatible stub)."""
        from manic.processors.integration import integrate_peak

        return integrate_peak(
            intensity_data, time_data, use_legacy=self.use_legacy_integration
        )

    def _generate_changelog(self, export_filepath: str) -> None:
        """Delegate changelog generation to a separate module."""
        generate_changelog(
            export_filepath,
            internal_standard=self.internal_standard_compound,
            use_legacy_integration=self.use_legacy_integration,
        )

    def export_to_excel(
        self,
        filepath: str,
        progress_callback=None,
        use_legacy_integration: Optional[bool] = None,
        include_carbon_enrichment: bool = False,
    ) -> bool:
        """
        Export all data to Excel with multiple worksheets.

        Args:
            filepath: Output Excel file path
            progress_callback: Optional function to report progress (0-100)
            use_legacy_integration: If provided, overrides the integration mode for this export
            include_carbon_enrichment: If True, include the % Carbons Labelled sheet (default: False)

        Returns:
            True if export successful, False otherwise

        Raises:
            Exception: If export fails due to database or file system errors
        """
        try:
            start_time = time.time()
            logger.info(f"Starting Excel export to {filepath}")

            # Optional per-call override of integration mode
            if use_legacy_integration is not None:
                self.use_legacy_integration = use_legacy_integration
                self._provider.set_use_legacy_integration(use_legacy_integration)

            # Phase 1 optimization: Pre-load all sample data in bulk
            logger.info("Phase 1 optimization: Pre-loading all sample data...")
            data_load_start = time.time()
            bulk_data = self._provider.load_bulk_sample_data()
            data_load_time = time.time() - data_load_start
            logger.info(
                f"Loaded data for {len(bulk_data)} samples in bulk ({data_load_time:.2f}s)"
            )

            # Compute validation data for all samples/compounds
            samples = self._provider.get_all_samples()
            compounds = self._provider.get_all_compounds()
            validation_data = self._compute_validation_data(samples, compounds)

            # Create Excel workbook with optimization settings
            workbook = xlsxwriter.Workbook(
                filepath,
                {
                    "constant_memory": True,  # Optimize for low RAM usage
                    "use_zip64": True,  # Handle large files
                },
            )

            # Create all worksheets
            progress = 0
            if progress_callback:
                progress_callback(progress)

            # Sheet 1: Raw Values (16% of work)
            sheet_raw_values.write(
                workbook,
                self,
                progress_callback,
                0,
                16,
                validation_data=validation_data,
            )

            # Sheet 2: Corrected Values (16% of work)
            sheet_corrected_values.write(
                workbook,
                self,
                progress_callback,
                16,
                32,
                validation_data=validation_data,
            )

            # Sheet 3: Isotope Ratios (16% of work)
            sheet_isotope_ratios.write(
                workbook,
                self,
                progress_callback,
                32,
                48,
                validation_data=validation_data,
            )

            # Sheet 4: % Label Incorporation (16% of work)
            try:
                sheet_label_incorporation.write(
                    workbook,
                    self,
                    progress_callback,
                    48,
                    64,
                    validation_data=validation_data,
                )
            except Exception as e:
                logger.error(f"Error in % Label Incorporation sheet: {e}")
                raise

            # Sheet 5: % Carbons Labelled (Average Enrichment) - optional
            if include_carbon_enrichment:
                try:
                    sheet_carbon_enrichment.write(
                        workbook,
                        self,
                        progress_callback,
                        64,
                        80,
                        validation_data=validation_data,
                        provider=self._provider,
                    )
                except Exception as e:
                    logger.error(f"Error in % Carbons Labelled sheet: {e}")

            # Sheet 6: Abundances (20% of work) - Final sheet for easy access
            # Adjust progress range based on whether carbon enrichment was included
            abundance_start = 80 if include_carbon_enrichment else 64
            sheet_abundances.write(
                workbook,
                self,
                progress_callback,
                abundance_start,
                100,
                validation_data=validation_data,
            )

            workbook.close()

            if progress_callback:
                progress_callback(100)

            total_time = time.time() - start_time
            logger.info(
                f"Excel export completed successfully: {filepath} ({total_time:.2f}s total)"
            )
            logger.info(
                f"Performance breakdown: Data loading: {data_load_time:.2f}s, Excel writing: {total_time - data_load_time:.2f}s"
            )

            # Generate changelog
            self._generate_changelog(filepath)

            return True

        except Exception as e:
            logger.error(f"Excel export failed: {str(e)}")
            # Clean up partial file if it exists
            try:
                Path(filepath).unlink(missing_ok=True)
            except Exception as e:
                pass
            raise

    def _export_raw_values_sheet(
        self, workbook, progress_callback, start_progress, end_progress
    ):
        """
        Export Raw Values sheet - direct instrument signals (uncorrected peak areas).
        """
        from manic.sheet_generators import raw_values as _sheet_raw

        return _sheet_raw.write(
            workbook, self, progress_callback, start_progress, end_progress
        )

    def _export_corrected_values_sheet(
        self, workbook, progress_callback, start_progress, end_progress
    ):
        """
        Export Corrected Values sheet - natural isotope abundance corrected signals.
        """
        from manic.sheet_generators import corrected_values as _sheet_corrected

        return _sheet_corrected.write(
            workbook, self, progress_callback, start_progress, end_progress
        )

    def _export_isotope_ratios_sheet(
        self, workbook, progress_callback, start_progress, end_progress
    ):
        """
        Export Isotope Ratios sheet - normalized corrected values (sum to 1.0).
        """
        from manic.sheet_generators import isotope_ratios as _sheet_iso

        return _sheet_iso.write(
            workbook, self, progress_callback, start_progress, end_progress
        )

    def _export_abundances_sheet(
        self, workbook, progress_callback, start_progress, end_progress
    ):
        """
        Export Abundances sheet - absolute metabolite concentrations.
        """
        from manic.sheet_generators import abundances as _sheet_abund

        return _sheet_abund.write(
            workbook, self, progress_callback, start_progress, end_progress
        )

    def _export_label_incorporation_sheet(
        self, workbook, progress_callback, start_progress, end_progress
    ):
        """
        Export % Label Incorporation sheet - percentage of experimental label incorporation.
        """
        from manic.sheet_generators import label_incorporation as _sheet_label

        return _sheet_label.write(
            workbook, self, progress_callback, start_progress, end_progress
        )

    def _calculate_background_ratios(self, compounds) -> Dict[str, float]:
        """Delegate to provider for cached background ratio calculation."""
        return self._provider.get_background_ratios(compounds)

    def _calculate_mrrf_values(
        self, compounds, internal_standard_compound: Optional[str]
    ) -> Dict[str, float]:
        """Delegate to provider for cached MRRF calculation."""
        # Return empty results if no internal standard is provided
        if not internal_standard_compound:
            return {}
        return self._provider.get_mrrf_values(
            compounds,
            internal_standard_compound,
            internal_standard_isotope_index=self.internal_standard_reference_isotope,
        )

    def _calculate_peak_areas(
        self,
        time_data: np.ndarray,
        intensity_data: np.ndarray,
        label_atoms: int,
        retention_time: Optional[float] = None,
        loffset: Optional[float] = None,
        roffset: Optional[float] = None,
    ) -> List[float]:
        """Delegates to processors.integration.calculate_peak_areas (backward-compatible stub)."""
        from manic.processors.integration import calculate_peak_areas as _calc

        return _calc(
            time_data,
            intensity_data,
            label_atoms,
            retention_time,
            loffset,
            roffset,
            use_legacy=self.use_legacy_integration,
        )

    def _get_total_sample_count(self) -> int:
        """Get total number of active samples for progress calculation."""
        return self._provider.get_total_sample_count()

    def _load_bulk_sample_data(self) -> Dict[str, Dict[str, List[float]]]:
        """Load bulk sample data using provider for caching."""
        return self._provider.load_bulk_sample_data()

    def _get_sample_raw_data(self, sample_name: str) -> Dict[str, List[float]]:
        """
        Get integrated raw EIC data for all compounds in a sample.
        """
        return self._provider.get_sample_raw_data(sample_name)

    def _get_sample_corrected_data(self, sample_name: str) -> Dict[str, List[float]]:
        """
        Get integrated EIC data for all compounds in a sample.
        """
        # Use bulk data loading for better performance
        return self._provider.get_sample_corrected_data(sample_name)
