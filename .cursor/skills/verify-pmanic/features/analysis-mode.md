# Choose analysis mode

The first thing a user does is pick Labelled or Unlabelled. That choice is fixed for the session.

## Sub-features

- `mode-open` shows the `Choose Analysis Mode` dialog before any window.
- `mode-labelled` starts a labelled session from `Labelled isotope-tracing analysis`.
- `mode-unlabelled` starts an unlabelled session from `Unlabelled targeted analysis`.
- `mode-cancel` leaves the app when the user cancels.

## How to get to it (user POV)

- Launch MANIC. The dialog is the first surface.
- Choose **File → New Analysis Session…**. That clears the session and shows the same dialog.

## Driving it with verify-pmanic

Preconditions:

- `verify_pmanic.py doctor` reports `"app": "MANIC"` and `"run_sh_safe": false`.
- `QT_QPA_PLATFORM=offscreen`.

- **Open dialog.** Construct the startup chooser. Run `PYTHONPATH=src .venv/bin/python .cursor/skills/verify-pmanic/scripts/verify_pmanic.py drive analysis-mode --out artifacts/verify-pmanic/analysis-mode`. `analysis-mode.json` has `"ok": true`.
- **Confirm labels.** Read `buttons` in that JSON. It contains `Labelled isotope-tracing analysis` and `Unlabelled targeted analysis`.
- **Proof.** Open `artifacts/verify-pmanic/analysis-mode/analysis-mode.png`. The grab shows both mode buttons and Cancel.
- **Cancel path.** Not driven by the harness (`exec()` would block). Report it skipped. Do not mark it verified.

## Gotchas

- Do not launch `./scripts/run.sh` to see this dialog. That clears the user database.
- Cancel is only on the live dialog. The harness constructs the widget and does not call `exec()`.
- New Analysis Session is the same dialog after a live session exists. This harness does not click that menu.
