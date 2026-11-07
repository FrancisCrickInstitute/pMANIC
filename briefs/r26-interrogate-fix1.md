# Interrogate fix round 1 (before the PR)

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r18-linux.md` first and follow it (shared
rules, headless run, fences, report). Overrides: base commit `dfe4ec65`, 813 passed + 8 skipped at
base (suite ~3 min), scratch `/home/willyg/code/uiux-scratch/r26-fix/`. Bug fix playbook: reproduce
each defect on base first (the reviewers' probes are named below), fix the root cause, prove it with
a behaviour test that fails on base. The UI is rated 10/10: change nothing else a user would see;
the 2560 light and dark tours must stay pixel-identical to
`/home/willyg/code/uiux-scratch/m23/light-2560` and `dark-2560` (a toast caught at another moment is
the only acceptable difference).

Synthesis: `/home/willyg/code/pMANIC-notes/reviews/interrogate/synthesis.md`. Opus's findings and
probes: `/home/willyg/code/uiux-scratch/interrogate-opus/` (`findings.md`, `docs_scheme_probe.py`,
`dclick_probe.py`, `sel_probe.py`). Sol's probes: `/home/willyg/code/uiux-scratch/interrogate-sol/`
(`missing_sample_plot_probe.py`, `draft_order_ui_probe.py`, `draft_order_probe.py`).

Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r26-fix`
(branch `uiux/r26-fix`, base `dfe4ec65`; `testdata` linked). You may edit any file under
`src/manic/ui/` and `tests/`. Science fence as always.

1. Docs viewer (`documentation_viewer.py`): after a live scheme switch while the window is closed
   (or closing before the first page draws), it later shows "This page could not be displayed" with
   Retry for a good page. Base the paint check and its timeout on the window being visible, do not
   reload while closed (mark the page stale instead), and reload a stale or unrendered page when the
   window opens again. THIS IS A LOADING CHANGE: the QtWebEngine rules in the shared brief bind you
   (never start a load on a visible view while another load may still run), and
   `tests/test_documentation_viewer.py` must pass 30 consecutive runs with no crash: report the count.
   Test: open, let it draw, close, switch scheme, reopen; the page is rendered and no error shows.
2. Detailed view (`detailed_plot_dialog.py` ~133-146, `_plot_tic` ~779, `_plot_ms` ~809): stepping
   to a sample with no TIC / no spectrum leaves the previous sample's plots. Every no-data or failure
   state must redraw. Test: step from a sample with both to one with neither; the TIC and spectrum
   show the no-data state, not the previous sample's traces.
3. Integration drafts (`integration_window_widget.py` ~531-560): a draft is keyed by the order of its
   sample names; key it by the set (e.g. sorted tuple or frozenset). Test with real events: click each
   plot, type a left offset, press Ctrl+A (same set, other order): the draft value still shows.
4. Summary double-click to enlarge (`chart_style.py` `BarRows`, ~278): the first click of a
   double-click selects the row and replaces the grid's multi-selection before the popup opens. Make
   a double-click enlarge without touching the selection (e.g. defer the single-click selection by
   `QApplication.doubleClickInterval()` and cancel it on the double-click). Single click still selects.
   Test with the real click-then-double-click sequence.
5. Selection clicks (`main_window.py` `on_plot_selection_changed`, ~1708-1719): replace the Summary
   rebuild with `set_highlighted(selected)` on the three charts; nothing else on a selection change.
   Keep the comment true. Verify the highlight still shows in all three charts and the tip still
   follows (the transition matrix).
6. Nits: give the Summary charts a public `clear()` (and use it instead of the private
   `_clear_chart`); have `SummaryPanel` offer one place to clear / highlight / connect
   `sample_activated` if that removes the three repeated lists in `main_window.py`. Collapse the
   recovery dialog subclasses that exist only to rename a signal into `RecoveryDialog` with a
   `restored` signal, migrating both callers and deleting the subclass files.

Commit one concern each. Run the full suite, the five tours and the pixel comparison, and re-run the
reviewers' five probes against your worktree before you report.
