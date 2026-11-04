# Iteration 3 implementers: shared rules

You are one of three parallel implementers fixing review findings
for the MANIC desktop app (PySide6). Two reviewers rate the app on a frozen
rubric; target 8/10. Your brief names your worktree, your files and your findings.

## Read first
- `/home/willyg/code/pMANIC-notes/design_spec.md`: binding fences and the design system.
- `/home/willyg/code/pMANIC-notes/rubric.md`.
- The round 1 reviews, for detail on your findings:
  `/home/willyg/code/pMANIC-notes/reviews/round-1/sol-review.md` and `opus-report.md`
  (screenshots in `reviews/round-1/shots/`, macOS light). Do not edit anything in pMANIC-notes.

## Where you work
- Only your worktree (absolute path in your brief). Run every command with it as the
  working directory; edit by absolute path. Never touch `/home/willyg/code/pMANIC`
  itself or any other worktree. Do not push; I merge.
- Edit only the files your brief assigns, plus NEW test files named
  `tests/test_r3_<your group>_*.py`. If you truly need a change in a file you do not
  own, say so in your report with the exact hook you need; do not edit it.

## Running the app (headless Linux box, no display)
`source ~/.local/qtdeps/env.sh` in every shell first. Then:
- Tests: `uv run python -m pytest -q -p no:cacheprovider` (592 pass at start).
- Tour: `uv run python scripts/ui_tour.py /home/willyg/code/uiux-scratch/<group>/<name> --scheme light|dark`,
  must print `errors: 0`. Data in `testdata/` is a symlink: never commit it.
- Drive states the tour does not show by copying `scripts/ui_tour.py` to
  `/home/willyg/code/uiux-scratch/<group>/` and editing the copy (e.g. switch compounds, filter, hover,
  open menus, resize to 1280x800 and 1024x768, `QT_SCALE_FACTOR=1.5`).
- Look at every PNG you produce with your Read tool, in BOTH light and dark.
  Downscaled contact sheets via `uv run --with pillow python ...` save context.

## Fences
- No science changes: `git diff 94a4c11a -- src/manic/processors src/manic/models src/manic/validation src/manic/sheet_generators src/manic/io` stays empty.
- No lost functionality: moving a control is fine, removing one is not.
- Every colour from `theme` tokens; it must look right in light and dark and switch live.
- Windows parity: no hard-coded fonts, native shortcut text, logical px.
- Tests stay green. Add a behaviour test for each bug fix (call the code the way the
  app does, assert the visible result). Update a cosmetic UI test only where you
  deliberately changed that detail.
- Commits: one concern each, `git add <files>` only (never `-A`), never commit
  `bench/HILLCLIMB.md`, `testdata`, or a symlink. No Claude attribution, no
  Co-Authored-By. Messages like `fix(ui): ...`. Comments only for a non-obvious why.

## Report back
Branch head SHA; commits; per finding what you changed and the screenshot path that
proves it (light and dark); tests added; tests/tour result; anything left undone and
why; any hook you need in a file you do not own.

## Since round 2
- Base commit for this iteration is `94a4c11a` (feat/ui-ux-overhaul). The round 2 reviews are
  `/home/willyg/code/pMANIC-notes/reviews/round-2/sol-review.md` and `opus-report.md`; their
  evidence paths under `/tmp/review-r2-*` can be read. Some findings they list were fixed after
  they reviewed 6fc71eb5 (menu wording, checklist red copy, Review menu docs): check each finding
  against your base before working on it.
- Write all scratch output under `/home/willyg/code/uiux-scratch/<group>/`, never under `/tmp`
  (a shared RAM disk that has filled up). env.sh already points TMPDIR off /tmp.
