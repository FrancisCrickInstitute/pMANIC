# Iteration 14, group charts (resumed on the Linux machine)

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r16-linux.md` first and follow it.

Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r16-charts`
(branch `uiux/r16-charts`, base `970b288` = feat before the shell merge). `testdata` is
already linked. Scratch: `/home/willyg/code/uiux-scratch/r16-charts/`.

## Starting point: an unverified snapshot

The worktree holds, uncommitted, a snapshot of the previous charts implementer's
work, stopped mid-edit when the user moved machines (11 files; see `git diff`).
Nobody has run or reviewed it. It contains placeholder `pass` lines in
`isotopologue_ratio_widget.py` where code was about to go, and some items were not
started. Judge every hunk: keep what is right, finish what is half done, discard
what is wrong. You may throw it all away (`git checkout -- .`) if starting clean is
better. Commit your work in units of one concern each; do not commit the snapshot
as-is.

## Files you own

`src/manic/ui/channel_chips.py`, `chart_header.py`, `chart_style.py`,
`detailed_plot_dialog.py`, `graphs.py`, `plot_tile.py`, `isotopologue_ratio_widget.py`,
`total_abundance_widget.py`, `targeted_qc_widget.py`, `identity_chart.py`,
`chart_popup_dialog.py`, `summary_panel.py`, and the matching feature-named tests
(`tests/test_chart_summaries.py`, `tests/test_identity_chart.py`, `tests/test_chart_popups.py`,
`tests/test_detailed_plot_dialog.py`, `tests/test_tile_y_scale.py`). The shell implementer's work
(`main_window.py`, `left_toolbar.py`, `sidebar_widgets.py`, the list widgets,
`settings_window.py`, docs) is already merged on feat; do not edit those files. If you
need a hook there, report it.

## Findings (round 11; reproduce each first, then fix)

1. Short-cohort Summary stays together (Sol #4). With two labelled samples at 2560,
   the Label incorporation heading sits at the top, its key floats mid-height and its
   axis and bars sit near the bottom. Keep heading, key, axis and rows together at the
   top; spare height goes below the whole chart group. (`isotopologue_ratio_widget.py`,
   `summary_panel.py`.)
2. Roomy Summary names (Sol #8). Summary sample names use the 10 px axis font even when
   rows are tall. Grow the category labels with row height (up to the tile caption
   size), keeping the minimum and scrolling on small windows. Apply to Label
   incorporation, Peak area and Identity.
3. One qualifier message (Sol #9). When a compound's qualifier cannot be assessed
   (Glycine in `testdata/unlabelled_synthetic`), the grid note and the Identity panel
   both say so. One home while the Summary is open (the Summary, with the repair link);
   the grid note returns when the Summary is hidden.
4. Plain legend entries (Sol #10). The channel legend above the grid draws bordered
   capsules that look like buttons though they do not toggle. Use a light inline
   swatch-and-name legend like the detailed view's, keeping every channel, line style,
   tooltip and colour (label colours are settled; do not change them).
5. Names elide in the middle everywhere, including headers (Sol #3, Opus #7). The grid
   header's compound title and the detailed view's compound name clip without an
   ellipsis or tooltip and squeeze the sample name. Elide in the middle with the full
   text on hover, and keep a useful minimum width for the sample name. Names must be
   cut one way across the app (the shell implementer made the sidebar lists middle-
   elide with tooltips).
6. Larger fit-on-screen minimum tile (Sol #5). At 1024x720 thirty labelled samples fit
   five by six at about 130x95, which leaves only a strip for the peak. Raise the
   minimum useful plot rectangle (counting caption, ticks and badges) and fall back to
   the existing large-tile scrolling when it cannot fit. Keep automatic sizing.
7. One-row header at 1024 (Opus #4). At 1024 with the Summary open, the grid header
   wraps onto two rows. Keep it to one row; folding the two scale toggles into one
   "Scale" menu button when space is short is the snapshot's approach (the toggles,
   their shortcuts and View menu entries must all keep working). Buttons never touch
   (8 px apart; 4 px inside segmented controls).

Prove each at 2560 light and dark first, then 1500x940, 1024x720 and 150% 1280x800.
Use `testdata/bench/labelled`, `testdata/bench/unlabelled` and
`testdata/unlabelled_synthetic`; for findings 1 and 5 make a copy of a dataset with two
samples and with long compound and sample names under your scratch folder.
