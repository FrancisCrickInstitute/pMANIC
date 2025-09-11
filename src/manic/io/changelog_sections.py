from __future__ import annotations

from typing import Iterable


def format_compounds_table_for_data_export(compounds: Iterable[dict]) -> str:
    """
    Build the Compounds Processed table for data export changelog.
    Matches the existing columns and numeric formatting exactly.
    """
    out = []
    out.append("## Compounds Processed")
    out.append("| Compound Name | RT (min) | L Offset | R Offset | Mass (m/z) | Label Atoms | Formula | Internal Std Amount |")
    out.append("|---------------|----------|----------|----------|------------|-------------|---------|-------------------|")

    for compound in compounds:
        int_std = compound['int_std_amount'] if compound['int_std_amount'] else 'N/A'
        out.append(
            f"| {compound['compound_name']} | {compound['retention_time']:.3f} | {compound['loffset']:.3f} | "
            f"{compound['roffset']:.3f} | {compound['mass0']:.4f} | {compound['label_atoms']} | "
            f"{compound['formula'] or 'N/A'} | {int_std} |"
        )
    return "\n".join(out) + "\n"


def format_compounds_table_for_session_export(compounds: Iterable[dict]) -> str:
    """
    Build the Compound Definitions table for session export changelog.
    Matches the existing columns and numeric formatting exactly.
    """
    out = []
    # Normalize to list once for length and iteration
    if not isinstance(compounds, list):
        compounds = list(compounds)
    out.append(f"## Compound Definitions ({len(compounds)} compounds)\n")

    if compounds:
        out.append("| Compound Name | Retention Time (min) | Left Offset | Right Offset | Mass (m/z) | Label Atoms |")
        out.append("|---------------|---------------------|-------------|--------------|------------|-------------|")
        for compound in compounds:
            name = compound.get("compound_name", "Unknown")
            rt = compound.get("retention_time", 0) or 0
            loffset = compound.get("loffset", 0) or 0
            roffset = compound.get("roffset", 0) or 0
            mass = compound.get("mass0", 0) or 0
            label_atoms = compound.get("label_atoms", 0) or 0
            out.append(
                f"| {name} | {rt:.3f} | {loffset:.3f} | {roffset:.3f} | {mass:.4f} | {label_atoms} |"
            )
    else:
        out.append("*No compounds defined.*")
    return "\n".join(out) + "\n\n"


def format_overrides_section_for_data_export(session_overrides: Iterable[dict]) -> str:
    """
    Build the overrides section for the data export changelog.
    Plain table across all overrides.
    """
    rows = list(session_overrides)
    if not rows:
        return ""
    out = []
    out.append("## Session Parameter Overrides")
    out.append("The following compounds had their parameters modified during the session:\n")
    out.append("| Compound | Sample | RT Override | L Offset Override | R Offset Override |")
    out.append("|----------|--------|-------------|-------------------|-------------------|")
    for override in rows:
        out.append(
            f"| {override['compound_name']} | {override['sample_name']} | {override['retention_time']:.3f} | "
            f"{override['loffset']:.3f} | {override['roffset']:.3f} |"
        )
    return "\n".join(out) + "\n"


def format_overrides_section_for_session_export(session_overrides: Iterable[dict]) -> str:
    """
    Build the overrides section for session export changelog.
    Grouped by compound, with sub-table per compound (matches existing output).
    """
    rows = list(session_overrides)
    out = []
    out.append(f"## Session Integration Overrides ({len(rows)} overrides)\n")
    if not rows:
        out.append("*No session-specific integration overrides were made.*\n")
        out.append("This indicates that all compounds used their default integration parameters across all samples.")
        return "\n".join(out) + "\n\n"

    out.append("These represent manual adjustments to integration boundaries made during analysis.\n")
    overrides_by_compound: dict[str, list[dict]] = {}
    for override in rows:
        c = override.get("compound_name", "Unknown")
        overrides_by_compound.setdefault(c, []).append(override)

    for compound_name in sorted(overrides_by_compound):
        out.append(f"### {compound_name}\n")
        out.append("| Sample Name | Retention Time (min) | Left Offset | Right Offset |")
        out.append("|-------------|---------------------|-------------|-------------|")
        for override in sorted(overrides_by_compound[compound_name], key=lambda x: x.get("sample_name", "")):
            sample_name = override.get("sample_name", "Unknown")
            rt = override.get("retention_time", 0) or 0
            loffset = override.get("loffset", 0) or 0
            roffset = override.get("roffset", 0) or 0
            out.append(f"| {sample_name} | {rt:.3f} | {loffset:.3f} | {roffset:.3f} |")
        out.append("")

    return "\n".join(out) + "\n"
