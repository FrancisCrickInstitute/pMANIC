from __future__ import annotations

from dataclasses import dataclass

from manic.models.database import get_connection


@dataclass(slots=True)
class Compound:
    compound_name: str
    retention_time: float
    loffset: float
    roffset: float
    label_atoms: int
    mass0: float


def read_compound(compound_name: str) -> Compound:
    sql = """
        SELECT compound_name, retention_time, loffset, roffset, label_atoms, mass0
        FROM   compounds
        WHERE  compound_name=? AND deleted=0
        LIMIT  1
    """
    with get_connection() as conn:
        row = conn.execute(sql, (compound_name,)).fetchone()
        if row is None:
            raise LookupError(f"Compound not found for {compound_name}")

    return Compound(
        compound_name=row["compound_name"],
        retention_time=row["retention_time"],
        loffset=row["loffset"],
        roffset=row["roffset"],
        label_atoms=int(row["label_atoms"]),
        mass0=row["mass0"],
    )
