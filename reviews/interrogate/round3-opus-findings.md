## Findings

The fix itself is correct. Both round 2 probes now pass on 5d27d2bc: `probe_dbl.py` shows the first S2 click after the popup activating `['S2']`, and `probe_right.py` shows `_doubled = False` after a right double-click and the next left click activating `['S2']`. The full suite passes offscreen (820 passed, 8 skipped). Whether Qt sends a press before `MouseButtonDblClick` or not, the result is the same: the press clears the flag and the double-click sets it. A release can only reach the viewport after its own press, so a stale flag can no longer swallow a click. The parametrised test fails on the old code in both cases.

### 1. [warning] The same lost-release bug remains in the grid tile's `_swallow_release`
**Location**: `src/manic/ui/graphs.py:150-170` (`ClickableChartView.mouseDoubleClickEvent` / `mouseReleaseEvent`), reached through `double_clicked -> inspect_plot -> _show_detailed_view -> DetailedPlotDialog.exec()` (`graphs.py:1387`, `graphs.py:1168`)
**Finding**: `ClickableChartView` uses the same pattern this diff just fixed in `BarRows`. A left double-click sets `_swallow_release = True` and synchronously opens a modal `DetailedPlotDialog` via `exec()`. The release that ends the double-click goes to the modal dialog, so the flag stays set. Only a later left release clears it, and `mousePressEvent` never clears it. The first single click on that tile after the user closes the detail dialog is swallowed: no `clicked` signal fires, so the tile is not selected or deselected. The bug comes from this branch: `main` has no `_swallow_release` and no double-click-to-inspect on tiles.
**Evidence**: `/home/willyg/code/uiux-scratch/interrogate3-opus/probe_tile.py` runs offscreen against 5d27d2bc. It uses the same method as the round 2 `probe_dbl.py`: the trailing release goes through the window handle while the modal dialog is up. Output:
```
modal up: QDialog
after dialog: _swallow_release = True
first click after dialog emitted clicked: []
second click emitted clicked: ['S1']
```
The round 2 finding named the root cause: a "swallow the double-click's release" flag that only the release can clear. The fix applied that lesson to one of the two places on this branch that use the pattern. A user who double-clicks a tile to inspect it, closes the dialog, then clicks the same tile to select it sees nothing happen. A second click works.
**Suggestion**: Make the same change in `ClickableChartView.mousePressEvent`: set `self._swallow_release = False` on every press, before the button checks. Add a matching case to the tile tests (left double-click with the trailing release dropped, then one click must emit `clicked`). Better still, have both classes share one small helper for this, so a third copy cannot bring the bug back.
