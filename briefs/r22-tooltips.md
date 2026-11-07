# Iteration 20: one tooltip owner for Summary and popup charts

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r18-linux.md` first and follow it (shared
rules, headless run, fences, report). Overrides: base commit `e33c52c9`, 774 tests at base, scratch
`/home/willyg/code/uiux-scratch/r22-tooltips/`, the round 17 reports are
`/home/willyg/code/pMANIC-notes/reviews/round-17/sol-review.md` and `opus-report.md`. Sol's probe:
`/home/willyg/code/uiux-scratch/review-r17-sol/popup_transition_final.py` (+ `popup_transition_final/`).

Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r22-tooltips`
(branch `uiux/r22-tooltips`, base `e33c52c9`; `testdata` linked).
Files you own: `src/manic/ui/chart_popup_dialog.py`, `chart_style.py`, `identity_chart.py`,
`targeted_qc_widget.py`, `total_abundance_widget.py`, `isotopologue_ratio_widget.py`, and the tests
`tests/test_identity_chart.py`, `tests/test_chart_popups.py`, `tests/test_chart_summaries.py`,
`tests/test_main_window_shell.py` (item 3 only).

## Why this iteration exists
Rounds 15, 16 and 17 each fixed one tooltip transition and the next review found another. The
census (`/home/willyg/code/pMANIC-notes/reviews/drivers/tooltip_census.py <worktree>`) shows the
asymmetry: the Summary charts have ONE tooltip owner (`SummaryRows.refresh()` in `chart_style.py`,
deciding from the pointer's last position); the enlarged popup has THREE independent ones
(`_on_identity_cell_hover` hides, `_show_row_tip` shows/hides, `closeEvent` hides) plus
`show_identity_tooltip`. Round 17's defect (Sol #1): in the Identity popup, cell -> shortened sample
name (same or other row) then a rest shows no full-name tip; cell leave hides unconditionally and the
row filter only refreshes when the row changes.

## Work
1. Make the popup use the same single owner as the Summary: whatever is under the pointer (a cell,
   a row name, a bar, nothing) decides the tip, recomputed on every move, on cell enter/leave, on the
   resting tooltip request, and on leave/close. Delete the popup's own show/hide paths so the census
   shows one owner (plus the owner's callers). Keep every tip text exactly as today (cell detail,
   full name, values, "No ratio" notes), keep click/keyboard selection and the 300 ms Qt hide
   behaviour.
2. Replace the per-case hover tests with one transition-matrix test (parametrized) over the Summary
   Identity chart and the Identity popup (and the Peak area chart/popup where a transition applies):
   enter name, enter cell, cell -> same-row name, cell -> other-row name, cell -> neighbour cell,
   name -> cell, a rest with no further movement after each, a 1 px move, leave the chart, close.
   Each case asserts the exact visible tip text (or none). Use real QWindow mouse events, exactly one
   move per transition. It must reproduce Sol's round 17 failure on base. Delete hover tests it makes
   redundant (the user's directive: no redundant tests).
3. Sol's note: `tests/test_main_window_shell.py::test_long_session_name_toast_stays_inside_the_window`
   (or the toast test Sol names in `/home/willyg/code/uiux-scratch/review-r17-sol/toast/`) requires
   an ellipsis even when the whole text fits under the test's font. Make it assert the user-visible
   guarantee (the toast stays inside the window, buttons inside the toast, full text recoverable),
   independent of font metrics. No app change.

Run Sol's `popup_transition_final.py` against your worktree in light and dark and include its
results. Prove at 2560 light and dark.
