# Load compounds

A user imports a compound list before any plot appears. Labelled and unlabelled lists have different columns.

## Sub-features

- `compounds-menu` is **File → Load Compounds/Parameter List**.
- `compounds-unlabelled` imports a Q/V targeted list.
- `compounds-format` rejects a list that does not match the session mode.

## How to get to it (user POV)

- After choosing a mode, choose **File → Load Compounds/Parameter List** and pick the Excel or CSV list.

## Driving it with verify-pmanic

Preconditions:

- Doctor is green.
- The widget harness cannot operate `QFileDialog`.

- **Menu string.** Confirm the action title is `Load Compounds/Parameter List` in `src/manic/ui/main_window.py`. That is documentation of the user entry, not a drive.
- **Unlabelled import.** Run `PYTHONPATH=src .venv/bin/python -m pytest tests/test_unlabelled_compounds.py::test_data_provider_integrates_all_channels_but_quantifies_quantifier -q`. Exit code `0`.
- **Proof.** Keep the pytest transcript. Do not report the File menu click as verified.

## Gotchas

- Pytest import is not the File dialog. Say so when you skip the menu.
- An unlabelled list in a labelled session is the wrong workflow. Do not mix them.
- `./scripts/run.sh` then Load Compounds would work for a human and would wipe their database. Do not do that.
