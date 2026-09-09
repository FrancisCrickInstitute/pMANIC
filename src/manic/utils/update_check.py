"""
Update check against the ``releases/latest.json`` manifest on ``main``.

The manifest is fetched from raw.githubusercontent.com, which has no
per-IP API rate limit, so the check works on shared lab networks where
``api.github.com/releases/latest`` was returning 403s.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass

from manic.__version__ import __version_info__

logger = logging.getLogger(__name__)

LATEST_JSON_URL = (
    "https://raw.githubusercontent.com/FrancisCrickInstitute/pMANIC/main/releases/latest.json"
)


@dataclass(frozen=True)
class UpdateCheckResult:
    success: bool
    has_update: bool
    latest_version: str
    url: str


FAILED = UpdateCheckResult(False, False, "", "")


def parse_version(version_str: str) -> tuple[int, ...]:
    """'v1.2.3-beta' -> (1, 2, 3). Unparseable input compares lower than any release."""
    try:
        return tuple(int(part) for part in version_str.lstrip("v").split("-")[0].split("."))
    except ValueError:
        return (0, 0, 0)


def compare_manifest(
    manifest: dict, current: tuple[int, ...] = __version_info__
) -> UpdateCheckResult:
    version = str(manifest.get("version", "")).lstrip("v")
    if not version:
        return FAILED
    return UpdateCheckResult(
        success=True,
        has_update=parse_version(version) > current,
        latest_version=version,
        url=str(manifest.get("url", "")),
    )


def fetch_manifest(url: str = LATEST_JSON_URL, timeout: float = 5.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "MANIC-Update-Checker"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def check_for_update() -> UpdateCheckResult:
    try:
        return compare_manifest(fetch_manifest())
    except Exception as exc:
        logger.warning("Update check failed: %s", exc)
        return FAILED
