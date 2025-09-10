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
import zlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import xlsxwriter

from manic.__version__ import __version__
from manic.io.compound_reader import read_compound
from manic.models.database import get_connection

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

    def _resolve_mm_samples(self, mm_files_field: Optional[str]) -> List[str]:
        """Resolve MM file patterns to a deduplicated list of sample names.

        Behavior:
        - Split by commas into multiple patterns
        - Trim whitespace
        - Strip '*' characters from each token
        - Match each token as a substring (SQL LIKE %token%)
        - Union matches across tokens (dedupe overlaps)
        """
        if not mm_files_field:
            return []

        # Prepare tokens
        raw_tokens = [t.strip() for t in mm_files_field.split(',') if t.strip()]
        tokens = [t.replace('*', '') for t in raw_tokens]
        tokens = [t for t in tokens if t]  # drop empties after stripping

        if not tokens:
            return []

        matched: set = set()
        with get_connection() as conn:
            for token in tokens:
                like = f"%{token}%"
                for row in conn.execute(
                    "SELECT sample_name FROM samples WHERE sample_name LIKE ? AND deleted=0",
                    (like,),
                ):
                    matched.add(row["sample_name"])

        return sorted(matched)
        
    def set_internal_standard(self, compound_name: Optional[str]):
        """Set the internal standard compound for abundance calculations."""
        self.internal_standard_compound = compound_name
        
    def set_use_legacy_integration(self, use_legacy: bool):
        """Set whether to use legacy MATLAB-compatible unit-spacing integration."""
        self.use_legacy_integration = use_legacy
        
    def _integrate_peak(self, intensity_data: np.ndarray, time_data: np.ndarray = None) -> float:
        """
        Integrate peak using either time-based or legacy unit-spacing method.
        
        Args:
            intensity_data: Peak intensity values
            time_data: Time points (optional, ignored in legacy mode)
            
        Returns:
            Integrated peak area
        """
        if self.use_legacy_integration or time_data is None:
            # MATLAB-style: unit spacing (produces ~100× larger values)
            return np.trapz(intensity_data)
        else:
            # Scientific: time-based integration (physically meaningful)
            return np.trapz(intensity_data, time_data)

    def _generate_changelog(self, export_filepath: str) -> None:
        """
        Generate a comprehensive changelog.md file detailing the export session.
        
        Args:
            export_filepath: Path to the Excel export file (changelog will be created in same directory)
        """
        export_path = Path(export_filepath)
        changelog_path = export_path.parent / "changelog.md"
        
        # Get session information from database
        with get_connection() as conn:
            # Get compounds info
            compounds_query = """
                SELECT compound_name, retention_time, loffset, roffset, mass0, 
                       label_atoms, formula, label_type, tbdms, meox, me,
                       amount_in_std_mix, int_std_amount, mm_files
                FROM compounds 
                WHERE deleted = 0 
                ORDER BY compound_name
            """
            compounds = conn.execute(compounds_query).fetchall()
            
            # Get samples info
            samples_query = """
                SELECT sample_name, file_name 
                FROM samples 
                WHERE deleted = 0 
                ORDER BY sample_name
            """
            samples = conn.execute(samples_query).fetchall()
            
            # Get session activity (parameter overrides)
            session_query = """
                SELECT compound_name, sample_name, retention_time, loffset, roffset
                FROM session_activity 
                WHERE sample_deleted = 0
                ORDER BY compound_name, sample_name
            """
            session_overrides = conn.execute(session_query).fetchall()

        # Generate changelog content
        changelog_content = f"""# MANIC Export Session Changelog

## Export Information
- **Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **MANIC Version:** {__version__}
- **Export File:** {export_path.name}
- **Internal Standard:** {self.internal_standard_compound or 'None selected'}

## Processing Settings
- **Mass Tolerance Method:** Asymmetric offset + rounding (MANIC original method)
- **Integration Method:** {"Legacy Unit-Spacing (MATLAB Compatible)" if self.use_legacy_integration else "Time-based integration (scientifically accurate)"}
- **Expected Value Scale:** {"~100× larger than time-based method" if self.use_legacy_integration else "Physically meaningful units"}
- **Natural Isotope Correction:** Applied to all compounds with label_atoms > 0
- **Internal Standard Handling:** Raw values copied directly for label_atoms = 0

## Data Summary
- **Total Compounds:** {len(compounds)}
- **Total Samples:** {len(samples)}
- **Session Parameter Overrides:** {len(session_overrides)}

## Compounds Processed
| Compound Name | RT (min) | L Offset | R Offset | Mass (m/z) | Label Atoms | Formula | Internal Std Amount |
|---------------|----------|----------|----------|------------|-------------|---------|-------------------|
"""
        
        for compound in compounds:
            int_std = compound['int_std_amount'] if compound['int_std_amount'] else 'N/A'
            changelog_content += f"| {compound['compound_name']} | {compound['retention_time']:.3f} | {compound['loffset']:.3f} | {compound['roffset']:.3f} | {compound['mass0']:.4f} | {compound['label_atoms']} | {compound['formula'] or 'N/A'} | {int_std} |\n"
        
        changelog_content += f"\n## Sample Files Processed\n"
        for sample in samples:
            file_name = sample['file_name'] if sample['file_name'] else 'N/A'
            changelog_content += f"- **{sample['sample_name']}**: {file_name}\n"
        
        if session_overrides:
            changelog_content += f"\n## Session Parameter Overrides\n"
            changelog_content += f"The following compounds had their parameters modified during the session:\n\n"
            changelog_content += f"| Compound | Sample | RT Override | L Offset Override | R Offset Override |\n"
            changelog_content += f"|----------|--------|-------------|-------------------|-------------------|\n"
            
            for override in session_overrides:
                changelog_content += f"| {override['compound_name']} | {override['sample_name']} | {override['retention_time']:.3f} | {override['loffset']:.3f} | {override['roffset']:.3f} |\n"
        
        changelog_content += f"""
## Export Sheets Generated
1. **Raw Values** - Direct instrument signals (uncorrected peak areas using {"legacy unit-spacing" if self.use_legacy_integration else "time-based"} integration)
2. **Corrected Values** - Natural isotope abundance corrected signals
3. **Isotope Ratios** - Normalized corrected values (fractions sum to 1.0)  
4. **% Label Incorporation** - Percentage of experimental label incorporation
5. **Abundances** - Absolute metabolite concentrations via internal standard calibration

## Key Processing Notes
- Integration boundaries determined by compound-specific loffset/roffset values
- Inclusive boundaries (time >= l_boundary & time <= r_boundary) to match MATLAB exports
- Compound-specific MM file patterns used for standard mixture identification
- {"Legacy unit-spacing integration matches MATLAB MANIC (larger numerical values)" if self.use_legacy_integration else "Time-based integration produces physically meaningful results with proper units"}
- Natural isotope correction applied using high-performance algorithms for accuracy

## Session Changes Made
This export represents the final state of all data processing and parameter adjustments made during the session. All parameter overrides and corrections have been applied to generate the most accurate quantitative results possible.

---
*Generated automatically by MANIC v{__version__}*
"""

        # Write changelog file
        try:
            with open(changelog_path, 'w', encoding='utf-8') as f:
                f.write(changelog_content)
            logger.info(f"Changelog generated: {changelog_path}")
        except Exception as e:
            logger.error(f"Failed to generate changelog: {e}")
        
    def export_to_excel(self, filepath: str, progress_callback=None, use_legacy_integration: Optional[bool] = None) -> bool:
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
            logger.info(f"Starting Excel export to {filepath}")

            # Optional per-call override of integration mode
            if use_legacy_integration is not None:
                self.use_legacy_integration = use_legacy_integration
            
            # Create Excel workbook with optimization settings
            workbook = xlsxwriter.Workbook(filepath, {
                'constant_memory': True,  # Optimize for low RAM usage
                'use_zip64': True,       # Handle large files
            })
            
            # Create all worksheets
            progress = 0
            if progress_callback:
                progress_callback(progress)
                
            # Sheet 1: Raw Values (20% of work)
            self._export_raw_values_sheet(workbook, progress_callback, 0, 20)
            
            # Sheet 2: Corrected Values (20% of work)
            self._export_corrected_values_sheet(workbook, progress_callback, 20, 40)
            
            # Sheet 3: Isotope Ratios (20% of work)
            self._export_isotope_ratios_sheet(workbook, progress_callback, 40, 60)
            
            # Sheet 4: % Label Incorporation (20% of work)
            try:
                self._export_label_incorporation_sheet(workbook, progress_callback, 60, 80)
            except Exception as e:
                logger.error(f"Error in % Label Incorporation sheet: {e}")
                raise
            
            # Sheet 5: Abundances (20% of work) - Final sheet for easy access
            self._export_abundances_sheet(workbook, progress_callback, 80, 100)
            
            workbook.close()
            
            if progress_callback:
                progress_callback(100)
                
            logger.info(f"Excel export completed successfully: {filepath}")
            
            # Generate changelog
            self._generate_changelog(filepath)
            
            return True
            
        except Exception as e:
            logger.error(f"Excel export failed: {str(e)}")
            # Clean up partial file if it exists
            try:
                Path(filepath).unlink(missing_ok=True)
            except:
                pass
            raise
    
    def _export_raw_values_sheet(self, workbook, progress_callback, start_progress, end_progress):
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
        worksheet = workbook.add_worksheet('Raw Values')
        
        # Get all compounds and their metadata in order
        with get_connection() as conn:
            compounds_query = """
                SELECT compound_name, label_atoms, mass0, retention_time, mm_files
                FROM compounds 
                WHERE deleted=0 
                ORDER BY id
            """
            compounds = list(conn.execute(compounds_query))
            
            samples = [row['sample_name'] for row in 
                      conn.execute("SELECT sample_name FROM samples WHERE deleted=0 ORDER BY sample_name")]
        
        # Build column structure - each compound creates multiple columns for isotopologues
        compound_names = []
        masses = []
        isotopes = []
        retention_times = []
        
        for compound_row in compounds:
            compound_name = compound_row['compound_name']
            label_atoms = compound_row['label_atoms'] or 0
            mass0 = compound_row['mass0'] or 0
            rt = compound_row['retention_time'] or 0
            
            num_isotopologues = label_atoms + 1
            
            for isotope_idx in range(num_isotopologues):
                compound_names.append(compound_name)
                masses.append(mass0)
                isotopes.append(isotope_idx)
                retention_times.append(rt)
        
        # Write the 4 header rows exactly as in the reference file
        
        # Row 1: Compound Name | None | [Compound names]
        worksheet.write(0, 0, 'Compound Name')
        worksheet.write(0, 1, None)
        for col, compound_name in enumerate(compound_names):
            worksheet.write(0, col + 2, compound_name)
        
        # Row 2: Mass | None | [Mass values]
        worksheet.write(1, 0, 'Mass')
        worksheet.write(1, 1, None)
        for col, mass in enumerate(masses):
            worksheet.write(1, col + 2, mass)
        
        # Row 3: Isotope | None | [Isotope indices]
        worksheet.write(2, 0, 'Isotope')
        worksheet.write(2, 1, None)
        for col, isotope in enumerate(isotopes):
            worksheet.write(2, col + 2, isotope)
        
        # Row 4: tR | None | [Retention times]
        worksheet.write(3, 0, 'tR')
        worksheet.write(3, 1, None)
        for col, rt in enumerate(retention_times):
            worksheet.write(3, col + 2, rt)
        
        # Rows 5+: None | [Sample names] | [Data values]
        for sample_idx, sample_name in enumerate(samples):
            row = 4 + sample_idx
            worksheet.write(row, 0, None)
            worksheet.write(row, 1, sample_name)
            
            # Get all raw data for this sample
            sample_data = self._get_sample_raw_data(sample_name)
            
            # Write data values in column order
            col = 2
            for compound_row in compounds:
                compound_name = compound_row['compound_name']
                label_atoms = compound_row['label_atoms'] or 0
                num_isotopologues = label_atoms + 1
                
                # Get isotopologue data for this compound
                isotopologue_data = sample_data.get(compound_name, [0.0] * num_isotopologues)
                
                # Write each isotopologue value
                for isotope_idx in range(num_isotopologues):
                    area_value = isotopologue_data[isotope_idx] if isotope_idx < len(isotopologue_data) else 0.0
                    worksheet.write(row, col, area_value)
                    col += 1
            
            # Update progress
            if progress_callback and (sample_idx + 1) % 5 == 0:
                progress = start_progress + (sample_idx + 1) / len(samples) * (end_progress - start_progress)
                progress_callback(int(progress))
    
    def _export_corrected_values_sheet(self, workbook, progress_callback, start_progress, end_progress):
        """
        Export Corrected Values sheet - natural isotope abundance corrected signals.
        
        Format matches the reference xlsx exactly (same as Raw Values).
        
        This data has the predictable signal from naturally occurring isotopes 
        mathematically removed using the compound's chemical formula correction matrix.
        This is the clean, deconvoluted signal representing true experimental labeling.
        """
        worksheet = workbook.add_worksheet('Corrected Values')
        
        # Get all compounds and their metadata in order
        with get_connection() as conn:
            compounds_query = """
                SELECT compound_name, label_atoms, mass0, retention_time, mm_files
                FROM compounds 
                WHERE deleted=0 
                ORDER BY id
            """
            compounds = list(conn.execute(compounds_query))
            
            samples = [row['sample_name'] for row in 
                      conn.execute("SELECT sample_name FROM samples WHERE deleted=0 ORDER BY sample_name")]
        
        # Build column structure - same as Raw Values
        compound_names = []
        masses = []
        isotopes = []
        retention_times = []
        
        for compound_row in compounds:
            compound_name = compound_row['compound_name']
            label_atoms = compound_row['label_atoms'] or 0
            mass0 = compound_row['mass0'] or 0
            rt = compound_row['retention_time'] or 0
            
            num_isotopologues = label_atoms + 1
            
            for isotope_idx in range(num_isotopologues):
                compound_names.append(compound_name)
                masses.append(mass0)
                isotopes.append(isotope_idx)
                retention_times.append(rt)
        
        # Write the 4 header rows exactly as in the reference file
        
        # Row 1: Compound Name | None | [Compound names]
        worksheet.write(0, 0, 'Compound Name')
        worksheet.write(0, 1, None)
        for col, compound_name in enumerate(compound_names):
            worksheet.write(0, col + 2, compound_name)
        
        # Row 2: Mass | None | [Mass values]
        worksheet.write(1, 0, 'Mass')
        worksheet.write(1, 1, None)
        for col, mass in enumerate(masses):
            worksheet.write(1, col + 2, mass)
        
        # Row 3: Isotope | None | [Isotope indices]
        worksheet.write(2, 0, 'Isotope')
        worksheet.write(2, 1, None)
        for col, isotope in enumerate(isotopes):
            worksheet.write(2, col + 2, isotope)
        
        # Row 4: tR | None | [Retention times]
        worksheet.write(3, 0, 'tR')
        worksheet.write(3, 1, None)
        for col, rt in enumerate(retention_times):
            worksheet.write(3, col + 2, rt)
        
        # Rows 5+: None | [Sample names] | [Corrected data values]
        for sample_idx, sample_name in enumerate(samples):
            row = 4 + sample_idx
            worksheet.write(row, 0, None)
            worksheet.write(row, 1, sample_name)
            
            # Get all corrected data for this sample
            sample_data = self._get_sample_corrected_data(sample_name)
            
            # Write data values in column order
            col = 2
            for compound_row in compounds:
                compound_name = compound_row['compound_name']
                label_atoms = compound_row['label_atoms'] or 0
                num_isotopologues = label_atoms + 1
                
                # Get isotopologue data for this compound
                isotopologue_data = sample_data.get(compound_name, [0.0] * num_isotopologues)
                
                # Write each isotopologue value
                for isotope_idx in range(num_isotopologues):
                    area_value = isotopologue_data[isotope_idx] if isotope_idx < len(isotopologue_data) else 0.0
                    worksheet.write(row, col, area_value)
                    col += 1
            
            # Update progress
            if progress_callback and (sample_idx + 1) % 5 == 0:
                progress = start_progress + (sample_idx + 1) / len(samples) * (end_progress - start_progress)
                progress_callback(int(progress))
    
    def _export_isotope_ratios_sheet(self, workbook, progress_callback, start_progress, end_progress):
        """
        Export Isotope Ratios sheet - normalized corrected values (sum to 1.0).
        
        Format matches the reference xlsx exactly (same structure as Raw Values and Corrected Values).
        
        Takes the Corrected Values data and normalizes it so all isotopologues 
        for a given compound sum to 1.0, showing the fractional distribution of the label.
        """
        worksheet = workbook.add_worksheet('Isotope Ratio')
        
        # Get all compounds and their metadata in order
        with get_connection() as conn:
            compounds_query = """
                SELECT compound_name, label_atoms, mass0, retention_time, mm_files
                FROM compounds 
                WHERE deleted=0 
                ORDER BY id
            """
            compounds = list(conn.execute(compounds_query))
            
            samples = [row['sample_name'] for row in 
                      conn.execute("SELECT sample_name FROM samples WHERE deleted=0 ORDER BY sample_name")]
        
        # Build column structure - same as Raw Values and Corrected Values
        compound_names = []
        masses = []
        isotopes = []
        retention_times = []
        
        for compound_row in compounds:
            compound_name = compound_row['compound_name']
            label_atoms = compound_row['label_atoms'] or 0
            mass0 = compound_row['mass0'] or 0
            rt = compound_row['retention_time'] or 0
            
            num_isotopologues = label_atoms + 1
            
            for isotope_idx in range(num_isotopologues):
                compound_names.append(compound_name)
                masses.append(mass0)
                isotopes.append(isotope_idx)
                retention_times.append(rt)
        
        # Write the 4 header rows exactly as in the reference file
        
        # Row 1: Compound Name | None | [Compound names]
        worksheet.write(0, 0, 'Compound Name')
        worksheet.write(0, 1, None)
        for col, compound_name in enumerate(compound_names):
            worksheet.write(0, col + 2, compound_name)
        
        # Row 2: Mass | None | [Mass values]
        worksheet.write(1, 0, 'Mass')
        worksheet.write(1, 1, None)
        for col, mass in enumerate(masses):
            worksheet.write(1, col + 2, mass)
        
        # Row 3: Isotope | None | [Isotope indices]
        worksheet.write(2, 0, 'Isotope')
        worksheet.write(2, 1, None)
        for col, isotope in enumerate(isotopes):
            worksheet.write(2, col + 2, isotope)
        
        # Row 4: tR | None | [Retention times]
        worksheet.write(3, 0, 'tR')
        worksheet.write(3, 1, None)
        for col, rt in enumerate(retention_times):
            worksheet.write(3, col + 2, rt)
        
        # Rows 5+: None | [Sample names] | [Isotope ratio values]
        for sample_idx, sample_name in enumerate(samples):
            row = 4 + sample_idx
            worksheet.write(row, 0, None)
            worksheet.write(row, 1, sample_name)
            
            # Get all corrected data for this sample
            sample_data = self._get_sample_corrected_data(sample_name)
            
            # Write normalized data values in column order
            col = 2
            for compound_row in compounds:
                compound_name = compound_row['compound_name']
                label_atoms = compound_row['label_atoms'] or 0
                num_isotopologues = label_atoms + 1
                
                # Get isotopologue data for this compound
                isotopologue_data = sample_data.get(compound_name, [0.0] * num_isotopologues)
                
                # Normalize isotopologue data to sum = 1.0
                total_area = sum(isotopologue_data)
                if total_area > 0:
                    ratios = [area / total_area for area in isotopologue_data]
                else:
                    ratios = [0.0] * num_isotopologues
                
                # Write each normalized ratio
                for isotope_idx in range(num_isotopologues):
                    ratio_value = ratios[isotope_idx] if isotope_idx < len(ratios) else 0.0
                    worksheet.write(row, col, ratio_value)
                    col += 1
            
            # Update progress
            if progress_callback and (sample_idx + 1) % 5 == 0:
                progress = start_progress + (sample_idx + 1) / len(samples) * (end_progress - start_progress)
                progress_callback(int(progress))
    
    def _export_abundances_sheet(self, workbook, progress_callback, start_progress, end_progress):
        """
        Export Abundances sheet - absolute metabolite concentrations.
        
        Format matches reference xlsx exactly:
        - Only M+0 isotopologue for each compound (total abundance)
        - Includes Units row after tR row
        - Uses compound-based structure (not isotopologue-based)
        
        Uses internal standard calibration to convert corrected signals into 
        absolute biological quantities.
        """
        worksheet = workbook.add_worksheet('Abundances')
        
        # Get all compounds and their metadata in order
        with get_connection() as conn:
            compounds_query = """
                SELECT compound_name, mass0, retention_time, amount_in_std_mix, int_std_amount, mm_files
                FROM compounds 
                WHERE deleted=0 
                ORDER BY id
            """
            compounds = list(conn.execute(compounds_query))
            
            samples = [row['sample_name'] for row in 
                      conn.execute("SELECT sample_name FROM samples WHERE deleted=0 ORDER BY sample_name")]
        
        # Build column structure - only M+0 for each compound (total abundance)
        compound_names = []
        masses = []
        retention_times = []
        
        for compound_row in compounds:
            compound_name = compound_row['compound_name']
            mass0 = compound_row['mass0'] or 0
            rt = compound_row['retention_time'] or 0
            
            compound_names.append(compound_name)
            masses.append(mass0)
            retention_times.append(rt)
        
        # Write the 5 header rows (Abundances has an extra Units row)
        
        # Row 1: Compound Name | None | [Compound names]
        worksheet.write(0, 0, 'Compound Name')
        worksheet.write(0, 1, None)
        for col, compound_name in enumerate(compound_names):
            worksheet.write(0, col + 2, compound_name)
        
        # Row 2: Mass | None | [Mass values]
        worksheet.write(1, 0, 'Mass')
        worksheet.write(1, 1, None)
        for col, mass in enumerate(masses):
            worksheet.write(1, col + 2, mass)
        
        # Row 3: Isotope | None | [All zeros - only M+0 for abundances]
        worksheet.write(2, 0, 'Isotope')
        worksheet.write(2, 1, None)
        for col in range(len(compound_names)):
            worksheet.write(2, col + 2, 0)
        
        # Row 4: tR | None | [Retention times]
        worksheet.write(3, 0, 'tR')
        worksheet.write(3, 1, None)
        for col, rt in enumerate(retention_times):
            worksheet.write(3, col + 2, rt)
        
        # Row 5: Units | None | [Unit labels - "nmol" for all compounds]
        worksheet.write(4, 0, 'Units')
        worksheet.write(4, 1, None)
        for col in range(len(compound_names)):
            worksheet.write(4, col + 2, 'nmol')  # Default unit
        
        # Pre-calculate MRRF values using MM files and internal standard
        if not self.internal_standard_compound:
            logger.warning("No internal standard selected - using raw abundance values")
            mrrf_values = {}
            internal_std_amount = 1.0  # Default fallback
        else:
            logger.info(f"Calculating MRRF values using internal standard: {self.internal_standard_compound}")
            mrrf_values = self._calculate_mrrf_values(compounds, self.internal_standard_compound)
            
            # Get internal standard amount from compound metadata
            with get_connection() as conn:
                cursor = conn.execute(
                    "SELECT int_std_amount FROM compounds WHERE compound_name = ? AND deleted = 0",
                    (self.internal_standard_compound,)
                )
                row = cursor.fetchone()
                try:
                    internal_std_amount = row['int_std_amount'] if row and row['int_std_amount'] is not None else 1.0
                except (KeyError, TypeError):
                    internal_std_amount = 1.0
                    logger.debug(f"int_std_amount not found for {self.internal_standard_compound}, using default 1.0")
        
        # Rows 6+: None | [Sample names] | [Calibrated abundance values]
        for sample_idx, sample_name in enumerate(samples):
            row = 5 + sample_idx
            worksheet.write(row, 0, None)
            worksheet.write(row, 1, sample_name)
            
            # Get all corrected data for this sample
            sample_data = self._get_sample_corrected_data(sample_name)
            
            # Get internal standard signal in this sample (total signal - sum of all isotopologues)
            if self.internal_standard_compound:
                internal_std_data = sample_data.get(self.internal_standard_compound, [0.0])
                internal_std_signal = sum(internal_std_data) if internal_std_data else 0.0
            else:
                internal_std_signal = 1.0  # Avoid division by zero
            
            # Write calibrated abundance values
            for col, compound_row in enumerate(compounds):
                compound_name = compound_row['compound_name']
                
                # Get isotopologue data and sum for total abundance
                isotopologue_data = sample_data.get(compound_name, [0.0])
                total_signal = sum(isotopologue_data)  # Sum all isotopologues
                
                if self.internal_standard_compound and compound_name != self.internal_standard_compound:
                    # Apply MRRF calibration to get abundance in nmol
                    # Abundance = Total_Signal_In_Sample * (IntStd_Amount / IntStd_Signal_In_Sample) * (1 / MRRF)
                    mrrf = mrrf_values.get(compound_name, 1.0)
                    
                    if internal_std_signal > 0 and mrrf > 0:
                        # Calculate final abundance in nmol
                        calibrated_abundance = total_signal * (internal_std_amount / internal_std_signal) * (1 / mrrf)
                        logger.debug(f"Abundance for {compound_name}: total_signal={total_signal:.1f}, "
                                   f"int_std_amount={internal_std_amount}, int_std_signal={internal_std_signal:.1f}, "
                                   f"mrrf={mrrf:.3f}, result={calibrated_abundance:.3f} nmol")
                    else:
                        calibrated_abundance = 0.0  # No valid calibration data
                        logger.debug(f"No valid calibration for {compound_name} (int_std_signal={internal_std_signal:.3f}, mrrf={mrrf:.3f})")
                elif self.internal_standard_compound and compound_name == self.internal_standard_compound:
                    # For internal standard itself, the abundance should be the known amount added
                    calibrated_abundance = internal_std_amount if internal_std_amount > 0 else 0.0
                    logger.debug(f"Internal standard {compound_name} abundance: {calibrated_abundance} nmol (known amount)")
                else:
                    # No internal standard calibration - return raw signal or 0
                    calibrated_abundance = 0.0
                    logger.debug(f"No internal standard calibration available for {compound_name}")
                
                worksheet.write(row, col + 2, calibrated_abundance)
            
            # Update progress
            if progress_callback and (sample_idx + 1) % 5 == 0:
                progress = start_progress + (sample_idx + 1) / len(samples) * (end_progress - start_progress)
                progress_callback(int(progress))
        
        if self.internal_standard_compound:
            logger.info("Abundances sheet created with MRRF calibration applied")
        else:
            logger.info("Abundances sheet created with raw abundance values (no internal standard)")
    
    def _export_label_incorporation_sheet(self, workbook, progress_callback, start_progress, end_progress):
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
        worksheet = workbook.add_worksheet('% Label Incorporation')
        
        # Get all compounds and their metadata in order
        with get_connection() as conn:
            compounds_query = """
                SELECT compound_name, mass0, retention_time, label_atoms, amount_in_std_mix, int_std_amount, mm_files
                FROM compounds 
                WHERE deleted=0 
                ORDER BY id
            """
            compounds = list(conn.execute(compounds_query))
            
            samples = [row['sample_name'] for row in 
                      conn.execute("SELECT sample_name FROM samples WHERE deleted=0 ORDER BY sample_name")]
        
        # Build column structure - only compounds with labeling (M+0 base)
        compound_names = []
        masses = []
        retention_times = []
        
        for compound_row in compounds:
            compound_name = compound_row['compound_name']
            mass0 = compound_row['mass0'] or 0
            rt = compound_row['retention_time'] or 0
            
            compound_names.append(compound_name)
            masses.append(mass0)
            retention_times.append(rt)
        
        # Write the 4 header rows (same as Raw Values, Corrected Values, Isotope Ratio)
        
        # Row 1: Compound Name | None | [Compound names]
        worksheet.write(0, 0, 'Compound Name')
        worksheet.write(0, 1, None)
        for col, compound_name in enumerate(compound_names):
            worksheet.write(0, col + 2, compound_name)
        
        # Row 2: Mass | None | [Mass values]
        worksheet.write(1, 0, 'Mass')
        worksheet.write(1, 1, None)
        for col, mass in enumerate(masses):
            worksheet.write(1, col + 2, mass)
        
        # Row 3: Isotope | None | [All zeros - only M+0 for % label calculation]
        worksheet.write(2, 0, 'Isotope')
        worksheet.write(2, 1, None)
        for col in range(len(compound_names)):
            worksheet.write(2, col + 2, 0)
        
        # Row 4: tR | None | [Retention times]
        worksheet.write(3, 0, 'tR')
        worksheet.write(3, 1, None)
        for col, rt in enumerate(retention_times):
            worksheet.write(3, col + 2, rt)
        
        # Pre-calculate background ratios from MM files (standard samples)
        logger.info("Calculating background ratios from MM files for % label incorporation...")
        background_ratios = self._calculate_background_ratios(compounds)
        
        # Rows 5+: None | [Sample names] | [% Label Incorporation values]
        for sample_idx, sample_name in enumerate(samples):
            row = 4 + sample_idx
            worksheet.write(row, 0, None)
            worksheet.write(row, 1, sample_name)
            
            # Get all corrected data for this sample
            sample_data = self._get_sample_corrected_data(sample_name)
            
            # Write % label incorporation values
            for col, compound_row in enumerate(compounds):
                try:
                    compound_name = compound_row['compound_name']
                except (KeyError, IndexError) as e:
                    logger.error(f"Error accessing compound_name for compound {col}: {e}")
                    continue
                
                # Get isotopologue data for this compound
                isotopologue_data = sample_data.get(compound_name, [0.0])
                
                # Calculate % label incorporation with background correction
                if len(isotopologue_data) > 1:
                    m0_signal = isotopologue_data[0]  # Unlabeled (M+0)
                    raw_labeled_signal = sum(isotopologue_data[1:])  # Sum of M+1, M+2, etc.
                    
                    # Apply background correction using MM files
                    background_ratio = background_ratios.get(compound_name, 0.0)
                    corrected_labeled_signal = raw_labeled_signal - (background_ratio * m0_signal)
                    
                    # Ensure corrected signal is not negative
                    corrected_labeled_signal = max(0.0, corrected_labeled_signal)
                    
                    total_signal = m0_signal + corrected_labeled_signal
                    
                    if total_signal > 0:
                        label_percentage = (corrected_labeled_signal / total_signal) * 100
                    else:
                        label_percentage = 0.0
                else:
                    # No isotopologues, no labeling possible
                    label_percentage = 0.0
                
                worksheet.write(row, col + 2, label_percentage)
            
            # Update progress
            if progress_callback and (sample_idx + 1) % 5 == 0:
                progress = start_progress + (sample_idx + 1) / len(samples) * (end_progress - start_progress)
                progress_callback(int(progress))
        
        logger.info("% Label Incorporation sheet created with background correction applied")
    
    def _calculate_background_ratios(self, compounds) -> Dict[str, float]:
        """
        Calculate background ratios from MM files (standard mixture samples).
        
        Background_Ratio = Mean_Labelled_Signal_in_Standards / Mean_Unlabelled_Signal_in_Standards
        
        Args:
            compounds: List of compound database rows
            
        Returns:
            Dictionary mapping compound names to background ratios
        """
        background_ratios = {}
        
        # Calculate background ratio for each compound using its specific MM files
        for compound_row in compounds:
            compound_name = compound_row['compound_name']
            label_atoms = compound_row['label_atoms'] or 0
            mm_files_field = compound_row['mm_files'] if compound_row['mm_files'] is not None else ''

            # Resolve samples from possibly multiple mm_files patterns
            mm_samples = self._resolve_mm_samples(mm_files_field)

            if not mm_samples:
                logger.warning(f"No MM files found for compound {compound_name} with patterns '{mm_files_field}'")
                background_ratios[compound_name] = 0.0
                continue

            logger.info(f"Found {len(mm_samples)} MM files for {compound_name} with patterns '{mm_files_field}': {mm_samples}")
            
            if label_atoms == 0:
                # No isotopologues, no background correction needed
                background_ratios[compound_name] = 0.0
                continue
            
            mm_unlabeled_signals = []
            mm_labeled_signals = []
            
            # Get data from all MM files for this compound
            for mm_sample in mm_samples:
                sample_data = self._get_sample_corrected_data(mm_sample)
                isotopologue_data = sample_data.get(compound_name, [0.0] * (label_atoms + 1))
                
                if len(isotopologue_data) > 1:
                    unlabeled_signal = isotopologue_data[0]  # M+0
                    labeled_signal = sum(isotopologue_data[1:])  # M+1, M+2, etc.
                    
                    mm_unlabeled_signals.append(unlabeled_signal)
                    mm_labeled_signals.append(labeled_signal)
            
            # Calculate mean signals and background ratio
            if mm_unlabeled_signals and mm_labeled_signals:
                mean_unlabeled = sum(mm_unlabeled_signals) / len(mm_unlabeled_signals)
                mean_labeled = sum(mm_labeled_signals) / len(mm_labeled_signals)
                
                if mean_unlabeled > 0:
                    background_ratio = mean_labeled / mean_unlabeled
                else:
                    background_ratio = 0.0
                
                background_ratios[compound_name] = background_ratio
                logger.debug(f"Background ratio for {compound_name}: {background_ratio:.6f}")
            else:
                background_ratios[compound_name] = 0.0
        
        return background_ratios
    
    def _calculate_mrrf_values(self, compounds, internal_standard_compound: str) -> Dict[str, float]:
        """
        Calculate MRRF (Metabolite Response Ratio Factor) values using MM files.
        
        MATLAB-compatible approach:
        - Numerator uses the metabolite's own MM set
        - Denominator uses the internal standard's own MM set
        
        MRRF = (Metabolite_Standard_Signal / Metabolite_Standard_Concentration) / 
               (Internal_Standard_Signal / Internal_Standard_Concentration)
        
        Args:
            compounds: List of compound database rows
            internal_standard_compound: Name of internal standard compound
            
        Returns:
            Dictionary mapping compound names to MRRF values
        """
        mrrf_values = {}
        
        # Get internal standard concentration from compound metadata 
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT amount_in_std_mix FROM compounds WHERE compound_name = ? AND deleted = 0",
                (internal_standard_compound,)
            )
            row = cursor.fetchone()
            try:
                internal_std_concentration = row['amount_in_std_mix'] if row and row['amount_in_std_mix'] is not None else 1.0
            except (KeyError, TypeError):
                internal_std_concentration = 1.0
                logger.debug(f"amount_in_std_mix not found for internal standard {internal_standard_compound}, using default 1.0")

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
        internal_std_mm_samples = self._resolve_mm_samples(internal_std_mm_field)

        # Calculate MRRF for each compound using metabolite's MM set (numerator)
        # and the internal standard's own MM set (denominator)
        for compound_row in compounds:
            compound_name = compound_row['compound_name']
            
            if compound_name == internal_standard_compound:
                # Internal standard has MRRF = 1.0 by definition
                mrrf_values[compound_name] = 1.0
                continue
            
            # Get compound-specific MM files 
            compound_mm_field = compound_row['mm_files'] if compound_row['mm_files'] is not None else ''
            if not compound_mm_field:
                logger.warning(f"No MM files pattern specified for compound {compound_name}")
                mrrf_values[compound_name] = 1.0
                continue
            
            compound_mm_samples = self._resolve_mm_samples(compound_mm_field)

            if not compound_mm_samples:
                logger.warning(f"No MM files found for compound {compound_name} with patterns '{compound_mm_field}'")
                mrrf_values[compound_name] = 1.0
                continue
            
            # Numerator: metabolite mean over its own MM sample set
            metabolite_signals = []
            for mm_sample in compound_mm_samples:
                sample_data = self._get_sample_corrected_data(mm_sample)
                
                # Get metabolite signal from this MM sample
                isotopologue_data = sample_data.get(compound_name, [0.0])
                metabolite_signal = sum(isotopologue_data) if isotopologue_data else 0.0
                metabolite_signals.append(metabolite_signal)

            # Denominator: internal standard mean over ITS OWN MM sample set
            internal_std_signals = []
            for mm_sample in internal_std_mm_samples:
                sample_data = self._get_sample_corrected_data(mm_sample)
                internal_std_data = sample_data.get(internal_standard_compound, [0.0])
                internal_std_signal = sum(internal_std_data) if internal_std_data else 0.0
                internal_std_signals.append(internal_std_signal)

            # Use MEANS (Python legacy behavior)
            mean_metabolite_signal = (sum(metabolite_signals) / len(metabolite_signals)) if metabolite_signals else 0.0
            mean_internal_std_signal = (sum(internal_std_signals) / len(internal_std_signals)) if internal_std_signals else 0.0

            logger.debug(
                f"MRRF calc for {compound_name}: mean_metabolite={mean_metabolite_signal:.3f} (n={len(metabolite_signals)}), "
                f"mean_internal_std={mean_internal_std_signal:.3f} (n={len(internal_std_signals)})"
            )
            
            # Get metabolite standard concentration from compound metadata
            try:
                amount_in_std_mix = compound_row['amount_in_std_mix']
                metabolite_std_concentration = amount_in_std_mix if amount_in_std_mix is not None else 1.0
            except (KeyError, IndexError):
                metabolite_std_concentration = 1.0
                logger.debug(f"amount_in_std_mix not found for {compound_name}, using default 1.0")
            
            # Calculate MRRF using MEANS
            if mean_metabolite_signal > 0 and metabolite_std_concentration > 0 and mean_internal_std_signal > 0 and internal_std_concentration > 0:
                mrrf = (mean_metabolite_signal / metabolite_std_concentration) / (mean_internal_std_signal / internal_std_concentration)
                mrrf_values[compound_name] = mrrf
                logger.debug(f"MRRF for {compound_name}: {mrrf:.6f} (using MEANS)")
            else:
                # Fallback to 1.0 if calculation fails
                mrrf_values[compound_name] = 1.0
                logger.warning(f"Could not calculate MRRF for {compound_name}, using 1.0. "
                             f"mean_metabolite_signal={mean_metabolite_signal:.3f}, "
                             f"metabolite_std_concentration={metabolite_std_concentration}, "
                             f"mean_internal_std_signal={mean_internal_std_signal:.3f}, "
                             f"internal_std_concentration={internal_std_concentration}")
        
        return mrrf_values
    
    def _calculate_peak_areas(self, time_data: np.ndarray, intensity_data: np.ndarray, label_atoms: int, 
                              retention_time: float = None, loffset: float = None, roffset: float = None) -> List[float]:
        """
        Calculate integrated peak areas for each isotopologue from EIC data.
        
        Args:
            time_data: Array of retention times
            intensity_data: Array of intensities (may be multi-dimensional for isotopologues)
            label_atoms: Number of labeled atoms (determines isotopologue count)
            retention_time: Compound retention time (minutes)
            loffset: Left integration boundary offset (minutes)  
            roffset: Right integration boundary offset (minutes)
            
        Returns:
            List of integrated peak areas for M+0, M+1, M+2, etc.
        """
        # Helper function to apply integration boundaries
        def apply_integration_boundaries(time_data, intensity_data):
            if retention_time is not None and loffset is not None and roffset is not None:
                l_boundary = retention_time - loffset
                r_boundary = retention_time + roffset
                
                # Debug logging to understand integration window sizes
                original_points = len(time_data)
                time_range = (time_data.max() - time_data.min()) if len(time_data) > 0 else 0
                window_size = r_boundary - l_boundary
                
                # Inclusive boundaries to match MATLAB behavior
                integration_mask = (time_data >= l_boundary) & (time_data <= r_boundary)
                points_in_window = np.sum(integration_mask)
                
                logger.debug(f"Integration boundaries: rt={retention_time:.3f}, loffset={loffset:.3f}, roffset={roffset:.3f}")
                logger.debug(f"Boundaries: {l_boundary:.3f} to {r_boundary:.3f} (window={window_size:.3f} min)")
                logger.debug(f"Data points: {points_in_window}/{original_points} in window (time_range={time_range:.3f} min)")
                
                # Apply mask to trim data to integration window
                if np.any(integration_mask):
                    time_data = time_data[integration_mask]
                    if intensity_data.ndim == 1:
                        intensity_data = intensity_data[integration_mask]
                    else:
                        # For multi-dimensional data, apply mask to time axis (last dimension)
                        intensity_data = intensity_data[..., integration_mask]
                    return time_data, intensity_data
                else:
                    # No data in integration window - return empty arrays
                    logger.warning(f"No data points in integration window {l_boundary:.3f} to {r_boundary:.3f}")
                    return np.array([]), np.array([])
            return time_data, intensity_data
            
        num_isotopologues = label_atoms + 1
        
        # Check if this compound has isotopologues (labeled atoms > 0)
        if label_atoms == 0:
            # Unlabeled compound - single trace
            # Apply integration boundaries
            time_data, intensity_data = apply_integration_boundaries(time_data, intensity_data)
            if len(time_data) == 0:
                return [0.0]
            # Integrate using selected method (time-based or legacy unit-spacing)
            peak_area = self._integrate_peak(intensity_data, time_data)
            return [float(peak_area)]
        else:
            # Labeled compound - multiple isotopologue traces
            # Intensity data should be reshaped to (num_isotopologues, num_time_points)
            num_time_points = len(time_data)
            
            try:
                # Reshape intensity data for isotopologues FIRST
                intensity_reshaped = intensity_data.reshape(num_isotopologues, num_time_points)
                
                # THEN apply integration boundaries to the reshaped data
                time_data, intensity_reshaped = apply_integration_boundaries(time_data, intensity_reshaped)
                if len(time_data) == 0:
                    return [0.0] * num_isotopologues
                
                # Integrate each isotopologue using selected method
                peak_areas = []
                for i in range(num_isotopologues):
                    peak_area = self._integrate_peak(intensity_reshaped[i], time_data)
                    peak_areas.append(float(peak_area))
                return peak_areas
                
            except ValueError as e:
                # If reshaping fails, log the issue and return zeros
                logger.warning(f"Failed to reshape intensity data for isotopologue integration. "
                             f"Expected shape: ({num_isotopologues}, {num_time_points}), "
                             f"Got total elements: {len(intensity_data)}. Error: {e}")
                # Return zero areas for all isotopologues
                return [0.0] * num_isotopologues
    
    def _get_total_sample_count(self) -> int:
        """Get total number of active samples for progress calculation."""
        with get_connection() as conn:
            result = conn.execute("SELECT COUNT(*) FROM samples WHERE deleted=0").fetchone()
            return result[0] if result else 0
    
    
    def _get_sample_raw_data(self, sample_name: str) -> Dict[str, List[float]]:
        """
        Get integrated raw EIC data for all compounds in a sample.
        
        Args:
            sample_name: Name of the sample
            
        Returns:
            Dictionary mapping compound names to lists of isotopologue peak areas
        """
        sample_data = {}
        
        with get_connection() as conn:
            # Debug: Check what compounds exist in this sample
            compound_check = conn.execute(
                "SELECT DISTINCT e.compound_name FROM eic e WHERE e.sample_name = ? AND e.deleted = 0 ORDER BY e.compound_name", 
                (sample_name,)
            ).fetchall()
            available_compounds = [row['compound_name'] for row in compound_check]
            logger.info(f"Raw EIC compounds in {sample_name}: {available_compounds[:10]}...")  # Show first 10
            
            # Get all EIC data for this sample with integration boundaries
            eic_query = """
                SELECT e.compound_name, e.x_axis, e.y_axis, c.label_atoms, c.retention_time, c.loffset, c.roffset
                FROM eic e
                JOIN compounds c ON e.compound_name = c.compound_name
                WHERE e.sample_name = ? AND e.deleted = 0 AND c.deleted = 0
                ORDER BY e.compound_name
            """
            
            for row in conn.execute(eic_query, (sample_name,)):
                compound_name = row['compound_name']
                label_atoms = row['label_atoms']
                retention_time = row['retention_time']
                loffset = row['loffset']
                roffset = row['roffset']
                
                # Decompress and integrate the raw EIC data
                time_data = np.frombuffer(zlib.decompress(row['x_axis']), dtype=np.float64)
                intensity_data = np.frombuffer(zlib.decompress(row['y_axis']), dtype=np.float64)
                
                # Calculate integrated peak areas using compound-specific integration boundaries
                peak_areas = self._calculate_peak_areas(time_data, intensity_data, label_atoms, retention_time, loffset, roffset)
                sample_data[compound_name] = peak_areas
                
        
        return sample_data
    
    def _get_sample_corrected_data(self, sample_name: str) -> Dict[str, List[float]]:
        """
        Get integrated EIC data for all compounds in a sample.
        
        For labeled compounds (label_atoms > 0): fetches corrected data from eic_corrected table
        For unlabeled compounds (label_atoms = 0): fetches raw data directly from eic table
        
        This approach is more robust as it doesn't depend on the eic_corrected table being
        properly populated for unlabeled compounds (internal standards).
        
        Args:
            sample_name: Name of the sample
            
        Returns:
            Dictionary mapping compound names to lists of isotopologue peak areas
        """
        sample_data = {}
        
        with get_connection() as conn:
            # Get all compounds that should have EIC data in this sample
            all_compounds_query = """
                SELECT DISTINCT c.compound_name, c.label_atoms, c.retention_time, c.loffset, c.roffset
                FROM compounds c
                WHERE c.deleted = 0
                AND (
                    EXISTS (SELECT 1 FROM eic e WHERE e.compound_name = c.compound_name AND e.sample_name = ? AND e.deleted = 0)
                    OR EXISTS (SELECT 1 FROM eic_corrected ec WHERE ec.compound_name = c.compound_name AND ec.sample_name = ? AND ec.deleted = 0)
                )
                ORDER BY c.compound_name
            """
            
            for compound_row in conn.execute(all_compounds_query, (sample_name, sample_name)):
                compound_name = compound_row['compound_name']
                label_atoms = compound_row['label_atoms']
                retention_time = compound_row['retention_time']
                loffset = compound_row['loffset']
                roffset = compound_row['roffset']
                
                time_data = None
                intensity_data = None
                
                if label_atoms > 0:
                    # Labeled compound: fetch corrected data from eic_corrected table
                    corrected_query = """
                        SELECT x_axis, y_axis_corrected
                        FROM eic_corrected
                        WHERE sample_name = ? AND compound_name = ? AND deleted = 0
                        LIMIT 1
                    """
                    corrected_row = conn.execute(corrected_query, (sample_name, compound_name)).fetchone()
                    
                    if corrected_row:
                        time_data = np.frombuffer(zlib.decompress(corrected_row['x_axis']), dtype=np.float64)
                        intensity_data = np.frombuffer(zlib.decompress(corrected_row['y_axis_corrected']), dtype=np.float64)
                    else:
                        logger.warning(f"No corrected data found for labeled compound '{compound_name}' in sample '{sample_name}'")
                        continue
                
                else:
                    # Unlabeled compound (internal standard): fetch raw data directly from eic table
                    raw_query = """
                        SELECT x_axis, y_axis
                        FROM eic
                        WHERE sample_name = ? AND compound_name = ? AND deleted = 0
                        LIMIT 1
                    """
                    raw_row = conn.execute(raw_query, (sample_name, compound_name)).fetchone()
                    
                    if raw_row:
                        time_data = np.frombuffer(zlib.decompress(raw_row['x_axis']), dtype=np.float64)
                        intensity_data = np.frombuffer(zlib.decompress(raw_row['y_axis']), dtype=np.float64)
                    else:
                        logger.warning(f"No raw data found for unlabeled compound '{compound_name}' in sample '{sample_name}'")
                        continue
                
                # Calculate integrated peak areas using compound-specific integration boundaries
                if time_data is not None and intensity_data is not None:
                    peak_areas = self._calculate_peak_areas(time_data, intensity_data, label_atoms, retention_time, loffset, roffset)
                    sample_data[compound_name] = peak_areas
        
        return sample_data
