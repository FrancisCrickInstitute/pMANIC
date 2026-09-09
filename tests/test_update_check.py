import json
from pathlib import Path

from manic.utils import update_check
from manic.utils.update_check import (
    FAILED,
    UpdateCheckResult,
    check_for_update,
    compare_manifest,
    parse_version,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_parse_version_strips_prefix_and_suffix():
    assert parse_version("v5.1.2-beta") == (5, 1, 2)
    assert parse_version("garbage") is None


def test_compare_manifest_reports_newer_release():
    manifest = {"version": "5.1.0", "url": "https://example.test/v5.1.0"}
    assert compare_manifest(manifest, current=(5, 0, 0)) == UpdateCheckResult(
        True, True, "5.1.0", "https://example.test/v5.1.0"
    )


def test_compare_manifest_older_or_equal_is_not_an_update():
    assert compare_manifest({"version": "v4.1.0"}, current=(5, 0, 0)).has_update is False
    assert compare_manifest({"version": "5.0.0"}, current=(5, 0, 0)).has_update is False


def test_compare_manifest_without_a_valid_version_fails():
    assert compare_manifest({}, current=(5, 0, 0)) == FAILED
    assert compare_manifest({"version": "garbage"}, current=(5, 0, 0)) == FAILED


def test_check_for_update_swallows_network_errors(monkeypatch):
    def boom(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(update_check, "fetch_manifest", boom)
    assert check_for_update() == FAILED


def test_committed_manifest_matches_the_worker_schema():
    manifest = json.loads((REPO_ROOT / "releases" / "latest.json").read_text())
    outcome = compare_manifest(manifest, current=(0, 0, 0))
    assert outcome.success
    assert outcome.has_update
    assert outcome.url.startswith("https://github.com/FrancisCrickInstitute/pMANIC/releases/")
