# MANIC UI/UX review, round 19 (re-rating at f2c42d2c), reviewer: opus

## Evidence

**Screenshots.** I built 4×4 contact sheets (640 px tiles, `sheets/`) of all nine round-19 folders and pixel-diffed every shot against round 18 (`imgdiff.py`).
- The five Linux folders (2560 light and dark, 1500, 1024, 150%) are pixel-identical to round 18 (0 of 62 changed in each).
- macOS: 8 of 62 shots differ per scheme, all unlabelled and inside the grid area. CI regenerates the synthetic data, as in rounds 17 and 18.
- Windows: the same unlabelled shots differ, plus three small regions I cropped and compared at 2×. `WD/05` and `WL/05` caught the "Imported 2850 EICs" toast (timing). `WD/14` and `WD/22` differ by a pixel or two at a scrollbar edge.
- I viewed every sheet for 2560 light and dark, both Windows schemes and both macOS schemes. For 1500, 1024 and 150% I viewed sheets 00, 01 and 03. I skipped their sheet 02 (documentation pages only), which is pixel-identical to round 18.

Short names: `2560L/`, `2560D/` (Linux 2560×1410, the primary target); `WL/`, `WD/` (Windows CI); `ML/`, `MD/` (macOS CI); `1500L/`, `1024D/`, `150D/`.

**Code.** `git diff 7434f240..f2c42d2c -- src` changes five UI files and adds 10 lines:
- `chart_popup_dialog.py:291-293`: each popup sets `WA_DeleteOnClose`. No caller reads the dialog after `exec()` returns (`total_abundance_widget.py:289-300`, `isotopologue_ratio_widget.py:410-419`, `targeted_qc_widget.py:255`).
- `chart_style.py:222-223`: `BarRows` is now a child of the viewport, not of the view.
- The three Summary widgets now keep their `BarRows` and call `self._rows.refresh()` after every data update and clear (`total_abundance_widget.py:181, 265`; `isotopologue_ratio_widget.py:249, 365`; `targeted_qc_widget.py:167, 193`).
- `_rows` is assigned before the first `refresh()` call in all three.

**Tests.** `test_chart_popups`, `test_identity_chart`, `test_chart_summaries`, `test_main_window_shell` and `test_plot_grid_ui`: 149 passed and 8 skipped in 115 s. `git status` is clean.

**My own drive.** I ran `drive18.py` → `body18.py` offscreen with `screen2560.json` (`extra/log.txt`). It reached DONE with no traceback. With timings stripped, its 159 lines are identical to round 18's except the scratch path in one line. That covers:
- Both fresh loads and their status.
- The refusals, a Peak window draft and apply, and a tR window apply ("Regenerated 30 EICs").
- All Settings pages, both popups and the detailed view.
- Both exports ("Exported export.xlsx").
- Resizing 2560 → 1024 → 2560, the Scale menu, and every menu read live.
- The unlabelled compounds, a fit override, and Open Recent.

**Round-19 probes** (`probe19.py`, `probe19b.py`, `probe19d.py`, and my round-18 `probe18c.py` rerun; logs under `p19_*`, `p19b`, `p19d`, `probe18c`). All of them move a real pointer with `QTest.mouseMove`.

**Not run:**
- Real OS hover and Enter/Leave timing.
- The native macOS menu bar.
- Windows at 125% and 150%.
- A real OS scheme switch.
- Closing a popup while its tip is showing, inside a real `exec()` loop. Offscreen, no tip appeared in the nested loop with any of three approaches (details under the stale-tip and crash re-checks).

## Verdict

Both round-18 regressions are fixed.
- **Popup crash.** 120 popups per scheme opened and closed through the real, unpatched `exec()` loop, with `gc.collect()` after each close. They were opened by the enlarge button and by double-click, and closed by Esc, the Close button, a row click and `close()`. That gave no crash, no exception and no leftover dialog, and a row click still selects its plot.
- **Stale tip in labelled mode.** It is gone. With the pointer resting on a Peak area or Label incorporation bar, ↓ in the compound list now shows the new compound's value at once and keeps it. I checked 24 transitions on top, middle and bottom rows, including Valine 218 → Urea "Peak area 136". A keyboard Peak window Apply and a tR-window regeneration also update a resting tip.

One narrower case remains, in unlabelled mode. A compound change can change the Identity panel's height. Glycine has no expected ratios, so its panel collapses to a note; Serine's makes the panel taller. The Peak area chart then moves under a resting pointer, but its tip still describes the bar that used to be there. The value is correct for the sample it names, but that bar is no longer under the pointer. The tip can sit up to 344 px from the pointer, and it stays there until the pointer moves. On the Identity chart, the same kind of change can hide the tip instead of updating it.

This is much smaller than round 18's wrong value. It is still the one thing between F5 and a 10. The screens, the drive, the menus and every path on `main` are unchanged.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 10 | Pixel-identical to rounds 17 and 18 at 2560: one type scale, quiet hairlines, colour only for traces and verdicts (`2560L/24_unlabelled_grid.png`, `2560D/05_labelled_grid.png`). The Windows and macOS CI shots render the same tokens in both schemes (`WD/33`, `MD/27`, `ML/34`). |
| F2 | Layout and hierarchy | 10 | 30 labelled and 11 unlabelled tiles with no scroll at 2560 (`2560L/05`, `2560L/24`). The resize series in the drive log is unchanged: the Summary yields at 1100 and returns at 2560. |
| F3 | Onboarding and workflow clarity | 10 | One action per empty state (`*/02`, `*/03`, `*/36`). The checklist has a pattern how-to (`*/04_*_steps`). Quick Start has a key table (`*/17_…DocumentationViewer.png`). Refusals explain themselves (drive log). |
| F4 | Consistency and polish | 10 | All three popups now share one lifetime: they are deleted on close (`chart_popup_dialog.py:291-293`), and one tip owner serves the Summary and the popups (`chart_style.py:207-266`). The CI dialogs follow each platform's button order (`ML/18`, `WL/18`). |
| F5 | Feedback and state | 9.5 | Labelled resting tips now follow new data after ↓, Apply and regeneration (`p19_stale`, `p19_stale2`). But in unlabelled mode a resting Peak area tip keeps describing a bar that has moved away when the Identity panel changes height, and an Identity tip can hide instead of updating (`chart_style.py:229-249`; `p19b`: 16 of 28 transitions). |
| F6 | Efficiency and flexibility | 10 | Every shortcut and menu is intact (menus read live). In the popups, ↑↓, Return and click still choose a row (`probe18c`: "click row 27 … selected Bio_003"). |
| F7 | Data visualisation | 10 | Cell tips give the qualifier, the state, then "expected … ±25% observed …". Name tips summarise each qualifier's state (`probe18c`). The qualifier key lists only the states present (`*/24`), and the detailed view tags qualifier states in its legend (`*/34`). |
| F8 | Modern feel | 10 | Current, considered software on the 27" screen and both CI platforms. Panels yield and return, the theme switches live (`*/08_*`), and opening and closing popups is now as robust as the rest of the app. |
| F9 | Taste (not AI slop) | 10 | The copy is unchanged and short: "Re-extracts all 11 shown samples", "Qualifier cells ✓ 16 ✕ 2 ? 4", "Hover a cell for details · ↑↓ to choose · Return or click to select its plot" (`*/33`). I found no template layouts, decorative chips or ornamental icons. |

Overall: (10×8 + 9.5)/9 = 9.94 → **9.9** (round 18: 9.9).

### F9 tells and duplications, named

These are unchanged from round 18. Judged strictly, I found none that lacks a reason.

| Tell | Where | Justified? |
|---|---|---|
| Sidebar and Summary toggles in the header, the View menu, and Ctrl+Alt+S/R | `*/05` | Yes: a menu command, a shortcut, and a button beside its panel. |
| Shared Y / Scale to peak in the header (or the folded Scale button) and the View menu | `*/05` | Yes: a menu command plus a control at the grid. |
| The qualifier QC key in the grid header, with a tally in the Identity footer | `2560L/24`, `*/33` | Yes: the key names the colours, and the footer only counts marks. |
| The Identity popup key, with swatches and labels | `*/33_identity_popup` | Yes: the popup is a separate window, away from the grid header's key. |
| The popup footer hint | `*/13`, `*/14`, `*/33` | Yes: it is the only place these popup keys are taught. |
| The internal standard in the sidebar, the checklist and Settings | `*/04_*`, `*/16_settings_page4` | Yes: each is a place to act on it. |
| The deconvolution indicator in the status bar and in Settings | drive log | Yes: it appears only when the settings differ from the defaults. |
| The qualifier gap note in the grid header or in the Identity panel | `*/26` | Yes: it has one home at a time. |

## Top issues, ranked by user impact

Only issue 1 affects a score. I found nothing else above the cut, so the list is short rather than padded to 12.

**1. After a compound change shifts the Summary layout, a resting tip describes what used to be under the pointer (unlabelled; F5 −0.5).**

*What is wrong.* `probe19b` rests the pointer at a fixed screen point on the unlabelled Summary, presses ↓ through all 8 compounds at four points, and compares the tip with the chart actually under the pointer. 16 of 28 transitions disagree. Representative rows from `p19b/log.txt` (y and height of the Identity and Peak area viewports in brackets):

| Transition | Tip after ↓ | Under the pointer now | Layout |
|---|---|---|---|
| Lactate → Glycine | Sample_02 / Peak area 4.77e+03 | nothing: the Identity note | Peak area moves up, y 472 → 157 |
| Glycine → Serine | Sample_02 / Peak area 4.2e+03 | Sample_01's bar | Peak area moves down, y 157 → 501 |
| Glycine → Serine, another point | Sample_04_ratio_fail / Peak area 6.64e+03 | Sample_03's bar | same |
| Alanine → Lactate, Identity name column | (hidden) | MM_02 / Qualifier 1 Validated | none |

- The Peak area tip names the right sample and shows that sample's new value. It is drawn beside that bar's new position, up to 344 px from the pointer, and held there until the pointer moves (`_TIP_HOLD_MS`, `chart_style.py:204`).
- On the Identity chart, a change in the qualifier count can hide the tip rather than update it. Each transition with no layout change updates correctly (12 rows OK).

*Cause.* `BarRows.refresh()` with no argument reuses the viewport-local `_pointer` it stored at the last mouse event (`chart_style.py:229-249`). Qt sends no Enter, Leave or move event when a widget moves under a still pointer, so after the shift that local point no longer matches the pointer. The Identity hide is likely `refresh()` running before the chart lays out its new columns, so `bar_row_at` finds no row. That is a reading of the code, not traced.

*Offscreen-only follow-on, not scored.* `probe19d` shows the stale `_pointer` can also outlive a window resize. Clicking an Identity cell then pops a Peak area tip ("MM_01 / Peak area 8.1e+03"). After a Glycine collapse, a compound change with the pointer on the grid pops one too. Both depend on Qt missing a Leave event, which offscreen (no real cursor tracking) may cause and a real OS may not.

*Fix.* In `refresh()`, when called without a pointer, re-read the pointer instead of trusting the stored one:
`local = vp.mapFromGlobal(QCursor.pos()); self._pointer = local if vp.visibleRegion().contains(local) else None`
This shows the tip for what is under the pointer now, or hides it, and it also covers resizes. For the Identity hide, run the data-update `refresh()` after the chart lays out, for example `QTimer.singleShot(0, self._rows.refresh)`. Add a row to the transition matrix: rest on a Peak area bar, switch to a compound whose Identity panel has a different height, then assert the tip equals the chart under the pointer or is hidden.

*Expected gain.* F5 +0.5.

Below the cut, none affecting a score:

2. **Moving from a popup cell onto a row name keeps the cell's tip for up to 300 ms** (`probe18c`: shown at 150 ms, gone at 400 ms). This is Qt's hide delay, and the end state is right.
3. **The sidebar standard keeps only "Lactate_…026_long" of a 56-character name.** Unchanged; the full name shows on hover.
4. **The internal-standard row's tooltip is long.** Unchanged. It explains a consequence and its fix, which is what a tooltip is for.

## Re-rating comparison

**My round-18 issues, status:**
1. **Stale Summary tip after a keyboard compound change: fixed in labelled mode, partly fixed in unlabelled mode.**
   - `probe18c` lines 27, 29, 67 and 69 now show the new compound's value where round 18 showed the old one or hid it.
   - `p19_stale`: 24 of 24 ↓ transitions on both labelled bar charts are correct and held at 7.6 s, including the round-18 Valine 218 → Urea case ("Bio_001 / Peak area 136").
   - `p19_stale2`: a Peak window Apply ("Std_MM_02 / Peak area 989") and a tR-window regeneration ("Regenerated 30 EICs") also update a resting tip.
   - What remains is issue 1: an unlabelled compound change that shifts the layout.
2. The 300 ms hide delay: unchanged, by design.
3. Sidebar standard truncation: unchanged.
4. Long internal-standard tooltip: unchanged.

**The popup crash regression: fixed.**
- `p19_crash_light` and `p19_crash_dark` each opened and closed 120 popups through the real `exec()` loop: Peak area and Label incorporation in labelled mode, Identity and Peak area in unlabelled mode. The opens used the enlarge button and double-click. The closes used Esc, Close, a row click and `close()`. Each run collected garbage after every close and exited 0, with no exception and no dialog left over.
- Row clicks selected "Bio_015" and "Sample_04_ratio_fail".
- The repo's 30-per-scheme child-process test passes.
- Not exercised: closing while a tip is showing inside the nested loop, because no tip appeared offscreen there. In `probe18c`, popup hover and close via a patched `show()` behave exactly as in round 18.

**Improved:**
- Labelled resting tips follow new data.
- Popups no longer depend on the garbage collector.

**Regressed:** nothing. The screens are pixel-identical on Linux, the drive log is identical, and the hover-transition log matches round 18 line for line, except where the fix should change it.

One probe note: in my first stale-tip run, a programmatic `click()` on "Apply window" went through the window-modal progress dialog (`main_window.py:1058`) and started a second regeneration. A user cannot do this, because the dialog blocks the window. I reran that step with Return only, and it completed in under a second.

**Lost functionality: none against `origin/main` (5b17daca).** The UI diff against main is 8956 insertions and 3974 deletions. That is round 18's diff plus this round's 10 added lines; it adds no action and removes none. The menus read live match round 18:
- File: 12 actions.
- View: 8 actions.
- Review: 11 actions, including Curve Fit with five choices.
- Help: 4 actions.

Both exports completed. Popup click and Return still select a plot.

**What stands between each factor and a 10:**
- F5: issue 1.
- The other eight factors: nothing I could find.

**Per-platform limits:**
- **2560:** offscreen renders plus my drive and probes at that geometry. Not checked: the native title bar and the macOS menu bar.
- **Windows:** the CI shots are clean in both schemes. Issue 1 needs no OS event, so it should apply as measured. Not verified: whether a real Leave clears the resize case in `probe19d`, and 125% and 150% scaling.
- **macOS:** the CI shots are clean in both schemes, with the native button order (`ML/18`, `MD/16_*`). Not checked: the native menu bar, an OS scheme switch, and whether macOS hides a tip on a key press, which would mask issue 1 there.
- **150%:** dark only (`150D/*`), and clean.

```json
{"F1": 10, "F2": 10, "F3": 10, "F4": 10, "F5": 9.5, "F6": 10, "F7": 10, "F8": 10, "F9": 10, "overall": 9.9}
```
