# Iteration 15, group charts

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r17-linux.md` first and follow it.
Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r17-charts`
(branch `uiux/r17-charts`, base `fd447a30`; `testdata` linked). Scratch: `/home/willyg/code/uiux-scratch/r17-charts/`.

Files you own: `src/manic/ui/graphs.py`, `plot_tile.py`, `chart_style.py`, `chart_header.py`,
`chart_popup_dialog.py`, `detailed_plot_dialog.py`, `matplotlib_plot_widget.py`,
`total_abundance_widget.py`, `isotopologue_ratio_widget.py`, `targeted_qc_widget.py`,
`identity_chart.py`, `channel_chips.py`, `summary_panel.py`, and their feature-named tests
(`tests/test_plot_grid_ui.py`, `tests/test_chart_summaries.py`, `tests/test_chart_popups.py`,
`tests/test_identity_chart.py`, `tests/test_detailed_plot_dialog.py`, `tests/test_tile_y_scale.py`).
Others own `main_window.py`, the sidebar, Settings, the docs and `documentation_viewer.py`.

Findings (round 12; reproduce each first):
1. Opus #7 / Sol #6: in a normal 30-sample labelled Summary at 2560 the names stay 10 px on ~20 px
   rows, finer than the 13 px tile captions. Let them reach 11-12 px when rows have room (the
   short-cohort scaling already works); keep the minimum and scrolling on small windows.
2. Opus #4: the Peak area Summary draws nothing for zero or <0.01 samples, while Label
   incorporation beside it shows "—" and the popup shows "<0.01"/"0". Mark them consistently.
3. Opus #6: in unlabelled mode with the Summary open the qualifier swatches in the legend are grey
   while their traces are green/red (validated/failed); the only colour key is the Identity footer,
   which describes cells, not lines. Make the line colours explained where the lines are, without
   duplicating the Identity key (one home for each piece of information).
4. Sol #7: the folded "Scale" button hides the active policy (Shared Y on shows only "Scale",
   tooltip "Plot y-scale"). Let it name or mark the active policy, with the full state in its
   tooltip; keep the one-row header and both commands.
5. Sol #9: chart popup compound headings are plain QLabels that force a 600 px popup to 707 px.
   Reuse `HeaderName` (middle elision, full name on hover) like the grid and inspector.
6. Sol #10: the inspector (detailed view) does not show a sample's non-default curve-fit override
   that the grid caption shows. Carry that existing label into the inspector header area; no new
   control.
7. Regression test for the time-tick freeze fixed in ccc9554f (`chart_style.set_nice_ticks` flip
   between two steps at tile widths where the chosen step moves the plot edge): sweep one tile's
   width across ~150-260 px in 1 px steps so it crosses any font's band, and assert a user-visible
   result at each width (the tick interval is the same on two reads 100 ms apart, and a QTimer
   still fires). pytest-timeout is not installed, so guard against a hang (e.g. disconnect after
   ~50 plotAreaChanged emissions and fail with "ticks never settled at N px"). Prove it fails on
   the parent of ccc9554f and passes now. Keep it short; put it in the existing feature test file.
8. `tests/test_plot_grid_ui.py::_show_grid_with_viewport` waits a fixed 400 ms after a resize; on a
   slow machine the 200-tile layout is not finished and the test reads a mid-layout tile height.
   Wait for the layout to settle instead (e.g. `QTest.qWaitFor` on the grid shape and tile size).

Prove each at 2560 light and dark, then the laptop sizes.
