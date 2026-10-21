"""One MM-file pattern matcher shared by every resolver.

"Process External Data" (the in-memory provider) used its own matcher: it
removed every ``*`` and did a plain substring match, and it split patterns
only on commas. The main matcher honoured where the ``*`` sat and also split
on ``;``, tabs and new lines, so the same compound list could select different
MM files — and change the background correction and the MRRF (#193).
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional

_TOKEN_CACHE: dict = {}


def parse_mm_tokens(mm_files_field: Optional[str]) -> List[str]:
    """Split an ``mm_files`` pattern list on commas, semicolons, tabs and newlines."""
    if not mm_files_field:
        return []
    raw = mm_files_field.replace(";", ",").replace("\n", ",").replace("\t", ",")
    return [t.strip() for t in raw.split(",") if t.strip()]


def _token_regex(token: str) -> "re.Pattern[str]":
    """* means "anything" (SQL LIKE %); every other character is literal."""
    cached = _TOKEN_CACHE.get(token)
    if cached is None:
        parts = ["^"]
        for ch in token:
            if ch == "*":
                parts.append(".*")
            else:
                parts.append(re.escape(ch))
        parts.append("$")
        cached = re.compile("".join(parts), re.IGNORECASE)
        _TOKEN_CACHE[token] = cached
    return cached


def mm_token_matches(token: str, sample_name: str) -> bool:
    """A token holding a ``*`` anchors at both ends; a bare token is a substring match."""
    if "*" in token:
        return _token_regex(token).match(sample_name) is not None
    return token.lower() in sample_name.lower()


def resolve_mm_samples_from_names(
    mm_files_field: Optional[str], samples: Iterable[str]
) -> List[str]:
    """The sample names matching any pattern in *mm_files_field*, sorted."""
    tokens = parse_mm_tokens(mm_files_field)
    if not tokens:
        return []
    matched = set()
    for sample in samples:
        for token in tokens:
            if mm_token_matches(token, sample):
                matched.add(sample)
                break
    return sorted(matched)
