# pMANIC verification map

This directory is the maintained source for verifying user-facing pMANIC behaviour. Read this index, then the matching feature file.

## Baseline preconditions

- Checkout builds with `uv sync`.
- `QT_QPA_PLATFORM=offscreen`.
- `PYTHONPATH=src`.
- Run `verify_pmanic.py doctor` and require `"app": "MANIC"` and `"run_sh_safe": false`.
- Do not start `./scripts/run.sh`. It clears `~/.manic_app/manic.db`.
- Do not drive a `MainWindow` the operator already has open.
- Sequential harness processes only. One `QApplication` per process.

## Driving conventions

- Start from the feature file's preconditions.
- Use `objectName` values and exact button / menu strings.
- Treat every command as literal.
- Widget features run through `verify_pmanic.py drive`.
- Import and session features run the pytest command the feature file names.
- Leave `artifacts/verify-pmanic/` in place after cleanup.

## Proof and skip reporting

- Capture JSON plus a grab screenshot for widget drives.
- Capture pytest stdout, stderr, and exit code for pytest drives.
- Record the feature ID and entry point on every artifact.
- An unreachable File dialog is a skip. Do not mark it verified through pytest.
- `ok: false` on `toolbar-unlabelled` means the Identity / abundance stack is wrong.

## Feature entry contract

Each feature file starts with an H1 and one paragraph. Then exactly four H2 sections: `Sub-features`, `How to get to it (user POV)`, `Driving it with verify-pmanic`, `Gotchas`.

## Features

- [Choose analysis mode](./analysis-mode.md) covers the startup dialog that locks Labelled or Unlabelled.
- [Labelled toolbar charts](./labelled-toolbar.md) covers Label Incorporation above Total Abundance.
- [Unlabelled toolbar charts](./unlabelled-toolbar.md) covers Identity above Total Abundance.
- [Load compounds](./load-compounds.md) covers the compound-list import the user starts from File.
- [Session method](./session-method.md) covers Export Session and Import Session.
