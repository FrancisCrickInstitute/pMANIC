from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Optional

import xlsxwriter

from manic.io.legacy_raw_values_reader import read_raw_values_workbook
from manic.io.in_memory_provider import InMemoryDataProvider
import pandas as pd

from manic.sheet_generators import (
    raw_values as sheet_raw_values,
    corrected_values as sheet_corrected_values,
    isotope_ratios as sheet_isotope_ratios,
    label_incorporation as sheet_label_incorporation,
    abundances as sheet_abundances,
)

logger = logging.getLogger(__name__)


def _read_compounds_as_dicts(filepath: str) -> list[dict]:
    """
    Read compounds spreadsheet into a list of dicts without writing to DB.
    Mirrors columns used by sheet writers and calibration helpers.
    """
    path = filepath
    if filepath.lower().endswith('.xlsx'):
        df = pd.read_excel(path, engine='openpyxl')
    elif filepath.lower().endswith('.xls'):
        df = pd.read_excel(path, engine='xlrd')
    else:
        df = pd.read_csv(path)

    # Normalize columns to lower-case, strip
    df.columns = [c.strip().lower() for c in df.columns]

    # Required minimal columns
    required = {"name", "tr", "mass0", "loffset", "roffset", "labelatoms"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Compounds file missing columns: {', '.join(sorted(missing))}")

    out: list[dict] = []
    for _, row in df.iterrows():
        try:
            # Optional fields
            def get_opt(key, default=None):
                return (row[key] if key in row and pd.notna(row[key]) else default)

            out.append({
                'compound_name': str(row['name']).strip(),
                'retention_time': float(row['tr']),
                'mass0': float(row['mass0']),
                'loffset': float(row['loffset']),
                'roffset': float(row['roffset']),
                'label_atoms': int(row['labelatoms']),
                'formula': get_opt('formula'),
                'label_type': get_opt('labeltype', 'C') or 'C',
                'tbdms': int(get_opt('tbdms', 0) or 0),
                'meox': int(get_opt('meox', 0) or 0),
                'me': int(get_opt('me', 0) or 0),
                'amount_in_std_mix': float(get_opt('amountinstdmix', None)) if pd.notna(get_opt('amountinstdmix', float('nan'))) else None,
                'int_std_amount': float(get_opt('intstdamount', None)) if pd.notna(get_opt('intstdamount', float('nan'))) else None,
                'mm_files': get_opt('mmfiles', None),
            })
        except Exception as e:
            logger.warning(f"Skipping invalid compound row: {e}")
    return out


def rebuild_export_from_files(
    compounds_file: str,
    raw_values_file: str,
    output_path: str,
    *,
    internal_standard: Optional[str] = None,
    use_legacy_integration: bool = False,
    progress_callback=None,
) -> bool:
    """
    Build a full MANIC export workbook from a compounds list and a Raw Values workbook.
    """
    # Parse inputs
    compounds = _read_compounds_as_dicts(compounds_file)
    samples, raw_data = read_raw_values_workbook(raw_values_file)

    provider = InMemoryDataProvider(compounds, samples, raw_data, use_legacy_integration=use_legacy_integration)

    # Lightweight exporter-like context (only needs internal_standard_compound)
    exporter_ctx = SimpleNamespace(internal_standard_compound=internal_standard)

    # Create workbook
    workbook = xlsxwriter.Workbook(output_path, {
        'constant_memory': True,
        'use_zip64': True,
    })

    # Sheets with progress segments
    if progress_callback:
        progress_callback(0)

    sheet_raw_values.write(workbook, exporter_ctx, progress_callback, 0, 20, provider=provider)
    sheet_corrected_values.write(workbook, exporter_ctx, progress_callback, 20, 40, provider=provider)
    sheet_isotope_ratios.write(workbook, exporter_ctx, progress_callback, 40, 60, provider=provider)
    sheet_label_incorporation.write(workbook, exporter_ctx, progress_callback, 60, 80, provider=provider)
    sheet_abundances.write(workbook, exporter_ctx, progress_callback, 80, 100, provider=provider)

    workbook.close()
    if progress_callback:
        progress_callback(100)
    return True

