# Iteration 6 implementers: shared rules (Mac)

You are one of three parallel implementers fixing review findings for the MANIC
desktop app (PySide6, GC-MS analysis). Two reviewers rate the app on a frozen
rubric; target 8/10 average. Round 4 scored 7.75: F1..F8 are about 8, and the
new F9 "Taste (not AI slop)" is 6 to 6.5. F9 and redundancy are the main gap.
Your brief names your files and findings.

## Read first
- `/Users/couttsj/Documents/_code/pMANIC-notes/design_spec.md`: binding fences
  and design system. Its last section, "Taste, not AI slop", is binding and
  includes the redundancy rule (the user considers repetition generally bad).
- `/Users/couttsj/Documents/_code/pMANIC-notes/rubric.md`, especially the F9 anchors.
- The round 4 reports: `/Users/couttsj/Documents/_code/pMANIC-notes/reviews/round-4/sol-review.md`
  and `opus-report.md`, and the redundancy audit
  `/Users/couttsj/Documents/_code/pMANIC-notes/reviews/round-4/redundancy-audit-sol.md`
  (97 rows: apply every "Remove" row that touches your files; keep the "Keep" rows).
  Screenshots they cite are in `/Users/couttsj/Documents/_code/pMANIC-notes/reviews/round-4/shots/`;
  `extra/` and `supplement/` paths are under `/Users/couttsj/Documents/_code/uiux-scratch/review-r4b-*/`
  and `/Users/couttsj/Documents/_code/uiux-scratch/redundancy-audit-sol/`.
  Do not edit anything in pMANIC-notes.

## Where you work
- Only your worktree (your current checkout). Do not push; I merge.
- First: `ln -s /Users/couttsj/Documents/_code/pythonMANIC/testdata testdata` in
  the worktree root (it is in `.git/info/exclude`; never commit it), then `uv sync`.
- Edit only the files your brief assigns, plus NEW test files named
  `tests/test_r7_<your group>_*.py`. If you need a change in a file you do not
  own, say so in your report with the exact hook; do not edit it.

## Running the app (macOS, real display)
- Tests: `uv run python -m pytest -q -p no:cacheprovider` (686 pass at start, about a minute).
- Tour: `uv run python scripts/ui_tour.py /Users/couttsj/Documents/_code/uiux-scratch/r7-<group>/<name> --scheme light|dark`
  must print `errors: 0`. `QT_SCALE_FACTOR=1.5` with `--size 1280x800` is the
  small-laptop check (the screen becomes 1008x633 logical).
- Drive states the tour does not show by copying `scripts/ui_tour.py` into your
  scratch folder and editing the copy.
- Look at every PNG you produce with your Read tool, in BOTH light and dark.
- Disk is nearly full on this machine. Keep only the screenshot folders you
  cite in your report; delete the rest before you finish.

## Fences
- No science changes: `git diff <your base> -- src/manic/processors src/manic/models src/manic/validation src/manic/sheet_generators src/manic/io` stays empty.
- No lost functionality: moving a control is fine; removing one is not.
  Removing a duplicate display or a duplicate entry point is fine as long as one
  clear path to every function remains.
- Every colour from `theme` tokens; right in light and dark; switches live.
- Windows parity: no hard-coded fonts, native shortcut text, logical px.
- Tests stay green. Add a behaviour test for each bug fix (call the code the way
  the app does and assert the visible result). Update a cosmetic UI test only
  where you deliberately changed that detail.
- One wording for "no internal standard": the selectable item reads
  "No internal standard" ("No Internal Standard" in menus, which use Title Case),
  the status value reads "None", and no separate "Optional"/"(optional)" label.
- Commits: one concern each, `git add <files>` only (never `-A`), never commit
  `bench/HILLCLIMB.md`, `testdata`, or a symlink. No Claude attribution, no
  Co-Authored-By. Messages like `fix(ui): ...`. Comments only for a non-obvious why.

## Report back
Branch head SHA; commits; per finding what you changed and the screenshot path
that proves it (light and dark); audit rows applied (by ID) and any you skipped
with the reason; tests added; tests/tour result; anything left undone and why;
any hook you need in a file you do not own.
