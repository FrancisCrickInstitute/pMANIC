"""
Read a compound-list spreadsheet and write rows directly into the
`compounds` table. Talking to SQLite through get_connection() only.

Header handling: Column names are normalized by lowercasing and removing
spaces/underscores so variants like "MM Files" / "MMFiles" / "mm_files"
are all accepted. This also applies to fields such as "Int Std amount"
and "Amount in StdMix".
"""

import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic import BaseModel, ValidationError, validator

from manic.models.analysis import (
    AnalysisMode,
    IonChannel,
    IonRole,
    validate_unlabelled_channels,
)
from manic.models.database import get_connection
from manic.processors.chromatographic_peak_deconvolution import (
    DEFAULT_DECONVOLUTION_LEVEL,
)

logger = logging.getLogger(__name__)


# 1.  Pydantic model – row-level validation & coercion
class CompoundRow(BaseModel):
    compound_name: str
    retention_time: float
    mass0: float
    loffset: float = 0.0
    roffset: float = 0.0
    label_atoms: int = 0
    formula: Optional[str] = None  # Molecular formula for natural abundance correction
    label_type: str = 'C'  # Element being labeled
    tbdms: int = 0  # TBDMS derivatization count
    meox: int = 0   # MeOX derivatization count
    me: int = 0     # Methylation count
    amount_in_std_mix: Optional[float] = None  # Known concentration in standard mixture (for MRRF calculation)
    int_std_amount: Optional[float] = None     # Amount of internal standard added to each sample
    mm_files: Optional[str] = None             # Comma-separated list of MM file patterns
    deleted: int = 0  # soft-delete flag

    # pydantic auto checks all functions decorated
    @validator("compound_name")
    # function does not need to be manually called
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("compound_name is blank")
        return v
    
    @validator("formula")
    def _normalize_formula(cls, v: Optional[str]) -> Optional[str]:
        """Normalize formula format from space-separated to standard."""
        if not v or pd.isna(v):
            return None
        
        # Remove extra spaces and standardize
        # Convert "C6 O3 N1 H12 Si1 S0 P0" to "C6H12N1O3Si1"
        formula = str(v).strip()
        
        # Skip if already in standard format (no spaces between element and count)
        if ' ' not in formula:
            return formula
        
        # Parse space-separated format
        elements = {}
        parts = formula.split()
        
        for part in parts:
            match = re.match(r'([A-Z][a-z]?)(\d*)', part)
            if match:
                elem, count = match.groups()
                count = int(count) if count else 1
                if count > 0:  # Skip elements with 0 count
                    elements[elem] = count
        
        # Rebuild in standard order
        standard_order = ['C', 'H', 'N', 'O', 'S', 'Si', 'P']
        result = ''
        
        for elem in standard_order:
            if elem in elements:
                count = elements[elem]
                result += elem + (str(count) if count > 1 else '')
                del elements[elem]
        
        # Add any remaining elements
        for elem in sorted(elements.keys()):
            count = elements[elem]
            result += elem + (str(count) if count > 1 else '')
        
        return result if result else None


# 2.  Import function (
def detect_compound_list_format(filepath: str | Path) -> AnalysisMode | None:
    """Sniff a compound list's headers to infer which workflow it targets.

    Gv3-style lists (QIon / ValIon1 / ValIon2 columns) are unlabelled targeted
    lists; Gv5-style lists (Mass0 / LabelAtoms) are labelled isotope-tracing
    lists. Returns None when the format can't be determined — callers should
    then fall back to the session's own mode.
    """

    path = Path(filepath).expanduser()
    if not path.exists():
        return None

    try:
        if path.suffix.lower() == ".xlsx":
            columns = pd.read_excel(path, engine="openpyxl", nrows=0).columns
        elif path.suffix.lower() == ".xls":
            columns = pd.read_excel(path, engine="xlrd", nrows=0).columns
        else:
            columns = pd.read_csv(path, nrows=0).columns
    except Exception as exc:
        logger.warning(f"Could not sniff compound list format of {path.name}: {exc}")
        return None

    normalized = {
        str(c).strip().lower().replace(" ", "").replace("_", "") for c in columns
    }
    if {"qion", "valion1"} & normalized:
        return AnalysisMode.UNLABELLED
    if {"mass0", "labelatoms"} & normalized:
        return AnalysisMode.LABELLED
    return None


def import_compound_excel(
    filepath: str | Path,
    analysis_mode: AnalysisMode | str = AnalysisMode.LABELLED,
) -> int:
    """
    Parameters
    ----------
    filepath : str | Path
        .xlsx / .xls / .csv file with columns
        name | tR | Mass0 | lOffset | rOffset

    Returns
    -------
    int  – number of rows inserted
    """
    path = Path(filepath).expanduser()
    if not path.exists():
        raise FileNotFoundError(path)

    # ---- load into DataFrame -------------------------------------
    if path.suffix.lower() == ".xlsx":
        df = pd.read_excel(path, engine="openpyxl")
    elif path.suffix.lower() == ".xls":
        df = pd.read_excel(path, engine="xlrd")
    else:
        df = pd.read_csv(path)

    def _normalize_col(name: str) -> str:
        """Normalize column names to be case/space/underscore-insensitive.

        Examples:
        - 'MM Files' -> 'mmfiles'
        - 'Int Std amount' -> 'intstdamount'
        - 'Amount in StdMix' -> 'amountinstdmix'
        - 'LabelType' -> 'labeltype'
        - 'tR' -> 'tr'
        """
        if not isinstance(name, str):
            name = str(name)
        name = name.strip().lower()
        # remove spaces and underscores to unify variants
        name = name.replace(' ', '').replace('_', '')
        return name

    # Apply normalization to columns
    df.columns = [_normalize_col(c) for c in df.columns]
    df = df.rename(
        columns={
            "qion": "quantion",
            "valion1": "qualifierion1",
            "valion2": "qualifierion2",
            "valion1ratio": "qualifier1ratio",
            "valion2ratio": "qualifier2ratio",
            "valion1tolerance": "qualifier1tolerance",
            "valion2tolerance": "qualifier2tolerance",
        }
    )
    
    # Debug: log available columns
    logger.info(f"Available columns in {path.name} (normalized): {list(df.columns)}")

    mode = AnalysisMode.coerce(analysis_mode)
    if mode is AnalysisMode.UNLABELLED:
        return _import_unlabelled_dataframe(df, path)

    # Required columns: enforce presence to avoid silent partial imports
    # (headers are normalized; see _normalize_col above)
    required = {
        "name",
        "tr",
        "mass0",
        "loffset",
        "roffset",
        "labelatoms",
        "formula",
        "labeltype",
        "tbdms",
        "meox",
        "me",
        "amountinstdmix",
        "intstdamount",
        "mmfiles",
    }
    missing = required - set(df.columns)
    if missing:
        # Cancel import with a clear message (handled by UI as an alert)
        ordered_missing = ", ".join(sorted(missing))
        raise ValueError(
            f"{path.name}: missing required column(s): {ordered_missing}.\n"
            "Please provide a compound list with all required columns."
        )

    # ---- hard-fail validation: retention times must be present -----
    # When retention times are missing, CDF import can fail later with unclear errors.
    # Fail early (on compound list load) with a simple actionable message.
    def _is_missing_tr(v) -> bool:
        if pd.isna(v):
            return True
        if isinstance(v, str) and not v.strip():
            return True
        try:
            return not pd.notna(float(v))
        except Exception:
            return True

    if any(_is_missing_tr(v) for v in df["tr"].tolist()):
        raise ValueError(
            "Compound list contains rows missing retention time (tR). "
            "Please fill in tR (minutes) for all compounds and reload the compound list."
        )

    # ---- validate & prepare parameter list -----------------------
    # iterable of tuples required format for sqlite
    params: list[tuple] = []
    for idx, row in df.iterrows():
        try:
            # Get optional fields with defaults using pandas Series safe access
            formula = row["formula"] if pd.notna(row["formula"]) else None
            label_type = row["labeltype"] if pd.notna(row["labeltype"]) else "C"
            tbdms = int(row["tbdms"]) if pd.notna(row["tbdms"]) else 0
            meox = int(row["meox"]) if pd.notna(row["meox"]) else 0
            me = int(row["me"]) if pd.notna(row["me"]) else 0

            # Get new MRRF and MM file fields (normalized keys cover variants with spaces/underscores)
            amount_in_std_mix = (
                float(row["amountinstdmix"]) if "amountinstdmix" in row and pd.notna(row["amountinstdmix"]) else None
            )
            int_std_amount = (
                float(row["intstdamount"]) if "intstdamount" in row and pd.notna(row["intstdamount"]) else None
            )
            mm_files = row["mmfiles"] if "mmfiles" in row and pd.notna(row["mmfiles"]) else None
            
            cr = CompoundRow(
                compound_name=row["name"],
                retention_time=row["tr"],
                mass0=row["mass0"],
                loffset=row["loffset"],
                roffset=row["roffset"],
                label_atoms=row["labelatoms"],
                formula=formula,
                label_type=label_type,
                tbdms=tbdms,
                meox=meox,
                me=me,
                amount_in_std_mix=amount_in_std_mix,
                int_std_amount=int_std_amount,
                mm_files=mm_files,
            )
            params.append(
                (
                    cr.compound_name,
                    cr.retention_time,
                    cr.mass0,
                    cr.loffset,
                    cr.roffset,
                    cr.label_atoms,
                    cr.formula,
                    cr.label_type,
                    cr.tbdms,
                    cr.meox,
                    cr.me,
                    cr.amount_in_std_mix,
                    cr.int_std_amount,
                    cr.mm_files,
                    cr.deleted,
                )
            )
        except ValidationError as exc:
            logger.warning("Row %d skipped: %s", idx + 2, exc.errors())

    if not params:
        logger.warning("%s contained no valid rows; nothing imported", path.name)
        return 0

    # sql insert statement
    SQL = """
    INSERT OR IGNORE INTO compounds
        (compound_name, retention_time, mass0, loffset, roffset, label_atoms, 
         formula, label_type, tbdms, meox, me, amount_in_std_mix, int_std_amount, mm_files, deleted)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    # insert compound into the db
    with get_connection() as conn:
        # First check what columns exist in the table
        cursor = conn.execute("PRAGMA table_info(compounds)")
        columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"Compounds table columns: {columns}")
        
        # Try to insert
        try:
            conn.executemany(SQL, params)
        except Exception as e:
            logger.error(f"Failed to insert compounds: {e}")
            # Try without formula column if it doesn't exist
            if "formula" not in columns:
                logger.warning("Formula column not found, inserting without formulas")
                SQL_NO_FORMULA = """
                INSERT OR IGNORE INTO compounds
                    (compound_name, retention_time, mass0, loffset, roffset, label_atoms, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """
                params_no_formula = [(p[0], p[1], p[2], p[3], p[4], p[5], p[11]) for p in params]
                conn.executemany(SQL_NO_FORMULA, params_no_formula)
        
        # Verify formula column accessibility
        try:
            conn.execute("SELECT compound_name, formula FROM compounds WHERE deleted=0 LIMIT 1").fetchone()
        except Exception as e:
            logger.warning(f"Formula column may not be accessible: {e}")

    logger.info("Imported %d compound(s) from %s", len(params), path.name)
    return len(params)


def _optional_float(row: pd.Series, key: str) -> Optional[float]:
    if key not in row or pd.isna(row[key]):
        return None
    if isinstance(row[key], str) and not row[key].strip():
        return None
    return float(row[key])


def _import_unlabelled_dataframe(df: pd.DataFrame, path: Path) -> int:
    """Import a targeted quantifier/qualifier compound list."""

    required = {"name", "tr", "loffset", "roffset", "quantion", "qualifierion1"}
    missing = required - set(df.columns)
    if missing:
        ordered_missing = ", ".join(sorted(missing))
        raise ValueError(
            f"{path.name}: missing unlabelled column(s): {ordered_missing}.\n"
            "Required columns are name, tR, lOffset, rOffset, quant_ion, "
            "and qualifier_ion_1."
        )

    compounds: list[tuple] = []
    ions_by_compound: list[tuple[str, tuple[IonChannel, ...]]] = []
    rt_tolerances: list[tuple[float, str]] = []
    validation_errors: list[str] = []

    for idx, row in df.iterrows():
        spreadsheet_row = idx + 2
        try:
            name = str(row["name"]).strip()
            if not name:
                raise ValueError("name is blank")
            retention_time = float(row["tr"])
            if not pd.notna(retention_time):
                raise ValueError("retention time is missing")

            quantifier = IonChannel(
                mz=float(row["quantion"]),
                role=IonRole.QUANTIFIER,
                ordinal=0,
            )
            channel_values = [quantifier]
            for ordinal in (1, 2):
                mz = _optional_float(row, f"qualifierion{ordinal}")
                if mz is None:
                    continue
                channel_values.append(
                    IonChannel(
                        mz=mz,
                        role=IonRole.QUALIFIER,
                        ordinal=ordinal,
                        expected_ratio=_optional_float(
                            row, f"qualifier{ordinal}ratio"
                        ),
                        ratio_tolerance=_optional_float(
                            row, f"qualifier{ordinal}tolerance"
                        ),
                    )
                )

            channels = validate_unlabelled_channels(channel_values)
            amount_in_std_mix = _optional_float(row, "amountinstdmix")
            int_std_amount = _optional_float(row, "intstdamount")
            loffset = float(row["loffset"])
            roffset = float(row["roffset"])
            rt_tolerance = _optional_float(row, "trwindow")
            if rt_tolerance is None:
                rt_tolerance = max(loffset, roffset)
            if rt_tolerance < 0:
                raise ValueError("tR window cannot be negative")
            mm_files = (
                str(row["mmfiles"]).strip()
                if "mmfiles" in row and pd.notna(row["mmfiles"])
                else None
            )

            compounds.append(
                (
                    name,
                    retention_time,
                    float(quantifier.mz),
                    loffset,
                    roffset,
                    0,
                    None,
                    "C",
                    0,
                    0,
                    0,
                    amount_in_std_mix,
                    int_std_amount,
                    mm_files,
                    0,
                    DEFAULT_DECONVOLUTION_LEVEL,
                )
            )
            ions_by_compound.append((name, channels))
            rt_tolerances.append((rt_tolerance, name))
        except (TypeError, ValueError) as exc:
            validation_errors.append(f"row {spreadsheet_row}: {exc}")

    if validation_errors:
        raise ValueError(
            f"{path.name}: invalid unlabelled compound data:\n"
            + "\n".join(validation_errors)
        )
    if not compounds:
        return 0

    compound_sql = """
        INSERT OR IGNORE INTO compounds
            (compound_name, retention_time, mass0, loffset, roffset, label_atoms,
             formula, label_type, tbdms, meox, me, amount_in_std_mix,
             int_std_amount, mm_files, deleted, deconvolution_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    ion_sql = """
        INSERT OR REPLACE INTO compound_ions
            (compound_name, role, ordinal, mz, expected_ratio, ratio_tolerance)
        VALUES (?, ?, ?, ?, ?, ?)
    """

    with get_connection() as conn:
        conn.executemany(compound_sql, compounds)
        conn.executemany(
            "UPDATE compounds SET rt_tolerance = ? WHERE compound_name = ?",
            rt_tolerances,
        )
        for compound_name, channels in ions_by_compound:
            conn.execute(
                "DELETE FROM compound_ions WHERE compound_name = ?",
                (compound_name,),
            )
            conn.executemany(
                ion_sql,
                [
                    (
                        compound_name,
                        channel.role.value,
                        channel.ordinal,
                        channel.mz,
                        channel.expected_ratio,
                        channel.ratio_tolerance,
                    )
                    for channel in channels
                ],
            )

    logger.info("Imported %d unlabelled compound(s) from %s", len(compounds), path.name)
    return len(compounds)


@dataclass(frozen=True)
class UnlabelledCompoundRecord:
    compound_name: str
    retention_time: float
    loffset: float
    roffset: float
    rt_window: Optional[float]
    amount_in_std_mix: Optional[float]
    int_std_amount: Optional[float]
    mm_files: Optional[str]
    channels: tuple[IonChannel, ...]


def _duplicate_name_error(name: str) -> ValueError:
    return ValueError(
        f"A compound named '{name}' already exists. "
        "Soft-deleted compounds also occupy that name; "
        "recover deleted compounds or choose a different name."
    )


def insert_compound(row: CompoundRow) -> None:
    sql = """
    INSERT INTO compounds
        (compound_name, retention_time, mass0, loffset, roffset, label_atoms,
         formula, label_type, tbdms, meox, me, amount_in_std_mix, int_std_amount, mm_files, deleted)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    try:
        with get_connection() as conn:
            conn.execute(
                sql,
                (
                    row.compound_name,
                    row.retention_time,
                    row.mass0,
                    row.loffset,
                    row.roffset,
                    row.label_atoms,
                    row.formula,
                    row.label_type,
                    row.tbdms,
                    row.meox,
                    row.me,
                    row.amount_in_std_mix,
                    row.int_std_amount,
                    row.mm_files,
                    row.deleted,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise _duplicate_name_error(row.compound_name) from exc


def insert_unlabelled_compound(record: UnlabelledCompoundRecord) -> None:
    name = record.compound_name.strip()
    if not name:
        raise ValueError("compound_name is blank")

    channels = validate_unlabelled_channels(record.channels)
    quantifier = next(c for c in channels if c.role is IonRole.QUANTIFIER)

    rt_tolerance = record.rt_window
    if rt_tolerance is None:
        rt_tolerance = max(record.loffset, record.roffset)
    if rt_tolerance < 0:
        raise ValueError("tR window cannot be negative")

    compound_sql = """
        INSERT INTO compounds
            (compound_name, retention_time, mass0, loffset, roffset, label_atoms,
             formula, label_type, tbdms, meox, me, amount_in_std_mix,
             int_std_amount, mm_files, deleted, deconvolution_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    ion_sql = """
        INSERT INTO compound_ions
            (compound_name, role, ordinal, mz, expected_ratio, ratio_tolerance)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    try:
        with get_connection() as conn:
            conn.execute(
                compound_sql,
                (
                    name,
                    record.retention_time,
                    float(quantifier.mz),
                    record.loffset,
                    record.roffset,
                    0,
                    None,
                    "C",
                    0,
                    0,
                    0,
                    record.amount_in_std_mix,
                    record.int_std_amount,
                    record.mm_files,
                    0,
                    DEFAULT_DECONVOLUTION_LEVEL,
                ),
            )
            conn.execute(
                "UPDATE compounds SET rt_tolerance = ? WHERE compound_name = ?",
                (rt_tolerance, name),
            )
            conn.executemany(
                ion_sql,
                [
                    (
                        name,
                        channel.role.value,
                        channel.ordinal,
                        channel.mz,
                        channel.expected_ratio,
                        channel.ratio_tolerance,
                    )
                    for channel in channels
                ],
            )
    except sqlite3.IntegrityError as exc:
        raise _duplicate_name_error(name) from exc
