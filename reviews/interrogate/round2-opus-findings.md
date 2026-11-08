## Findings

### 1. [Critical] After a double-click opens a Summary popup, the next click on that chart does nothing
**Location**: `src/manic/ui/chart_style.py:292-305` (`BarRows.eventFilter`, the `_doubled` flag)
**Finding**: `_doubled` is set on `MouseButtonDblClick` and cleared only by a later left-button `MouseButtonRelease` on the viewport. Two cases leave it stuck at `True`, and the next real single click is then taken for "the release that ends a double-click" and dropped.
- **Left double-click that enlarges the chart (the main use).** The viewport's `mouseDoubleClickEvent` override (`total_abundance_widget.py:268`, `isotopologue_ratio_widget.py:373`, `targeted_qc_widget.py:244`) calls `ChartPopupDialog.exec()` inside the DblClick delivery. The trailing release then reaches the main window while the modal popup blocks it, so Qt drops it and the viewport never sees it.
- **Right-button double-click.** The DblClick branch has no button check, but the release branch needs `Qt.LeftButton`. A right double-click sets `_doubled`, and its right release never clears it. It also cancels any left click still waiting.

**Evidence**: I ran offscreen probes in the scratch folder.
- `probe_dbl.py` sends press, release, press and DblClick to a `TotalAbundanceWidget`. The real `ChartPopupDialog.exec()` runs, and the trailing release is injected through `QTest.mouseRelease(window.windowHandle(), …)` (the window-system path) while the popup is modal. Output: the viewport never receives that release, `after popup: _doubled = True`, the first click on S2 after the popup closes activates `[]`, and only the second click activates `['S2']`.
- `probe_right.py` does a right double-click, then a left click on S2: `_doubled = True`, activated `[]`.

The new test `test_a_click_on_a_summary_row_selects_its_sample_and_a_double_click_only_enlarges` misses this because it monkeypatches `ChartPopupDialog.exec` to return at once, then sends the trailing release itself. That is the one ordering where the flag gets cleared. So fix 4 swaps "a double-click replaces the selection" for "the first selection click after every enlarge is swallowed", in all three Summary charts.
**Suggestion**: Clear the flag on every press instead of relying on a release that may never arrive: `elif kind == QEvent.MouseButtonPress: self._doubled = False`. Qt sends DblClick in place of the second press, so "the last press was a DblClick" is exactly the state to track. Also limit the DblClick branch to `event.button() == Qt.LeftButton`. For the test, let the stubbed `exec` swallow the trailing release (or inject it through the window handle while a real modal runs), then assert that one later click activates.

### 2. [Nit] `_show_empty` sits under an unrelated orphaned comment
**Location**: `src/manic/ui/detailed_plot_dialog.py:86-94`
**Finding**: The comment "Same meaning as on the grid tiles: dashed steel blue bounds the integration window, solid grey marks the target tR or m/z." was already orphaned above `class DetailedPlotDialog`. The fix put `_show_empty` directly under it, so the comment now reads as the description of a helper that draws an empty plot.
**Evidence**: `git show dfe4ec65:src/manic/ui/detailed_plot_dialog.py` lines 86-88 show the comment directly above the class. At `52f6d0d5` it sits directly above `def _show_empty`.
**Suggestion**: Put `_show_empty` above that comment, or move the comment to the `add_vertical_line` calls in `_plot_eic` that it describes.

Checked and found sound:
- **Fix 1 (docs viewer stale page):** every path that shows the window goes through `open()` / `open_at()`. `load_markdown_file` clears `_stale`, so `open_at` does not load twice. A reload from `open()` starts while the window is hidden.
- **Fix 2 (detailed view no-data state):** `step_sample` resets `_eic_plot_error`, so stepping to a no-data sample does not carry an old error.
- **Fix 3 (drafts keyed by `frozenset`):** every `_drafts` access goes through `_draft_key`.
- **Fix 5 (selection only re-highlights):** every path that changes the data calls `_refresh_mode_charts` itself, so dropping the rebuild from the selection handler loses nothing.
- **Renames and removed recovery-dialog subclasses:** no callers remain in `src/`, `scripts/` or `tests/`.
- **Tests:** the eight touched test files pass offscreen (216 passed, 8 skipped).
