"""
Read a compound-list spreadsheet and write rows directly into the
`compounds` table. Talking to SQLite through get_connection() only.
"""

import logging
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ValidationError, validator

from manic.models.database import get_connection

logger = logging.getLogger(__name__)


# 1.  Pydantic model – row-level validation & coercion
class CompoundRow(BaseModel):
    compound_name: str
    retention_time: float
    mass0: float
    loffset: float = 0.0
    roffset: float = 0.0
    label_atoms: int = 0
    deleted: int = 0  # soft-delete flag

    # pydantic auto checks all functions decorated
    @validator("compound_name")
    # function does not need to be manually called
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("compound_name is blank")
        return v


# 2.  Import function (
def import_compound_excel(filepath: str | Path) -> int:
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

    df.columns = [c.strip().lower() for c in df.columns]

    required = {"name", "tr", "mass0", "loffset", "roffset", "labelatoms"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns: {', '.join(missing)}")

    # ---- validate & prepare parameter list -----------------------
    # iterable of tuples required format for sqlite
    params: list[tuple] = []
    for idx, row in df.iterrows():
        try:
            cr = CompoundRow(
                compound_name=row["name"],
                retention_time=row["tr"],
                mass0=row["mass0"],
                loffset=row["loffset"],
                roffset=row["roffset"],
                label_atoms=row["labelatoms"],
            )
            params.append(
                (
                    cr.compound_name,
                    cr.retention_time,
                    cr.mass0,
                    cr.loffset,
                    cr.roffset,
                    cr.label_atoms,
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
        (compound_name, retention_time, mass0, loffset, roffset, label_atoms, deleted)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """

    # insert compound into the db
    with get_connection() as conn:
        conn.executemany(SQL, params)

    logger.info("Imported %d compound(s) from %s", len(params), path.name)
    return len(params)
