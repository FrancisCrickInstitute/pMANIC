# Iteration 22: a resting tip follows the chart actually under the pointer (round 19, Opus #1)

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r18-linux.md` first and follow it (shared
rules, headless run, fences, report). Overrides: base commit `f2c42d2c`, 813 passed + 8 skipped at
base, scratch `/home/willyg/code/uiux-scratch/r24-tipfix/`, round 19 reports:
`/home/willyg/code/pMANIC-notes/reviews/round-19/opus-report.md` (issue 1) and `sol-review.md`.
Opus's probes: `/home/willyg/code/uiux-scratch/review-r19-opus/` (`probe19b*`, `p19b/log.txt`,
`probe19d*`). Bug fix playbook: reproduce on base first, fix the root cause, prove it.

Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r24-tipfix`
(branch `uiux/r24-tipfix`, base `f2c42d2c`; `testdata` linked).
Files you own: `src/manic/ui/chart_style.py`, `targeted_qc_widget.py`, `total_abundance_widget.py`,
`isotopologue_ratio_widget.py`, `summary_panel.py`, and `tests/test_identity_chart.py`,
`tests/test_chart_summaries.py`.

## The defect
Unlabelled mode, pointer resting on the Summary, press Down through compounds. When the new compound
changes the Identity panel's height (e.g. Lactate -> Glycine, Glycine -> Serine), the Peak area chart
moves under the still pointer. `BarRows.refresh()` with no argument reuses `_pointer`, the
viewport-local point stored at the last mouse event (`chart_style.py` ~229-249); Qt sends no move,
Enter or Leave when a widget moves under a still pointer. So the tip names the row that used to be
under the pointer (drawn up to 344 px away, held by `_TIP_HOLD_MS`), or, on the Identity chart, can
hide instead of updating (likely `refresh()` running before the chart lays out its new columns).
16 of 28 of Opus's transitions disagree; 12 without a layout change are right.

## Fix at the root
When `refresh()` runs without a pointer event, decide from where the pointer actually is now,
after the layout has settled: the viewport under the real cursor (`QCursor.pos()` mapped into the
viewport, and only if that viewport is the visible widget under it), or none -> hide. Run the
data-change refresh after the chart lays out (e.g. a single-shot to the next event-loop pass). Also
handle the case the chart itself moves or resizes under a resting pointer.
Caution from iteration 20: offscreen QTest moves a shared cursor and an earlier test's window can be
under it, so a fix or test that reads `QCursor.pos()` must make sure the widget under the cursor is
this viewport (e.g. `QApplication.widgetAt` / the viewport's visible region and window), not just
that the mapped point falls inside its rectangle.

## Proof
Add one case to the transition matrix: rest on a Peak area bar, switch to a compound whose Identity
panel has a different height, assert the tip equals the text of the row actually under the pointer
now, or that it is hidden when no row is there. It must fail on base. Re-run Opus's `probe19b`
against your worktree (expect 28 of 28 agreeing) and `probe19d`. The full suite must pass in one run
and in the order pytest uses (the matrix runs among other tests). Run the five tours.
