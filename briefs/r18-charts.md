# Iteration 16, group charts

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r18-linux.md` first and follow it.
Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r18-charts`
(branch `uiux/r18-charts`, base `72561139`; `testdata` linked). Scratch: `/home/willyg/code/uiux-scratch/r18-charts/`.

Files you own: `src/manic/ui/graphs.py`, `plot_tile.py`, `chart_style.py`, `chart_header.py`,
`chart_popup_dialog.py`, `detailed_plot_dialog.py`, `total_abundance_widget.py`,
`isotopologue_ratio_widget.py`, `targeted_qc_widget.py`, `identity_chart.py`, `channel_chips.py`,
`colors.py` (UI colours only; never `PEAK_VERDICT_FILL` / `QUALIFIER_OUTCOME_FILL`),
`summary_panel.py`, and their feature-named tests (`tests/test_plot_grid_ui.py`,
`tests/test_chart_summaries.py`, `tests/test_chart_popups.py`, `tests/test_identity_chart.py`,
`tests/test_detailed_plot_dialog.py`, `tests/test_ui_formatting.py`). Others own `main_window.py`,
Settings, the start panel, the checklist and the sidebar. If you need a `main_window.py` hook, say so.

Findings (round 13; reproduce each first; the reviewers' probe images and JSON are under
`/home/willyg/code/uiux-scratch/review-r13-sol/` and `review-r13-opus/`):
1. Opus #1: at 150% (`QT_SCALE_FACTOR=1.5 --size 1280x800`), selecting a sample makes the Peak
   area Summary's names shrink, lose their ellipsis and clip at the card edge
   ("ample_04_ratio_fail"). One cohort must keep one name size and one elision rule whether or not
   a plot is selected, at every size.
2. Opus #2 and #4: the qualifier QC key (header) lists Validated/Failed on compounds where no
   qualifier is assessed (Glycine, Serine in `testdata/unlabelled_synthetic`), and with the Summary
   open the key appears twice (header and Identity footer). One home for each piece of
   information: the header key explains the line colours and shows only states that can occur for
   this compound (none when nothing is assessed); the Identity footer keeps its counts without
   repeating the key. Decide the cleanest split and justify it.
3. Sol #7: a zero-area Summary row shows "0" but has no hover; normal bars show the full sample name
   and area. Resolve hover by row so empty and tiny rows show the same text.
4. Sol #9: clicking an Identity cell selects that sample's plot; clicking a Peak area or Label
   incorporation bar does nothing. Make a single click on a Summary row select its sample in every
   Summary chart; double-click still enlarges.
5. Sol #8: Identity validated checkmarks are faint (2.76:1 light, 3.41:1 dark against their cell).
   Use an ink that reaches at least 4.5:1 against the actual cell fill; keep cell meaning and the
   trace colours.
6. Sol #11: the popup footer says "Return or click to open a plot", but the first Return only
   outlines the first row. Make the hint true (e.g. "↑↓ to choose · Return to inspect"); keep the
   select-then-open behaviour.
7. Sol #12: the enlarge tooltip "Enlarge with sample names (or double-click the chart)" promises
   names the Summary already shows. Shorten it to the action, keep the double-click alternative.

Prove each at 2560 light and dark, then 1500x940, 1024x720 and 150% 1280x800.
