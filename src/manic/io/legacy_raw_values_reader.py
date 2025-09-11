from __future__ import annotations

from typing import Dict, List

import pandas as pd


def read_raw_values_workbook(path: str) -> tuple[List[str], Dict[str, Dict[str, List[float]]]]:
    """
    Parse a MANIC Raw Values worksheet into in-memory structures.

    Returns a tuple of (samples, raw_data) where:
    - samples: ordered list of sample names
    - raw_data: mapping sample_name -> {compound_name: [areas per isotopologue]}

    Assumes sheet structure identical to our export's 'Raw Values':
      Row 1: 'Compound Name' | None | [compound names per isotopologue column]
      Row 2: 'Mass'          | None | [mass per isotopologue]
      Row 3: 'Isotope'       | None | [0..k]
      Row 4: 'tR'            | None | [retention time repeated]
      Row 5+: None           | sample_name | [values]
    """
    # Read without headers to preserve positions
    df = pd.read_excel(path, sheet_name='Raw Values', header=None, engine='openpyxl')

    # Header rows
    compounds_row = df.iloc[0, 2:].tolist()
    isotopes_row = df.iloc[2, 2:].tolist()

    # Build column mapping: col_index -> (compound_name, isotope_index)
    col_map: Dict[int, tuple[str, int]] = {}
    for idx, (cmp, iso) in enumerate(zip(compounds_row, isotopes_row)):
        col_map[2 + idx] = (str(cmp), int(iso))

    # Samples and data rows
    samples: List[str] = []
    raw_data: Dict[str, Dict[str, List[float]]] = {}

    for ridx in range(4, len(df)):
        sample = df.iat[ridx, 1]
        if pd.isna(sample):
            continue
        sample = str(sample)
        samples.append(sample)
        raw_data[sample] = {}

        # Gather values per compound by isotopologue index
        accum: Dict[str, Dict[int, float]] = {}
        for c in range(2, df.shape[1]):
            if c not in col_map:
                continue
            cmp, iso = col_map[c]
            val = df.iat[ridx, c]
            try:
                fval = float(val) if not pd.isna(val) else 0.0
            except Exception:
                fval = 0.0
            if cmp not in accum:
                accum[cmp] = {}
            accum[cmp][iso] = fval

        # Convert to ordered list per compound (0..max_iso)
        for cmp, iso_map in accum.items():
            max_iso = max(iso_map.keys()) if iso_map else 0
            areas = [iso_map.get(i, 0.0) for i in range(max_iso + 1)]
            raw_data[sample][cmp] = areas

    return samples, raw_data

