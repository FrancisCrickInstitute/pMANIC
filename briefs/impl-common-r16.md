# Iteration 14 implementers: shared rules (Mac)

You are one of three parallel implementers fixing review findings for the MANIC
desktop app (PySide6, GC-MS analysis). Two reviewers rate the app on a frozen
rubric. Round 11 scored 9.2 (Sol 9.4, Opus 9.0); the user wants 10. The
remaining gaps are edge cases, small losses and residual copy.
Your brief names your files and findings.

## Read first
- `/Users/couttsj/Documents/_code/pMANIC-notes/design_spec.md`: binding fences
  and design system. Its last section, "Taste, not AI slop", is binding and
  includes the redundancy rule (the user considers repetition generally bad).
- `/Users/couttsj/Documents/_code/pMANIC-notes/rubric.md`, especially the F9 anchors.
- The round 11 reports: `/Users/couttsj/Documents/_code/pMANIC-notes/reviews/round-11/sol-review.md`
  and `opus-report.md` (same folder). The round-4 redundancy audit
  `/Users/couttsj/Documents/_code/pMANIC-notes/reviews/round-4/redundancy-audit-sol.md`
  is already applied; do not reintroduce anything it removed.
  Screenshots they cite are in `/Users/couttsj/Documents/_code/pMANIC-notes/reviews/round-11/shots/`;
  `extra/`, `supplement/`, `flows/` and `diagnostic/` paths are under `/Users/couttsj/Documents/_code/uiux-scratch/review-r11-*/`
  (`review-r11-sol` or `review-r11-opus`, matching the report).
  Do not edit anything in pMANIC-notes.

## Where you work
- Only your worktree (your current checkout). Do not push; I merge.
- First: `ln -s /Users/couttsj/Documents/_code/pythonMANIC/testdata testdata` in
  the worktree root (it is in `.git/info/exclude`; never commit it), then `uv sync`.
- Edit only the files your brief assigns, plus NEW test files named
  `tests named after the feature they protect (for example `tests/test_sidebar.py`); never name a test file after a round`. If you need a change in a file you do not
  own, say so in your report with the exact hook; do not edit it.

## Running the app (macOS, real display)
- Tests: `uv run python -m pytest -q -p no:cacheprovider` (note the count at your base; about a minute).
- Tour: `uv run python scripts/ui_tour.py /Users/couttsj/Documents/_code/uiux-scratch/r16-<group>/<name> --scheme light|dark`
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

## Also binding this round
- The user is happy with the graphs. Do not change the isotopologue colours
  (`colors.label_colors`) or the plot traces' look; the round-5 suggestion to
  swap the tab10 palette is declined. Other chart improvements a review asks
  for are welcome (the user approved larger tiles).
- No redundant code or tests. Add a test only for a behaviour a user would
  notice, calling the code as the app does and asserting the literal visible
  result. Put it in the existing feature-named test file. Delete code your change
  makes dead in your files. A cleanup pass already removed dead code; keep it gone.
- Functional first: a broken, misleading or silent path outranks styling.
- QtWebEngine: never start a load on a visible QWebEngineView while another
  load may still run (that segfaulted and was reverted in b804ecf). Any change
  to the documentation viewer's loading must pass 30 consecutive runs of
  `tests/test_documentation_viewer.py` with no crash; report the count.
- Never call `setVisible(True)`/`show()` on a widget before it has a parent:
  a parentless widget shown becomes its own window, which on Windows takes
  activation and closes any open popup (this broke the standard chooser).
- No Python `QAccessible.installFactory`: it runs for every widget once
  accessibility is active and segfaulted. Use names, descriptions and Qt's
  built-in roles and states.
- Do not run `uv sync` or create worktrees while a tour is running on this
  machine; it has killed tours mid-run.
- Big screens first: the user's display is 2560x1440 at DPR 1.0. Render it with
  `QT_QPA_PLATFORM="offscreen:configfile=/Users/couttsj/Documents/_code/pMANIC-notes/briefs/screen2560.json" uv run python scripts/ui_tour.py <dir> --size 2560x1410 --scheme light|dark`
  and look at it first; laptop sizes (1500x940, 1280x800, 1024x720, 150%) must still work.
- Read the last three sections of `design_spec.md` (clean not cluttered, button
  spacing, pastel verdicts, big screens, both panels toggle). They are binding.
- Scope every widget stylesheet with a selector (`QChartView { ... }`), never
  bare declarations: a tooltip shown from a widget inherits its unscoped rules
  (a bare `background: transparent` made the summary tooltips invisible).
- Settled decisions in `reviewer_brief.md` ("Settled decisions") bind you too:
  no flag for labelled peaks outside the integration window; label colours stay;
  `manic_session_export/` stays; Settings stays one page per topic.
- The monitor is attached: run tours for real at `--size 2560x1410`.

## Screenshots and probes run offscreen

`scripts/ui_tour.py` renders offscreen on a virtual 2560x1410 screen by default
(no window opens on the user's desktops). Use it as is; pass `--size 1500x940` or
`--size 1024x720` for laptop sizes and `QT_SCALE_FACTOR=1.5 ... --size 1280x800`
for 150%. Any probe script of your own must set
`QT_QPA_PLATFORM="offscreen:configfile=<repo>/scripts/screen2560.json"`. Never use
`--onscreen` (CI only).
