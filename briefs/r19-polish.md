# Iteration 17, group polish (last three round 14 findings)

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r18-linux.md` first and follow it (shared
rules, headless run, fences, report). Overrides: base commit `b99e2e22`, 771 tests at base, scratch
`/home/willyg/code/uiux-scratch/r19-polish/`, the round 14 reports are
`/home/willyg/code/pMANIC-notes/reviews/round-14/opus-report.md` and `sol-review.md` (Opus's probe
images are under `/home/willyg/code/uiux-scratch/review-r14-opus/`).

Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r19-polish`
(branch `uiux/r19-polish`, base `b99e2e22`; `testdata` linked).
Files you own: `src/manic/ui/targeted_qc_widget.py`, `identity_chart.py`, `sidebar_widgets.py`,
`chart_style.py` (only if the shared row helper needs it), and their feature-named tests.

Round 14 averaged 9.95 (Sol 10.0, Opus 9.9). These three small inconsistencies are all that stand
between the app and 10. Keep each change minimal; add nothing that clutters.

1. Opus #1: the Identity Summary chart attaches the shared `SummaryRows` handler without a row
   tooltip and keeps a static view tooltip ("Click a row to select its plot; double-click to
   enlarge"), so hovering a cut sample name (e.g. "Sampl…_fail" at 1500x940 or 150%) shows the
   generic tip, while Peak area and Label incorporation names show the full name and value. Give
   Identity rows the same behaviour: hovering a row's name shows the full sample name and its
   qualifier states; drop the static view tooltip. Keep the per-cell tooltips.
2. Opus #2: the sidebar's internal-standard status value (`sidebar_widgets.py` ~209, `ElidedLabel()`
   with the default end elision and no hover) cuts a long name at the end, while the compound list
   below and Settings cut in the middle with a full-name tooltip. Use middle elision with hover.
3. Opus #3: the Identity header says "1 sample failed" (samples) while the footer tally says
   "✕ 2" (cells), which can read as a contradiction. Make the units unambiguous with the least
   text (for example name the unit once in the tally, or let one count go); one home for each
   number.

Prove each at 2560 light and dark and at 150% dark (unlabelled data; make a copy with a long
internal-standard name under your scratch folder for item 2). Behaviour tests in the existing
feature-named test files.
