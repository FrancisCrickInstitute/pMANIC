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

from manic.io.data_provider import DataProvider
from manic.io.changelog_writer import generate_changelog
from manic.sheet_generators import (
    raw_values as sheet_raw_values,
    corrected_values as sheet_corrected_values,
    isotope_ratios as sheet_isotope_ratios,
    label_incorporation as sheet_label_incorporation,
    abundances as sheet_abundances,
)

logger = logging.getLogger(__name__)


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
                )
                validation_data[sample][compound_name] = is_valid

        return validation_data

    def _integrate_peak(
        self, intensity_data: np.ndarray, time_data: np.ndarray = None
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
    ) -> bool:
        """
        Export all data to Excel with 5 worksheets.

        Args:
            filepath: Output Excel file path
            progress_callback: Optional function to report progress (0-100)
            use_legacy_integration: If provided, overrides the integration mode for this export

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

            # Sheet 1: Raw Values (20% of work)
            sheet_raw_values.write(
                workbook,
                self,
                progress_callback,
                0,
                20,
                validation_data=validation_data,
            )

            # Sheet 2: Corrected Values (20% of work)
            sheet_corrected_values.write(
                workbook,
                self,
                progress_callback,
                20,
                40,
                validation_data=validation_data,
            )

            # Sheet 3: Isotope Ratios (20% of work)
            sheet_isotope_ratios.write(
                workbook,
                self,
                progress_callback,
                40,
                60,
                validation_data=validation_data,
            )

            # Sheet 4: % Label Incorporation (20% of work)
            try:
                sheet_label_incorporation.write(
                    workbook,
                    self,
                    progress_callback,
                    60,
                    80,
                    validation_data=validation_data,
                )
            except Exception as e:
                logger.error(f"Error in % Label Incorporation sheet: {e}")
                raise

            # Sheet 5: Abundances (20% of work) - Final sheet for easy access
            sheet_abundances.write(
                workbook,
                self,
                progress_callback,
                80,
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

        Format matches the reference xlsx exactly:
        Row 1: Compound Name | None | [Compound names repeated for each isotopologue]
        Row 2: Mass | None | [Mass values repeated for each isotopologue]
        Row 3: Isotope | None | [0, 1, 2, 3... for each isotopologue]
        Row 4: tR | None | [Retention times repeated for each isotopologue]
        Row 5+: None | [Sample names] | [Data values]

        This is the starting point data: direct, uncorrected signal intensity from the
        instrument including all natural isotope abundance, baseline noise, and
        experimental artifacts.
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

        Format matches the reference xlsx exactly (same as Raw Values).

        This data has the predictable signal from naturally occurring isotopes
        mathematically removed using the compound's chemical formula correction matrix.
        This is the clean, deconvoluted signal representing true experimental labeling.
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

        Format matches the reference xlsx exactly (same structure as Raw Values and Corrected Values).

        Takes the Corrected Values data and normalizes it so all isotopologues
        for a given compound sum to 1.0, showing the fractional distribution of the label.
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

        Format matches reference xlsx exactly:
        - Only M+0 isotopologue for each compound (total abundance)
        - Includes Units row after tR row
        - Uses compound-based structure (not isotopologue-based)

        Uses internal standard calibration to convert corrected signals into
        absolute biological quantities.
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

        Format matches reference xlsx exactly:
        - Only M+0 isotopologue for each compound (base for calculation)
        - Same structure as Abundances but without Units row
        - Uses compound-based structure (not isotopologue-based)

        Calculates the true percentage of metabolite that has incorporated the
        experimental label, correcting for experimental artifacts using background
        ratios from standard samples.
        """
        from manic.sheet_generators import label_incorporation as _sheet_label

        return _sheet_label.write(
            workbook, self, progress_callback, start_progress, end_progress
        )

    def _calculate_background_ratios(self, compounds) -> Dict[str, float]:
        """Delegate to provider for cached background ratio calculation."""
        return self._provider.get_background_ratios(compounds)

    def _calculate_mrrf_values(
        self, compounds, internal_standard_compound: str
    ) -> Dict[str, float]:
        """Delegate to provider for cached MRRF calculation."""
        return self._provider.get_mrrf_values(compounds, internal_standard_compound)

    def _calculate_peak_areas(
        self,
        time_data: np.ndarray,
        intensity_data: np.ndarray,
        label_atoms: int,
        retention_time: float = None,
        loffset: float = None,
        roffset: float = None,
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
        """Delegate bulk data loading to DataProvider."""
        return self._provider.load_bulk_sample_data()

    def _get_sample_raw_data(self, sample_name: str) -> Dict[str, List[float]]:
        """
        Get integrated raw EIC data for all compounds in a sample.
        Uses bulk data loading for improved performance.

        Args:
            sample_name: Name of the sample

        Returns:
            Dictionary mapping compound names to lists of isotopologue peak areas
        """
        return self._provider.get_sample_raw_data(sample_name)

    def _get_sample_corrected_data(self, sample_name: str) -> Dict[str, List[float]]:
        """
        Get integrated EIC data for all compounds in a sample.
        Uses bulk data loading for improved performance.

        For labeled compounds (label_atoms > 0): fetches corrected data from eic_corrected table
        For unlabeled compounds (label_atoms = 0): fetches raw data directly from eic table

        Args:
            sample_name: Name of the sample

        Returns:
            Dictionary mapping compound names to lists of isotopologue peak areas
        """
        # Use bulk data loading for better performance
        return self._provider.get_sample_corrected_data(sample_name)
