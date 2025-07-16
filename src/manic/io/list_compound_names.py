from typing import List

from manic.models.database import get_connection


def list_compound_names() -> List[str]:
    sql = """
        SELECT compound_name
        FROM   compounds
        WHERE  deleted = 0
        ORDER  BY id
    """

    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()

    # `conn.row_factory` is sqlite3.Row, so each row works like a dict
    return [row["compound_name"] for row in rows]
