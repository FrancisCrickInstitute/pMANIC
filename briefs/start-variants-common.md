# Start screen variants: shared brief

You are one of three designers each building one variant of MANIC's start
screen: the panel in the graph area before data is loaded
(`src/manic/ui/start_panel.py`, 245 lines). The user will look at all three
side by side and pick one. This is a prototype for a taste decision, so the
screenshots are the deliverable; the code must still be clean and working
because the chosen one gets merged.

## Why

The user finds the current screen "a bit AI sloppy". See
`/Users/couttsj/Documents/_code/pMANIC-notes/reviews/round-4/shots/mac-light/02_empty_labelled.png`
and `ci-windows-latest-dark/03_compounds_only.png` in the same folder. Problems:
- The sidebar header already shows Compound list / Raw data / Internal
  standard and their state; the stepper card repeats it and the status bar
  repeats it a third time.
- Four sentences of grey helper text under the card.
- Numbered 1/2 badges for a two-step flow; shortcut text crammed into
  buttons; file types spelled out; Recent shows a bare "List" label and a raw
  path.
- A small left-aligned column floating in a big empty canvas.

Read `/Users/couttsj/Documents/_code/pMANIC-notes/design_spec.md` in full,
especially the last section "Taste, not AI slop" (binding), and the F9
anchors in `/Users/couttsj/Documents/_code/pMANIC-notes/rubric.md`. Aim for a
screen a careful human designer working only on MANIC would make: restrained,
specific to GC-MS work, with a little character. No template patterns.

## Constraints

- Work only in your worktree (your current checkout). Do not push.
- Before running anything: `ln -s /Users/couttsj/Documents/_code/pythonMANIC/testdata testdata`
  in the worktree root. Never commit it (`/testdata` is in `.git/info/exclude`;
  check `git status` before every commit). Run `uv sync` once.
- Files you may edit: `src/manic/ui/start_panel.py`; the start-panel hookup
  lines in `src/manic/ui/main_window.py` (around 252-256, 445-458 and the
  `start_panel.refresh(` call near 674) only if your design needs it; the
  start-panel rules in `src/manic/resources/style.qss`; and
  `tests/test_main_window_shell.py` where it asserts start-panel details you
  deliberately changed. Nothing else. Colours only from `theme` tokens; it
  must look right in light and dark and switch live.
- Keep every function the current panel offers: load compound list, load raw
  data folder (enabled after compounds), reopen recent compound lists and raw
  data folders, change analysis mode, open the quick start guide, and the
  hint that sessions are imported after loading the same data (wording is
  yours; it may move to a quieter place). Drag and drop onto the window must
  still work. Keyboard: the primary action gets initial focus (update the
  `setFocus()` line in `main_window.py` if you rename it). Shortcuts stay in
  the menus; show them with `QKeySequence.toString(NativeText)` if you show
  them at all.
- Labelled and unlabelled modes both use this panel; check both.
- No science changes. Tests: `uv run python -m pytest -q -p no:cacheprovider`
  must pass (684 at start). `uv run python scripts/ui_tour.py <dir> --scheme light`
  must still print `errors: 0`.

## Screenshots (the deliverable)

Write a small driver (copy what you need from `scripts/ui_tour.py`: isolated
DB and QSettings, `make_window`, `pump`) that saves these PNGs to
`/Users/couttsj/Documents/_code/uiux-scratch/start-variants/<your-variant>/`:

- `empty-first-run-{light,dark}.png`: labelled mode, nothing loaded, no recent files.
- `empty-with-recents-{light,dark}.png`: labelled mode, nothing loaded, with
  recent files seeded (two compound lists and two data folders; use the real
  `testdata/bench/labelled` and `testdata/unlabelled_synthetic` paths plus
  realistic made-up ones such as `~/Data/2026-10-14 13C glucose/`).
- `compounds-loaded-{light,dark}.png`: compound list loaded, raw data not yet.
- `small-1024x720-{light,dark}.png`: the with-recents state at 1024x720 (the
  Windows CI laptop size).
- `unlabelled-empty-light.png`.

Window size 1500x940 unless stated. Use `--scheme`-style forcing as the tour
does (`set_scheme`). Look at every PNG yourself in both schemes and iterate
until it looks deliberate and right. Then commit on your branch
(`feat(ui): ...`, `git add <files>` only, no Claude attribution, no
Co-Authored-By).

## Report back

Branch name and head SHA; the screenshot folder; one paragraph on the design
idea and why it fits MANIC; what you removed and where each removed function
now lives; tests and tour result.
