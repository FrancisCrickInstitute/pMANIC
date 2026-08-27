# Session method

A user can export the current method and import it later. That is **File → Export Session...** and **File → Import Session...**.

## Sub-features

- `session-export` writes the method JSON.
- `session-import` reapplies overrides from that file.
- `session-standard` restores the internal standard when the file names one.

## How to get to it (user POV)

- Choose **File → Export Session...** after compounds are loaded.
- Choose **File → Import Session...** and pick the JSON file.

## Driving it with verify-pmanic

Preconditions:

- Doctor is green.
- The widget harness cannot operate `QFileDialog`.

- **Menu strings.** Confirm `Export Session...` and `Import Session...` in `src/manic/ui/main_window.py`.
- **Method settings.** Run `PYTHONPATH=src .venv/bin/python -m pytest tests/test_session_export_method_settings.py -q`. Exit code `0`.
- **Proof.** Keep the pytest transcript. Do not report the File dialogs as verified.

## Gotchas

- Pytest is the method file, not the menu.
- Import that cannot restore an internal standard must say so in the session dialog. That path needs a live window this harness does not open.
