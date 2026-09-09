from __future__ import annotations

from manic.models.database import get_connection
from manic.validation.peak_verdict import PeakReview


def set_peak_review(
    compound: str, sample: str, review: PeakReview | None
) -> None:
    with get_connection() as conn:
        if review is None:
            conn.execute(
                "DELETE FROM peak_review WHERE compound_name = ? AND sample_name = ?",
                (compound, sample),
            )
            return
        conn.execute(
            """
            INSERT OR REPLACE INTO peak_review (compound_name, sample_name, review)
            VALUES (?, ?, ?)
            """,
            (compound, sample, review.value),
        )


def get_peak_reviews() -> dict[tuple[str, str], PeakReview]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT compound_name, sample_name, review FROM peak_review"
        ).fetchall()
    return {
        (row["compound_name"], row["sample_name"]): PeakReview(row["review"])
        for row in rows
    }

