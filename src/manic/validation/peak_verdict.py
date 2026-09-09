from __future__ import annotations

from enum import StrEnum
from typing import Mapping


class PeakReview(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class PeakVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


def resolve_verdict(meets_threshold: bool, review: PeakReview | None) -> PeakVerdict:
    if review is PeakReview.REJECTED:
        return PeakVerdict.REJECTED
    if review is PeakReview.ACCEPTED:
        return PeakVerdict.ACCEPTED
    return PeakVerdict.PASS if meets_threshold else PeakVerdict.FAIL


PEAK_VERDICT_FILL: Mapping[PeakVerdict, str | None] = {
    PeakVerdict.PASS: None,
    PeakVerdict.FAIL: "#FFCCCC",
    PeakVerdict.ACCEPTED: "#E5D4F1",
    PeakVerdict.REJECTED: "#E0C9A6",
}
