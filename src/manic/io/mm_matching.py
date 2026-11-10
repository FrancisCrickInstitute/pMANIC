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


def parse_mm_tokens(mm_files_field: Optional[str]) -> List[str]:
    """Split an ``mm_files`` pattern list on commas, semicolons, tabs and newlines."""
    if not mm_files_field:
        return []
    raw = mm_files_field.replace(";", ",").replace("\n", ",").replace("\t", ",")
    return [t.strip() for t in raw.split(",") if t.strip()]


def mm_token_matches(token: str, sample_name: str) -> bool:
    """A token holding a ``*`` anchors at both ends; a bare token is a substring match."""
    if "*" in token:
        # * means "anything"; every other character is literal.
        pattern = ".*".join(re.escape(part) for part in token.split("*"))
        return re.fullmatch(pattern, sample_name, re.IGNORECASE) is not None
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
