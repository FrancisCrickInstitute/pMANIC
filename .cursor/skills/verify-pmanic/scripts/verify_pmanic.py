#!/usr/bin/env python3
"""Isolated Qt widget harness for pMANIC. Never opens or clears ~/.manic_app/manic.db."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "src" / "manic" / "main.py").exists():
            return parent
    raise SystemExit("Run this from a pMANIC checkout")


ROOT = repo_root()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import __version__ as pyside_version
from PySide6.QtWidgets import QApplication, QPushButton

from manic.__version__ import APP_NAME, __version__
from manic.models.analysis import AnalysisMode
from manic.models.database import DB_FILE
from manic.ui.analysis_mode_dialog import AnalysisModeDialog
from manic.ui.left_toolbar import Toolbar

EVIDENCE_ROOT = ROOT / "artifacts" / "verify-pmanic"
USER_DB = Path.home() / ".manic_app" / "manic.db"
FEATURES = ("analysis-mode", "toolbar-labelled", "toolbar-unlabelled")


def _qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _grab(widget, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(path), "PNG")


def cmd_doctor(_: argparse.Namespace) -> int:
    report = {
        "app": APP_NAME,
        "version": __version__,
        "python": sys.version.split()[0],
        "pyside6": pyside_version,
        "qt_platform": os.environ.get("QT_QPA_PLATFORM", "unset"),
        "checkout": str(ROOT),
        "user_db": str(DB_FILE),
        "user_db_exists": DB_FILE.exists(),
        "harness": "verify_pmanic.py widget",
        "run_sh_safe": False,
    }
    print(json.dumps(report, indent=2))
    if DB_FILE != USER_DB:
        print("doctor fail: database.DB_FILE is not the documented user path", file=sys.stderr)
        return 1
    return 0


def _toolbar_report(toolbar) -> dict:
    layout = toolbar.targeted_qc.parentWidget().layout()
    return {
        "isotopologueRatioWidget": {
            "objectName": toolbar.isotopologue_ratios.objectName(),
            "hidden": toolbar.isotopologue_ratios.isHidden(),
            "index": layout.indexOf(toolbar.isotopologue_ratios),
        },
        "targetedQc": {
            "objectName": toolbar.targeted_qc.objectName(),
            "hidden": toolbar.targeted_qc.isHidden(),
            "index": layout.indexOf(toolbar.targeted_qc),
        },
        "totalAbundanceWidget": {
            "objectName": toolbar.total_abundance.objectName(),
            "hidden": toolbar.total_abundance.isHidden(),
            "index": layout.indexOf(toolbar.total_abundance),
        },
    }


def cmd_drive(args: argparse.Namespace) -> int:
    out = Path(args.out or EVIDENCE_ROOT / args.feature)
    app = _qt_app()
    payload = {"app": APP_NAME, "version": __version__, "feature": args.feature}

    if args.feature == "analysis-mode":
        dialog = AnalysisModeDialog()
        buttons = [b.text() for b in dialog.findChildren(QPushButton)]
        payload["buttons"] = buttons
        _grab(dialog, out / "analysis-mode.png")
        dialog.deleteLater()
        expected = {
            "Labelled isotope-tracing analysis",
            "Unlabelled targeted analysis",
        }
        ok = expected <= set(buttons)
        payload["ok"] = ok
        _write_json(out / "analysis-mode.json", payload)
        app.processEvents()
        return 0 if ok else 1

    mode = (
        AnalysisMode.LABELLED
        if args.feature == "toolbar-labelled"
        else AnalysisMode.UNLABELLED
    )
    toolbar = Toolbar(mode)
    try:
        widgets = _toolbar_report(toolbar)
        payload["widgets"] = widgets
        _grab(toolbar, out / f"{args.feature}.png")
        if args.feature == "toolbar-labelled":
            ok = (
                not widgets["isotopologueRatioWidget"]["hidden"]
                and not widgets["totalAbundanceWidget"]["hidden"]
                and widgets["targetedQc"]["hidden"]
                and widgets["isotopologueRatioWidget"]["index"]
                < widgets["totalAbundanceWidget"]["index"]
            )
        else:
            ok = (
                widgets["isotopologueRatioWidget"]["hidden"]
                and not widgets["targetedQc"]["hidden"]
                and not widgets["totalAbundanceWidget"]["hidden"]
                and widgets["targetedQc"]["index"]
                < widgets["totalAbundanceWidget"]["index"]
            )
        payload["ok"] = ok
        _write_json(out / f"{args.feature}.json", payload)
    finally:
        toolbar.deleteLater()
        app.processEvents()
    return 0 if payload["ok"] else 1


def cmd_cleanup(args: argparse.Namespace) -> int:
    scratch = Path(args.scratch) if args.scratch else Path("/tmp") / "verify-pmanic-scratch"
    if scratch.exists() and scratch.is_dir() and "verify-pmanic" in str(scratch):
        for child in scratch.iterdir():
            if child.is_file():
                child.unlink()
    if args.pid_file:
        pid_path = Path(args.pid_file)
        if pid_path.exists():
            pid = int(pid_path.read_text(encoding="utf-8").strip())
            try:
                os.kill(pid, 0)
            except OSError:
                pid_path.unlink(missing_ok=True)
                return 0
            os.kill(pid, 15)
            pid_path.unlink(missing_ok=True)
    print(f"evidence kept at {EVIDENCE_ROOT}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify pMANIC widget surfaces")
    sub = parser.add_subparsers(dest="cmd", required=True)

    doctor = sub.add_parser("doctor", help="Read-only harness health")
    doctor.set_defaults(func=cmd_doctor)

    drive = sub.add_parser("drive", help="Drive one mapped feature")
    drive.add_argument("feature", choices=FEATURES)
    drive.add_argument("--out", help="Evidence directory")
    drive.set_defaults(func=cmd_drive)

    cleanup = sub.add_parser("cleanup", help="Remove scratch and harness PIDs. Keep evidence.")
    cleanup.add_argument("--scratch")
    cleanup.add_argument("--pid-file")
    cleanup.set_defaults(func=cmd_cleanup)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
