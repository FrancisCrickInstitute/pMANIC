# Iteration 18, group polish (round 15 findings)

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r18-linux.md` first and follow it (shared
rules, headless run, fences, report). Overrides: base commit `e640bf03`, 773 tests at base, scratch
`/home/willyg/code/uiux-scratch/r20-polish/`, the round 15 reports are
`/home/willyg/code/pMANIC-notes/reviews/round-15/sol-review.md` and `opus-report.md` (their probes:
`/home/willyg/code/uiux-scratch/review-r15-sol/r15_normal/` and `/home/willyg/code/uiux-scratch/review-r15-opus/probe_c/`).

Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r20-polish`
(branch `uiux/r20-polish`, base `e640bf03`; `testdata` linked).
Files you own: `src/manic/ui/targeted_qc_widget.py`, `identity_chart.py`, `chart_style.py`,
`matplotlib_plot_widget.py`, and their feature-named tests (`tests/test_identity_chart.py`,
`tests/test_chart_summaries.py`, `tests/test_detailed_plot_dialog.py`).

Round 15 averaged 9.95 (Sol 9.9, Opus 10.0). These are the last findings. Keep each change minimal.

1. Both reviewers: on the Identity Summary chart, one mouse move from a qualifier cell straight onto
   a sample name (the same row's or another row's), then a pause, shows the cell's stale detail or
   no tip at all until the next mouse move. Cause (Opus, Sol agree): `SummaryRows.eventFilter`
   (`chart_style.py`) runs before the scene and reads `_hovered_cell` before the cell's
   `hovered(False)` clears it; `_on_grid_hovered`'s leave branch (`targeted_qc_widget.py` ~254)
   then calls `QToolTip.hideText()`; the filter then swallows the resting ToolTip event. Fix it at
   the root with one owner of the tooltip deciding from the current pointer position (for example,
   on cell leave clear `_hovered_cell` and show the current row's tip at `QCursor.pos()` when the
   pointer is over a row, instead of hiding). Test with exactly ONE move event from cell to name,
   then a rest; the existing test at `tests/test_identity_chart.py` ~222 sends two moves, which
   masks the case. The test must fail on base.
2. Sol #2: the Identity cell tooltip repeats the qualifier identifier ("Qualifier 1  Failed" then
   "Qualifier 1  expected 0.450  ±25%  observed 0.815", from `identity_chart.py` ~177). Say the
   identifier once and keep the status and every number. Check the popup's cell tooltips read the
   same.
3. Opus #2: closing a detailed view with a draw queued runs `_on_draw` -> `_place_full_scan_button`
   after `cleanup()` set `self.ax = None` (`matplotlib_plot_widget.py`), and matplotlib prints a
   traceback. Return early when the widget has been cleaned up. A test that closes the view with a
   draw pending and asserts no exception reaches the callback (or the log).

Prove 1 and 2 at 2560 light and dark (unlabelled data, Alanine) with screenshots of the tips.
