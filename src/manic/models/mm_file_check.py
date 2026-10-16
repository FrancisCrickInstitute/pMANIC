from __future__ import annotations

import re
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


def match_mm_samples(mm_files_field: str | None, samples: Iterable[str]) -> list[str]:
    """Return the sorted samples an ``mm_files`` field selects.

    Tokens are separated by commas, semicolons, tabs or new lines. ``*`` matches
    any run of characters, and a token without ``*`` matches anywhere in the
    name. Case is ignored for ASCII letters only, as SQLite LIKE does.
    """
    if not mm_files_field:
        return []
    tokens = [t.strip() for t in re.split(r"[,;\t\n]", mm_files_field) if t.strip()]
    regexes = [
        re.compile(
            ".*".join(map(re.escape, (tok if "*" in tok else f"*{tok}*").split("*"))),
            re.IGNORECASE | re.ASCII | re.DOTALL,
        )
        for tok in tokens
    ]
    return sorted({s for s in samples if any(r.fullmatch(s) for r in regexes)})


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
