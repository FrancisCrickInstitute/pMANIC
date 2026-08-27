---
name: verify-pmanic
description: Drive the pMANIC desktop Qt UI in an isolated widget harness and capture proof. Use when verifying pMANIC, MANIC, toolbar charts, analysis mode, session export, or any user-visible PySide6 behaviour.
---

# Verify pMANIC

pMANIC is a PySide6 desktop app. A user chooses Labelled or Unlabelled, then works in `MainWindow`. There is no browser, no HTTP port, and no safe second instance of `./scripts/run.sh`.

**Never run `./scripts/run.sh` or `python -m src.manic.main` to verify.** `main()` calls `init_db()` then `clear_database()` on `~/.manic_app/manic.db`. That wipes the operator's session.

Drive widgets through `.cursor/skills/verify-pmanic/scripts/verify_pmanic.py`. It sets `QT_QPA_PLATFORM=offscreen` and never opens that database.

Read [features/README.md](features/README.md) before a run. Drive the mapped feature file, not a shortcut.

## Launch

Install once from the checkout:

```bash
uv sync
```

Ready when `doctor` prints `"app": "MANIC"` and `"run_sh_safe": false`. There is no server to keep alive. Each `drive` starts its own offscreen `QApplication` and exits.

Teardown is `cleanup`. It must not delete `artifacts/verify-pmanic/`.

## Doctor

Run first whenever anything looks off:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python \
  .cursor/skills/verify-pmanic/scripts/verify_pmanic.py doctor
```

Require:

- `"app": "MANIC"`
- `"harness": "verify_pmanic.py widget"`
- `"run_sh_safe": false`
- `"user_db"` equals `$HOME/.manic_app/manic.db`

Refuse to drive if `user_db` is some other path. A second harness in the same process cannot create another `QApplication`. Sequential `drive` processes are fine.

## Drive

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python \
  .cursor/skills/verify-pmanic/scripts/verify_pmanic.py drive <feature> \
  --out artifacts/verify-pmanic/<feature>
```

`<feature>` is `analysis-mode`, `toolbar-labelled`, or `toolbar-unlabelled`.

Stable handles:

| Handle | Widget |
| --- | --- |
| `mainWindow` | `MainWindow` |
| `toolbar` | left toolbar |
| `isotopologueRatioWidget` | label-incorporation chart |
| `totalAbundanceWidget` | total abundance chart |
| `targetedQc` | Identity chart |
| `Choose Analysis Mode` | startup dialog window title |
| `Labelled isotope-tracing analysis` | labelled mode button |
| `Unlabelled targeted analysis` | unlabelled mode button |
| `Load Compounds/Parameter List` | File menu |
| `Export Session...` / `Import Session...` | File menu |

Do not click by tab order. File dialogs (`QFileDialog`) are not in this harness. Those features use the pytest commands in their feature files.

## Evidence

Proof lives in `artifacts/verify-pmanic/<feature>/`. Cleanup must leave it there.

Each drive writes:

- `<feature>.json` with `ok`, widget `objectName` / `hidden` / layout `index`, or dialog button texts
- `<feature>.png` from `QWidget.grab()`

Standards:

- Exercise the real widget the user would see. Do not poke private setters to fake a pass.
- Capture the action and the resulting JSON. A screenshot alone is not proof.
- `ok: false` is a failed feature, not an inconclusive harness.
- `./scripts/run.sh` is not a dry-run. It clears the user database.

Pytest is allowed only where a feature file names the exact test. That is the user-visible import/export path this harness cannot open.

## Cleanup

```bash
PYTHONPATH=src .venv/bin/python \
  .cursor/skills/verify-pmanic/scripts/verify_pmanic.py cleanup
```

Kills only a PID in `--pid-file` if you started one. Deletes `--scratch` only when the path contains `verify-pmanic`. Never deletes `artifacts/verify-pmanic/`. Never deletes `~/.manic_app/manic.db`.

## Helpers

`scripts/verify_pmanic.py` is the harness. Run it. Do not reimplement it.

```bash
PYTHONPATH=src .venv/bin/python .cursor/skills/verify-pmanic/scripts/verify_pmanic.py doctor
PYTHONPATH=src .venv/bin/python .cursor/skills/verify-pmanic/scripts/verify_pmanic.py drive analysis-mode
PYTHONPATH=src .venv/bin/python .cursor/skills/verify-pmanic/scripts/verify_pmanic.py cleanup
```
