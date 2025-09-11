from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from manic.__version__ import __version__
from manic.models.database import get_connection

logger = logging.getLogger(__name__)


def generate_changelog(export_filepath: str, *, internal_standard: Optional[str], use_legacy_integration: bool) -> None:
    """
    Generate a comprehensive changelog.md file detailing the export session.
    """
    export_path = Path(export_filepath)
    changelog_path = export_path.parent / "changelog.md"

    # Get session information from database
    with get_connection() as conn:
        compounds_query = """
            SELECT compound_name, retention_time, loffset, roffset, mass0, 
                   label_atoms, formula, label_type, tbdms, meox, me,
                   amount_in_std_mix, int_std_amount, mm_files
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

    changelog_content = f"""# MANIC Export Session Changelog

## Export Information
- **Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **MANIC Version:** {__version__}
- **Export File:** {export_path.name}
- **Internal Standard:** {internal_standard or 'None selected'}

## Processing Settings
- **Mass Tolerance Method:** Asymmetric offset + rounding (MANIC original method)
- **Integration Method:** {"Legacy Unit-Spacing (MATLAB Compatible)" if use_legacy_integration else "Time-based integration (scientifically accurate)"}
- **Expected Value Scale:** {"~100× larger than time-based method" if use_legacy_integration else "Physically meaningful units"}
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
        changelog_content += (
            f"| {compound['compound_name']} | {compound['retention_time']:.3f} | {compound['loffset']:.3f} | "
            f"{compound['roffset']:.3f} | {compound['mass0']:.4f} | {compound['label_atoms']} | "
            f"{compound['formula'] or 'N/A'} | {int_std} |\n"
        )

    changelog_content += f"\n## Sample Files Processed\n"
    for sample in samples:
        file_name = sample['file_name'] if sample['file_name'] else 'N/A'
        changelog_content += f"- **{sample['sample_name']}**: {file_name}\n"

    if session_overrides:
        changelog_content += f"\n## Session Parameter Overrides\n"
        changelog_content += (
            "The following compounds had their parameters modified during the session:\n\n"
        )
        changelog_content += (
            "| Compound | Sample | RT Override | L Offset Override | R Offset Override |\n"
        )
        changelog_content += (
            "|----------|--------|-------------|-------------------|-------------------|\n"
        )

        for override in session_overrides:
            changelog_content += (
                f"| {override['compound_name']} | {override['sample_name']} | {override['retention_time']:.3f} | "
                f"{override['loffset']:.3f} | {override['roffset']:.3f} |\n"
            )

    changelog_content += f"""
## Export Sheets Generated
1. **Raw Values** - Direct instrument signals (uncorrected peak areas using {"legacy unit-spacing" if use_legacy_integration else "time-based"} integration)
2. **Corrected Values** - Natural isotope abundance corrected signals
3. **Isotope Ratios** - Normalized corrected values (fractions sum to 1.0)  
4. **% Label Incorporation** - Percentage of experimental label incorporation
5. **Abundances** - Absolute metabolite concentrations via internal standard calibration

## Key Processing Notes
- Integration boundaries determined by compound-specific loffset/roffset values
- Inclusive boundaries (time >= l_boundary & time <= r_boundary) to match MATLAB exports
- Compound-specific MM file patterns used for standard mixture identification
- {"Legacy unit-spacing integration matches MATLAB MANIC (larger numerical values)" if use_legacy_integration else "Time-based integration produces physically meaningful results with proper units"}
- Natural isotope correction applied using high-performance algorithms for accuracy

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

