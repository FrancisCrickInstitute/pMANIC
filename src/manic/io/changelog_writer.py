from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from manic.__version__ import __version__
from manic.models.analysis import AnalysisMode
from manic.models.database import get_connection
from manic.io.changelog_sections import (
    format_compounds_table_for_data_export,
    format_overrides_section_for_data_export,
    format_unlabelled_compounds_table_for_data_export,
)

logger = logging.getLogger(__name__)


def generate_changelog(
    export_filepath: str,
    *,
    internal_standard: Optional[str],
    use_legacy_integration: bool,
    analysis_mode: AnalysisMode | str = AnalysisMode.LABELLED,
) -> None:
    """
    Generate a comprehensive changelog file with timestamp detailing the export session.
    """
    export_path = Path(export_filepath)
    mode = AnalysisMode.coerce(analysis_mode)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    changelog_path = export_path.parent / f"changelog_{timestamp}.md"

    # Get session information from database
    with get_connection() as conn:
        compounds_query = """
            SELECT compound_name, retention_time, loffset, roffset, mass0, rt_tolerance,
                   label_atoms, formula, label_type, tbdms, meox, me,
                   amount_in_std_mix, int_std_amount, mm_files, baseline_correction,
                   deconvolution_level, deconvolution_fit_type, deconvolution_noise_gate
            FROM compounds 
            WHERE deleted = 0 
            ORDER BY compound_name
        """
        compounds = conn.execute(compounds_query).fetchall()

        samples_query = """
            SELECT sample_name, file_name 
            FROM samples 
            WHERE deleted = 0 
            ORDER BY sample_name
        """
        samples = conn.execute(samples_query).fetchall()

        session_query = """
            SELECT compound_name, sample_name, retention_time, loffset, roffset
            FROM session_activity 
            WHERE sample_deleted = 0
            ORDER BY compound_name, sample_name
        """
        session_overrides = conn.execute(session_query).fetchall()

        # Get deleted items for audit trail
        deleted_compounds_query = """
            SELECT compound_name FROM compounds WHERE deleted = 1 ORDER BY compound_name
        """
        deleted_compounds = conn.execute(deleted_compounds_query).fetchall()

        deleted_samples_query = """
            SELECT sample_name FROM samples WHERE deleted = 1 ORDER BY sample_name
        """
        deleted_samples = conn.execute(deleted_samples_query).fetchall()
        diagnostic_ions = conn.execute(
            """
            SELECT ci.compound_name, ci.role, ci.ordinal, ci.mz,
                   ci.expected_ratio, ci.ratio_tolerance
            FROM compound_ions ci
            JOIN compounds c ON c.compound_name = ci.compound_name
            WHERE c.deleted = 0
            ORDER BY ci.compound_name,
                     CASE ci.role WHEN 'quantifier' THEN 0 ELSE 1 END,
                     ci.ordinal
            """
        ).fetchall()

    if mode is AnalysisMode.UNLABELLED:
        processing_description = """- **Diagnostic-ion workflow:** Amount uses Q-ion area only. V ions are identity evidence and are not added to amount
- **V-ion ratio:** Observed ratio is V-ion area / Q-ion area. A ratio passes when |observed - expected| <= |expected| * fractional tolerance. If expected is 0 the comparison is absolute
- **Observed RT:** Raw Q-ion apex inside the shared window [tR - lOffset, tR + rOffset], not a fitted-centre time
- **tR window:** Identity RT check uses the compound tR window. Offsets still set the integration window
- **Natural Isotope Correction:** Not applied. Q and V are diagnostic ions, not isotopologues
- **Quantitative claim:** Peak Area without an internal standard. With an IS, nmol when Amount in StdMix is set, otherwise Relative. Single-point response factor, not a calibration curve"""
        sheets_description = """1. **Raw Values** - One column per compound, Q-ion area only. `Mass` is the Q m/z. V-ion areas are on Qualifier QC
2. **Abundances** - One column per compound, Q-ion response only. Units row is Peak Area, nmol, or Relative
3. **Qualifier QC** - Q and V raw areas, observed V/Q, expected ratio, fractional tolerance, and PASS / REVIEW / N/A. Composite identity status and ΔRT stay in the Identity chart and are not in this workbook"""
        key_processing_notes = """- Integration uses the shared Q/V window [tR - lOffset, tR + rOffset]. A V peak outside that window integrates near zero and fails ratio QC
- Q-ion area alone supplies the analytical response. V-ion areas are identity evidence
- Current tR is used for integration and for the in-app identity RT check. Changing tR updates both. That RT check is not written to the workbook
- Natural-isotope correction is not applied. Q and V are diagnostic ions, not isotopologues
- Chromatographic peak deconvolution defaults to level 4, as in labelled mode. Each Q/V ion is fitted independently. If any Q or V ion of a compound in a sample fails to fit, every ion of that compound/sample uses raw-window areas so V/Q is never mixed measurement types
- Observed RT used for identity is the raw Q apex in the window, not the fitted-centre time"""
    else:
        processing_description = """- **Natural Isotope Correction:** Applied to all compounds with label_atoms > 0
- **Internal Standard Handling:** Raw values copied directly for label_atoms = 0"""
        sheets_description = f"""1. **Raw Values** - Direct instrument signals (uncorrected peak areas using {"legacy unit-spacing" if use_legacy_integration else "time-based"} integration)
2. **Corrected Values** - Natural isotope abundance corrected signals
3. **Isotope Ratios** - Normalized corrected values (fractions sum to 1.0)
4. **% Label Incorporation** - Percentage of experimental label incorporation
5. **Abundances** - Absolute metabolite concentrations via internal standard calibration"""
        key_processing_notes = """- Integration boundaries determined by compound-specific loffset/roffset values
- Natural-isotope correction applied to labelled isotopologue channels
- Peak-area validation uses the configured internal-standard reference isotopologue"""

    changelog_content = f"""# MANIC Export Session Changelog

## Export Information
- **Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **MANIC Version:** {__version__}
- **Analysis Mode:** {mode.display_name}
- **Export File:** {export_path.name}
- **Internal Standard:** {internal_standard or 'None selected'}

## Processing Settings
- **Mass Tolerance Method:** Asymmetric offset + rounding (MANIC original method)
- **Integration Method:** {"Legacy Unit-Spacing (MATLAB Compatible)" if use_legacy_integration else "Time-based integration (scientifically accurate)"}
- **Expected Value Scale:** {"~100× larger than time-based method" if use_legacy_integration else "Physically meaningful units"}
{processing_description}

## Data Summary
- **Total Compounds:** {len(compounds)}
- **Total Samples:** {len(samples)}
- **Deleted Compounds:** {len(deleted_compounds)}
- **Deleted Samples:** {len(deleted_samples)}
- **Session Parameter Overrides:** {len(session_overrides)}

"""

    # Deleted Items section (only if any exist)
    if deleted_compounds or deleted_samples:
        changelog_content += "## Deleted Items\n"
        changelog_content += "The following items were excluded from this export:\n\n"
        
        if deleted_compounds:
            changelog_content += f"### Deleted Compounds ({len(deleted_compounds)})\n"
            for compound in deleted_compounds:
                changelog_content += f"- {compound['compound_name']}\n"
            changelog_content += "\n"
        
        if deleted_samples:
            changelog_content += f"### Deleted Samples ({len(deleted_samples)})\n"
            for sample in deleted_samples:
                changelog_content += f"- {sample['sample_name']}\n"
            changelog_content += "\n"

    # Compounds table
    if mode is AnalysisMode.UNLABELLED:
        changelog_content += (
            format_unlabelled_compounds_table_for_data_export(compounds) + "\n"
        )
    else:
        changelog_content += format_compounds_table_for_data_export(compounds) + "\n"

    if diagnostic_ions:
        changelog_content += "\n## Diagnostic Ion Definitions\n\n"
        changelog_content += "| Compound | Role | Ordinal | m/z | Expected Ratio | Fractional Tolerance |\n"
        changelog_content += "|---|---|---:|---:|---:|---:|\n"
        for ion in diagnostic_ions:
            changelog_content += (
                f"| {ion['compound_name']} | {ion['role']} | {ion['ordinal']} | "
                f"{ion['mz']:.4g} | {ion['expected_ratio'] if ion['expected_ratio'] is not None else 'N/A'} | "
                f"{ion['ratio_tolerance'] if ion['ratio_tolerance'] is not None else 'N/A'} |\n"
            )

    changelog_content += "\n## Sample Files Processed\n"
    for sample in samples:
        file_name = sample['file_name'] if sample['file_name'] else 'N/A'
        changelog_content += f"- **{sample['sample_name']}**: {file_name}\n"

    # Overrides section (if any)
    if session_overrides:
        changelog_content += "\n" + format_overrides_section_for_data_export(session_overrides) + "\n"

    changelog_content += f"""
## Export Sheets Generated
{sheets_description}

## Key Processing Notes
- Strict boundaries (time > l_boundary & time < r_boundary) for precise peak integration
- Compound-specific MM file patterns used for standard mixture identification
- {"Legacy unit-spacing integration matches MATLAB MANIC (larger numerical values)" if use_legacy_integration else "Time-based integration produces physically meaningful results with proper units"}
{key_processing_notes}

## Session Changes Made
This export represents the final state of all data processing and parameter adjustments made during the session. All parameter overrides and corrections have been applied to generate the most accurate quantitative results possible.

---
*Generated automatically by MANIC v{__version__}*
"""

    try:
        with open(changelog_path, 'w', encoding='utf-8') as f:
            f.write(changelog_content)
        logger.info(f"Changelog generated: {changelog_path}")
    except Exception as e:
        logger.error(f"Failed to generate changelog: {e}")
