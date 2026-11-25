from __future__ import annotations

from manic.models.database import get_connection

# Excel holds at most this many characters in a cell; a longer note would be cut on export.
MAX_NOTE_CHARS = 32767


def set_sample_note(compound: str, sample: str, note: str | None) -> None:
    """Save the note for one sample of one compound; empty or blank text deletes it."""
    text = (note or "").strip()
    if len(text) > MAX_NOTE_CHARS:
        raise ValueError(f"A note holds at most {MAX_NOTE_CHARS:,} characters")
    with get_connection() as conn:
        if not text:
            conn.execute(
                "DELETE FROM sample_note WHERE compound_name = ? AND sample_name = ?",
                (compound, sample),
            )
            return
        conn.execute(
            """
            INSERT OR REPLACE INTO sample_note (compound_name, sample_name, note)
            VALUES (?, ?, ?)
            """,
            (compound, sample, text),
        )


def get_sample_notes(compound: str | None = None) -> dict[tuple[str, str], str]:
    sql = "SELECT compound_name, sample_name, note FROM sample_note"
    params: tuple[str, ...] = ()
    if compound is not None:
        sql += " WHERE compound_name = ?"
        params = (compound,)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {(row["compound_name"], row["sample_name"]): row["note"] for row in rows}
