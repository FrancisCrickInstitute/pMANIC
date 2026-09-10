from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class MmFileStatus:
    compound_name: str
    pattern: str | None
    matched: tuple[str, ...]

    @property
    def state(self) -> Literal["unset", "no_match", "matched"]:
        if self.pattern is None:
            return "unset"
        if not self.matched:
            return "no_match"
        return "matched"


def _normalize_pattern(raw: str | None) -> str | None:
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def build_mm_file_report(
    rows: Iterable[tuple[str, str | None]],
    resolve: Callable[[str], list[str]],
) -> list[MmFileStatus]:
    report: list[MmFileStatus] = []
    for compound_name, raw_pattern in rows:
        pattern = _normalize_pattern(raw_pattern)
        if pattern is None:
            matched: tuple[str, ...] = ()
        else:
            matched = tuple(sorted(resolve(pattern)))
        report.append(
            MmFileStatus(
                compound_name=compound_name,
                pattern=pattern,
                matched=matched,
            )
        )
    return report
