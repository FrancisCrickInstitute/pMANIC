from __future__ import annotations

from typing import List

from manic.models.database import get_connection


def list_active_samples() -> List[str]:
    """
    Return every sample name whose `deleted` flag is 0.

    Examples
    --------
    >>> names = list_active_samples()
    >>> print(names[:3])
    ['sample_01', 'sample_02', 'qc_mix']

    The function is completely read-only and leaves the current
    transaction state unchanged.
    """
    sql = """
        SELECT sample_name
        FROM   samples
        WHERE  deleted = 0
        ORDER  BY sample_name
    """

    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()

    # `conn.row_factory` is sqlite3.Row, so each row works like a dict
    return [row["sample_name"] for row in rows]
