from __future__ import annotations

import math
from typing import Dict, List

import pandas as pd


class RawValuesFormatError(ValueError):
    """Raised when a Raw Values sheet has malformed isotope headers or non-numeric cells."""


def _parse_isotope_index(value: object, compound_name: str, col_num: int) -> int:
    if pd.isna(value) or isinstance(value, bool):
        raise RawValuesFormatError(
            f"Compound '{compound_name}' has an invalid isotope header {value!r} in column {col_num}."
        )
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise RawValuesFormatError(
            f"Compound '{compound_name}' has a non-integer isotope header {value!r} in column {col_num}."
        ) from exc
    if not math.isfinite(numeric) or not numeric.is_integer() or numeric < 0:
        raise RawValuesFormatError(
            f"Compound '{compound_name}' has an invalid isotope header {value!r} in column {col_num}."
        )
    return int(numeric)


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
    df = pd.read_excel(path, sheet_name="Raw Values", header=None, engine="openpyxl")
    if df.shape[0] < 4 or df.shape[1] < 3:
        raise ValueError("Raw Values sheet does not have the expected MANIC layout.")

    compounds_row = df.iloc[0, 2:].tolist()
    isotopes_row = df.iloc[2, 2:].tolist()

    col_map: Dict[int, tuple[str, int]] = {}
    compound_isos: Dict[str, List[int]] = {}
    for idx, (cmp_val, iso_val) in enumerate(zip(compounds_row, isotopes_row)):
        col = 2 + idx
        if pd.isna(cmp_val) or not str(cmp_val).strip():
            raise RawValuesFormatError(
                f"Missing compound name in Raw Values column {col + 1}."
            )
        cmp_name = str(cmp_val).strip()
        iso = _parse_isotope_index(iso_val, cmp_name, col + 1)
        seen = compound_isos.setdefault(cmp_name, [])
        if iso in seen:
            raise RawValuesFormatError(
                f"Compound '{cmp_name}' has duplicate isotope column M+{iso}."
            )
        seen.append(iso)
        col_map[col] = (cmp_name, iso)

    for cmp_name, isos in compound_isos.items():
        expected = list(range(len(isos)))
        if sorted(isos) != expected:
            missing = sorted(set(range(max(isos) + 1)) - set(isos))
            raise RawValuesFormatError(
                f"Compound '{cmp_name}' has a gap in its isotope columns "
                f"(missing {', '.join(f'M+{m}' for m in missing)})."
            )

    samples: List[str] = []
    raw_data: Dict[str, Dict[str, List[float]]] = {}

    for ridx in range(4, len(df)):
        sample = df.iat[ridx, 1]
        if pd.isna(sample):
            continue
        sample = str(sample)
        samples.append(sample)
        raw_data[sample] = {}

        accum: Dict[str, Dict[int, float]] = {}
        for c, (cmp_name, iso) in col_map.items():
            val = df.iat[ridx, c]
            if pd.isna(val) or isinstance(val, bool):
                raise RawValuesFormatError(
                    f"Non-numeric or blank value for compound '{cmp_name}' "
                    f"(M+{iso}) in sample '{sample}'."
                )
            try:
                fval = float(val)
            except (TypeError, ValueError) as exc:
                raise RawValuesFormatError(
                    f"Non-numeric value {val!r} for compound '{cmp_name}' "
                    f"(M+{iso}) in sample '{sample}'."
                ) from exc
            if not math.isfinite(fval):
                raise RawValuesFormatError(
                    f"Non-finite value {val!r} for compound '{cmp_name}' "
                    f"(M+{iso}) in sample '{sample}'."
                )
            accum.setdefault(cmp_name, {})[iso] = fval

        for cmp_name, iso_map in accum.items():
            raw_data[sample][cmp_name] = [iso_map[i] for i in range(len(iso_map))]

    return samples, raw_data
