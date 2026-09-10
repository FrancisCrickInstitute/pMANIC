from __future__ import annotations

from collections.abc import Iterable

from manic.models.database import get_connection
from manic.processors.chromatographic_peak_deconvolution import normalize_fit_type

FIT_TYPE_LABELS = {
    "auto": "Auto",
    "gaussian": "Gaussian",
    "bi_gaussian": "Bi-Gaussian",
    "emg": "EMG",
}


def set_sample_fit_type(
    compound_name: str, sample_names: Iterable[str], fit_type: str | None
) -> None:
    names = list(sample_names)
    if not names:
        return
    with get_connection() as conn:
        if fit_type is None:
            conn.executemany(
                "DELETE FROM sample_fit_type WHERE compound_name = ? AND sample_name = ?",
                [(compound_name, sample_name) for sample_name in names],
            )
            return
        normalized = normalize_fit_type(fit_type)
        conn.executemany(
            """
            INSERT OR REPLACE INTO sample_fit_type (compound_name, sample_name, fit_type)
            VALUES (?, ?, ?)
            """,
            [(compound_name, sample_name, normalized) for sample_name in names],
        )


def get_sample_fit_types(
    compound_name: str | None = None,
) -> dict[tuple[str, str], str]:
    sql = "SELECT compound_name, sample_name, fit_type FROM sample_fit_type"
    params: tuple[str, ...] = ()
    if compound_name is not None:
        sql += " WHERE compound_name = ?"
        params = (compound_name,)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {
        (row["compound_name"], row["sample_name"]): row["fit_type"] for row in rows
    }
