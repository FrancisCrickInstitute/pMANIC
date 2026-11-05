# Iteration 15 implementers: shared rules (Linux, headless)

You are one of three parallel implementers fixing review findings for the MANIC
desktop app (PySide6, GC-MS analysis). Two reviewers rate the app on a frozen
rubric. Round 12 scored 9.4 (Sol 9.6, Opus 9.2); the user wants 10. The
remaining gaps are edge cases, small losses and residual copy.
Your brief names your files and findings.

## Read first
- `/home/willyg/code/pMANIC-notes/design_spec.md`: binding fences
  and design system. Its last section, "Taste, not AI slop", is binding and
  includes the redundancy rule (the user considers repetition generally bad).
- `/home/willyg/code/pMANIC-notes/rubric.md`, especially the F9 anchors.
- The round 12 reports: `/home/willyg/code/pMANIC-notes/reviews/round-12/sol-review.md`
  and `opus-report.md` (same folder). The round-4 redundancy audit
  `/home/willyg/code/pMANIC-notes/reviews/round-4/redundancy-audit-sol.md`
  is already applied; do not reintroduce anything it removed.
  Screenshots they cite are in `/home/willyg/code/pMANIC-notes/reviews/round-12/shots/`;
  their own probe images and JSON are under `/home/willyg/code/uiux-scratch/review-r12-sol/`
  and `/home/willyg/code/uiux-scratch/review-r12-opus/` (matching the report).
  Do not edit anything in pMANIC-notes.

## Where you work
- Only your worktree (your current checkout). Do not push; I merge.
- First: `ln -s /home/willyg/code/uiux-testdata testdata` in
  the worktree root (it is in `.git/info/exclude`; never commit it), then `uv sync`.
- Edit only the files your brief assigns, plus NEW test files named
  tests named after the feature they protect (for example `tests/test_sidebar.py`); never name a test file after a round. If you need a change in a file you do not
  own, say so in your report with the exact hook; do not edit it.

## Running the app (this machine: headless Linux)
- In EVERY shell, first: `source ~/.local/qtdeps/libs.sh` (GL/font libraries unpacked
  without root, bundled Inter/DejaVu fonts standing in for the system font, TMPDIR off
  the small /tmp). Do not set QT_QPA_PLATFORM yourself for the tour; it picks its
  offscreen 2560x1410 screen.
- Tests: `uv run python -m pytest -q -p no:cacheprovider` takes about 4 minutes here
  (750 at base). While you work, run the test files your change touches; run the full
  suite once before you report.
- Tour: `uv run python scripts/ui_tour.py /home/willyg/code/uiux-scratch/r17-<group>/<name> --scheme light|dark`
  must print `errors: 0` (2560x1410 by default; about 3 minutes). Laptop sizes:
  `--size 1500x940`, `--size 1024x720`, and `QT_SCALE_FACTOR=1.5 ... --size 1280x800`.
- Drive states the tour does not show by copying `scripts/ui_tour.py` into your
  scratch folder and editing the copy. Probes set
  `QT_QPA_PLATFORM="offscreen:configfile=<worktree>/scripts/screen2560.json"`.
- Look at every PNG you produce with your Read tool, in BOTH light and dark.
- Reproduce each finding yourself before fixing it.

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
- Big screens first: the user's display is 2560x1440 at DPR 1.0. The tour renders that
  by default; look at it first. Laptop sizes (1500x940, 1280x800, 1024x720, 150%) must
  still work.
- Read the last three sections of `design_spec.md` (clean not cluttered, button
  spacing, pastel verdicts, big screens, both panels toggle). They are binding.
- Scope every widget stylesheet with a selector (`QChartView { ... }`), never
  bare declarations: a tooltip shown from a widget inherits its unscoped rules
  (a bare `background: transparent` made the summary tooltips invisible).
- Settled decisions in `reviewer_brief.md` ("Settled decisions") bind you too:
  no flag for labelled peaks outside the integration window; label colours stay;
  `manic_session_export/` stays; Settings stays one page per topic.

## Screenshots and probes run offscreen

`scripts/ui_tour.py` renders offscreen on a virtual 2560x1410 screen by default
(no window opens on the user's desktops). Use it as is; pass `--size 1500x940` or
`--size 1024x720` for laptop sizes and `QT_SCALE_FACTOR=1.5 ... --size 1280x800`
for 150%. Any probe script of your own must set
`QT_QPA_PLATFORM="offscreen:configfile=<repo>/scripts/screen2560.json"`. Never use
`--onscreen` (CI only).
