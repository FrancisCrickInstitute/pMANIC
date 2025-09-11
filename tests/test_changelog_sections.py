from manic.io.changelog_sections import (
    format_compounds_table_for_data_export,
    format_overrides_section_for_data_export,
    format_compounds_table_for_session_export,
    format_overrides_section_for_session_export,
)


def test_format_compounds_table_for_data_export_single():
    compounds = [
        {
            'compound_name': 'Glucose',
            'retention_time': 5.12345,
            'loffset': 0.5,
            'roffset': 0.75,
            'mass0': 180.063388,
            'label_atoms': 6,
            'formula': 'C6H12O6',
            'int_std_amount': 2.0,
        }
    ]
    out = format_compounds_table_for_data_export(compounds)

    # Headline and header row
    assert '## Compounds Processed' in out
    assert '| Compound Name | RT (min) | L Offset | R Offset | Mass (m/z) | Label Atoms | Formula | Internal Std Amount |' in out
    # Row content with precision
    assert '| Glucose | 5.123 | 0.500 | 0.750 | 180.0634 | 6 | C6H12O6 | 2.0 |' in out


def test_format_overrides_section_for_data_export_multiple():
    overrides = [
        {'compound_name': 'Glucose', 'sample_name': 'S1', 'retention_time': 5.0, 'loffset': 0.5, 'roffset': 0.7},
        {'compound_name': 'Lactate', 'sample_name': 'S2', 'retention_time': 3.2, 'loffset': 0.3, 'roffset': 0.4},
    ]
    out = format_overrides_section_for_data_export(overrides)
    assert '## Session Parameter Overrides' in out
    assert '| Glucose | S1 | 5.000 | 0.500 | 0.700 |' in out
    assert '| Lactate | S2 | 3.200 | 0.300 | 0.400 |' in out


def test_format_compounds_table_for_session_export_single():
    compounds = [
        {
            'compound_name': 'Alanine',
            'retention_time': 2.4567,
            'loffset': 0.2,
            'roffset': 0.3,
            'mass0': 89.0477,
            'label_atoms': 3,
        }
    ]
    out = format_compounds_table_for_session_export(compounds)
    assert '## Compound Definitions (1 compounds)' in out
    assert '| Alanine | 2.457 | 0.200 | 0.300 | 89.0477 | 3 |' in out


def test_format_overrides_section_for_session_export_grouping():
    overrides = [
        {'compound_name': 'Alanine', 'sample_name': 'S1', 'retention_time': 2.1, 'loffset': 0.2, 'roffset': 0.3},
        {'compound_name': 'Alanine', 'sample_name': 'S0', 'retention_time': 2.2, 'loffset': 0.25, 'roffset': 0.35},
        {'compound_name': 'Citrate', 'sample_name': 'S2', 'retention_time': 7.3, 'loffset': 0.6, 'roffset': 0.8},
    ]
    out = format_overrides_section_for_session_export(overrides)
    # Section header with count
    assert '## Session Integration Overrides (3 overrides)' in out
    # Group headings present
    assert '### Alanine' in out
    assert '### Citrate' in out
    # Rows with precision
    assert '| S0 | 2.200 | 0.250 | 0.350 |' in out
    assert '| S1 | 2.100 | 0.200 | 0.300 |' in out
    assert '| S2 | 7.300 | 0.600 | 0.800 |' in out

