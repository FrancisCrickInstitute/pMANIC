import json
from pathlib import Path

from conftest import _make_window
from PySide6.QtWidgets import QMessageBox

import manic.ui.main_window as main_window_module
from manic.ui.toast_notification import ToastNotification
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


def _toasts(window):
    bar = window.statusBar()
    return [t._label.full_text() for t in bar.findChildren(ToastNotification) if not t.isHidden()]


def test_a_start_up_check_stays_quiet_and_a_menu_check_answers(qapp, monkeypatch):
    window = _make_window(monkeypatch)
    try:
        window._on_update_check_finished(False, False, "", "")
        window._on_update_check_finished(True, False, "5.0.0", "")
        assert _toasts(window) == []

        window.check_updates_action.trigger()
        assert _toasts(window) == ["Checking for updates…"]
        window._on_update_check_finished(False, False, "", "")
        assert _toasts(window) == ["Update check failed"]

        # The menu's claim on an answer ends with that answer.
        window._on_update_check_finished(True, False, "5.0.0", "")
        assert _toasts(window) == ["Update check failed"]
    finally:
        window.close()


def test_an_update_is_pressed_on_the_user(qapp, monkeypatch):
    opened = []
    monkeypatch.setattr(main_window_module.QDesktopServices, "openUrl", opened.append)
    window = _make_window(monkeypatch)
    try:
        assert window.update_reminder_button.isHidden()

        # Return takes the default button, which must be the download.
        monkeypatch.setattr(QMessageBox, "exec", lambda box: box.defaultButton().click())
        window._on_update_check_finished(True, True, "9.9.9", "https://example.test/v9.9.9")
        assert [url.toString() for url in opened] == ["https://example.test/v9.9.9"]

        # Later leaves a reminder that still leads to the download.
        monkeypatch.setattr(QMessageBox, "exec", lambda box: box.reject())
        window._on_update_check_finished(True, True, "9.9.9", "https://example.test/v9.9.9")
        assert len(opened) == 1
        assert not window.update_reminder_button.isHidden()
        assert window.update_reminder_button.text() == "Update to v9.9.9"
        window.update_reminder_button.click()
        assert len(opened) == 2
    finally:
        window.close()
