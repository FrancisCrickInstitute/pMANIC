# MANIC UI/UX review, round 20 (re-rating at ece68c12), reviewer: opus

## Evidence

**Screenshots.** I pixel-diffed all nine round-20 folders against round 19 (`imgdiff.py`) and built 4×4 contact sheets with 640 px tiles (`sheets/`).
- The five Linux folders (2560 light and dark, 1500, 1024, 150%) are pixel-identical to round 19: 0 of 62 shots changed in each.
- macOS: 8 of 62 shots differ per scheme, all unlabelled and inside the grid area. CI regenerates the synthetic data, as in rounds 17 to 19.
- Windows: the same unlabelled shots differ, plus `05`, `14` and `22`. Their difference boxes are identical to round 19's: (444,723)-(583,746), the "Imported … EICs" toast timing; (769,118)-(785,555) and (1246,97)-(1259,104), a scrollbar edge.
- I viewed the sheets for 2560 light (00, 01, 03), 2560 dark (01, 03), Windows dark (01) and macOS light (03). I skipped the rest because they are pixel-identical to round 19, which I viewed in full then.

Short names: `2560L/`, `2560D/` (Linux 2560×1410, the primary target); `WL/`, `WD/` (Windows CI); `ML/`, `MD/` (macOS CI).

**Code.** `git diff f2c42d2c..ece68c12 -- src` changes one file, `chart_style.py` (+26 −13), inside `BarRows`:
- The stored viewport `_pointer` is gone.
- `refresh()` with no point now starts a 0 ms single-shot timer (`chart_style.py:227-228, 232-240`). When it fires, `_show_under(QCursor.pos())` acts only if `QApplication.widgetAt(cursor)` is this chart's viewport; otherwise it hides (`:242-246`).
- Qt's delayed `ToolTip` event uses its global position (`:268-271`).
- A viewport `Resize` calls `refresh()` (`:275-276`).
- `Leave` and `Hide` call `_show_at(None)` (`:273-274`).
- The keyboard path in the popups still passes an explicit point (`chart_popup_dialog.py:729`), so it is unchanged.

The commit also adds `test_a_resting_tip_follows_the_charts_a_compound_change_moves` (`tests/test_identity_chart.py:364-399`). It switches the transition test to the widget overload of `QTest.mouseMove`, which moves the cursor.

**Tests.** `test_chart_popups`, `test_identity_chart`, `test_chart_summaries`, `test_main_window_shell` and `test_plot_grid_ui`: 150 passed and 8 skipped in 118 s (round 19: 149 passed). `git status` in the checkout is clean.

**Probes.** All ran offscreen with `screen2560.json`. Per the round's PROBE NOTE, every hover move now moves the real cursor. I used the widget overload `QTest.mouseMove(<widget>, …)` and also called `QCursor.setPos(global)`. Each log records `QCursor.pos()` next to the target point, and the two match on every row.
- `probe19b.py` (round-19 issue 1 matrix): rest at four fixed screen points on the unlabelled Summary and press ↓ through all 8 compounds. The oracle is the chart whose visible viewport holds the cursor now, scored by its own tip function. Logs: `p20b_light`, `p20b_dark`.
- `probe19b.py … handle` is a control that moves only the window handle, as round 19 did.
- `probe19d.py` (round-19 resize and collapse follow-on), with Identity and grid clicks sent to the viewport. Log: `p20d`.
- `probe19.py stale` reruns the labelled stale-tip matrix plus an unlabelled Identity pass. Log: `p20_stale`.
- `probe18c.py` reruns the round-18 hover-transition and popup probe, with every window-handle move wrapped so that it also moves the cursor. Log: `probe18c`.
- `probe20e.py` and `probe20f.py` trace one hide found in `p20_stale` (below). `probe_click.py` checks how my probes deliver a click.

**Functional drive.** I ran `drive18.py` → `body18.py` (`extra/log.txt`). It reached DONE with 159 lines and no traceback. With timings and paths stripped, it differs from round 19 in only three lines. Two are export file sizes that are 1 byte smaller, a timestamp. The third is a toast caught by timing ("Imported 88 EICs"). That covers:
- Both fresh loads and every status they show.
- The refusals, a Peak window draft and apply, and a tR window apply.
- All Settings pages, both popups and the detailed view.
- Both exports.
- Resizing 2560 → 1024 → 2560, the Scale menu, and every menu read live.
- The unlabelled compounds, a fit override, and Open Recent.

**Not run:**
- Real OS hover and Enter/Leave timing.
- The native macOS menu bar.
- Windows at 125% and 150%.
- A real OS scheme switch.

## Verdict

Round 19's one scored issue is fixed. With the cursor really moved, a resting Summary tip now describes the chart under the pointer after a compound change moves the charts, or hides when nothing is there:
- 28 of 28 transitions correct in light and 28 of 28 in dark. Round 19 had 16 of 28 wrong.
- Includes Lactate → Glycine, where Identity collapses and Peak area jumps from y 472 to 157, and Glycine → Serine, where it drops to 501.

The round-19 offscreen follow-ons are gone too. A window resize under a resting pointer no longer leaves a Peak area tip to pop up when an Identity cell is clicked. A compound change with the pointer on the grid shows nothing.

The window-handle control fails 25 of 28, with `QCursor.pos()` stuck at (10, 10). That confirms the PROBE NOTE: the new code reads the real cursor, and only a probe that does not move it sees hidden tips.

Nothing else changed: the screens are pixel-identical on Linux, the drive is the same, and every path on `main` is present. I found one narrow hardening point, described below the cut. Offscreen I could reach it only with a cursor placed with no mouse event. It does not change a score.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 10 | Pixel-identical to rounds 17–19 at 2560: one type scale, quiet hairlines, colour only for traces and verdicts (`2560L/24_unlabelled_grid.png`, `2560D/12_another_compound.png`). Windows and macOS render the same tokens in both schemes (`WD/13`, `WD/14`, `ML/34`). |
| F2 | Layout and hierarchy | 10 | 30 labelled and 11 unlabelled tiles with no scroll at 2560 (`2560L/05`, `2560L/24`). The resize series in the drive log is unchanged: the Summary yields at 1100 and returns at 2560. |
| F3 | Onboarding and workflow clarity | 10 | One action per empty state (`*/02`, `*/03`, `*/36_all_samples_unchecked`). The checklist has a pattern how-to (`*/04_*_steps`, `*/23_*_step`). Quick Start has a key table (`*/17_…DocumentationViewer.png`). Refusals explain themselves (drive log). |
| F4 | Consistency and polish | 10 | One tip owner serves the Summary charts and the popups (`chart_style.py:207-283`). It now reads the pointer the same way for mouse, Qt tip events, resizes and data changes. The CI dialogs follow each platform's button order (`ML/28` Revert/Save, `WD/16_settings_page2` Save/Revert). |
| F5 | Feedback and state | 10 | A resting tip follows the charts a compound change moves (`p20b_light`, `p20b_dark`: 0 of 28 wrong each). Resizes and collapses leave no stale tip (`p20d`). Labelled ↓, Apply and tR regeneration still update a resting tip (`p20_stale`: 43 OK, plus 3 rows correct on inspection). |
| F6 | Efficiency and flexibility | 10 | Every shortcut and menu is intact (menus read live). In the popups, ↑↓, Return and click still choose a row (`probe18c`: "click row 27 … selected ['Bio_003']"). |
| F7 | Data visualisation | 10 | Cell tips give the qualifier, the state, then "expected 0.450 ±25% observed 0.815" (`p20d`). The qualifier key lists only the states present (`*/24`). The Identity popup tallies its marks (`*/33`). The detailed view tags qualifier states in its legend (`*/34`). |
| F8 | Modern feel | 10 | Current, considered software on the 27" screen and on both CI platforms. Panels yield and return, the theme switches live (`*/08_*`), and hover now holds up under layout changes the way a commercial app's does. |
| F9 | Taste (not AI slop) | 10 | The copy is unchanged and short: "Re-extracts all 11 shown samples", "Qualifier cells ✓ Validated 16 ✕ Failed 2 ? Not assessed 4", "Hover a cell for details · ↑↓ to choose · Return or click to select its plot" (`*/33`). I found no template layouts, decorative chips or ornamental icons. |

Overall: 90/9 = **10.0** (round 19: 9.9).

### F9 tells and duplications, named

These are unchanged from round 19. Judged strictly, I found none that lacks a reason.

| Tell | Where | Justified? |
|---|---|---|
| Sidebar and Summary toggles in the header, the View menu, and Ctrl+Alt+S/R | `*/05` | Yes: a menu command, a shortcut, and a button beside its panel. |
| Shared Y / Scale to peak in the header (or the folded Scale button) and the View menu | `*/05`, `WD/12` | Yes: a menu command plus a control at the grid. |
| The qualifier QC key in the grid header, with a tally in the Identity footer | `2560L/24`, `*/33` | Yes: the key names the colours, and the footer only counts marks. |
| The Identity popup key, with swatches and labels | `*/33_identity_popup` | Yes: the popup is a separate window, away from the grid header's key. |
| The popup footer hint | `*/13`, `*/14`, `*/33` | Yes: it is the only place these popup keys are taught. |
| The internal standard in the sidebar, the checklist and Settings | `*/04_*`, `*/16_settings_page4` | Yes: each is a place to act on it. |
| The deconvolution indicator in the status bar and in Settings | drive log | Yes: it appears only when the settings differ from the defaults. |
| The qualifier gap note in the grid header or in the Identity panel | `*/26` | Yes: it has one home at a time. |

## Top issues, ranked by user impact

None affects a score this round, so the list is short rather than padded to 12.

**1. A chart can hide another chart's fresh tip if it still thinks it owns the tooltip (hardening; no factor change).**

*What I saw.* In `p20_stale`'s unlabelled pass, with the cursor resting on an Identity cell, Alanine → Lactate showed the correct new tip at 100 ms ("Sample_09_overlap / Qualifier 1 Validated / expected 0.350 …"). It was hidden by 1.5 s.
- `probe20f` traced the hide to the Peak area chart in the same window. Its `_showing` still held "Sample_09_overlap / Peak area 8.31e+03".
- It had raised that tip from a resize refresh when the new window appeared under a cursor that had been placed with no mouse event. The probe then moved the cursor to Identity, and Qt never sent Peak area a Leave.
- On Peak area's next refresh, `_show_at(None)` called the global `QToolTip.hideText()` because its own `_showing` was set (`chart_style.py:252-254`).
- Run alone, the same transition holds the tip for 2.5 s in both delivery modes (`p20e_vp`, `p20e_win`).

*Reach on a real OS.* Narrow. Qt sends synthetic Enter/Leave when a chart is shown or hidden under the pointer. The first real mouse move after a layout shift sends Enter to the chart under the pointer, so a later Leave clears `_showing`. To leave `_showing` stale, the first move after the shift would have to land outside the chart that raised the tip. I could not produce that with a real pointer here.

*Fix.* Hide only a tip this chart owns, for example `if self._showing is not None and QToolTip.isVisible() and QToolTip.text().rstrip() == self._showing: QToolTip.hideText()`. Add a test: two charts, the second raises a tip by `refresh()` under a placed cursor, the cursor moves to the first, then data changes on both. The first's tip must stay.

*Expected gain.* None on the scores. It removes the last way one chart's bookkeeping can affect another's tip.

Below the cut, unchanged:

2. **Moving from a popup cell onto a row name keeps the cell's tip for up to 300 ms.** This is Qt's hide delay, and the end state is right.
3. **The sidebar standard keeps only "Lactate_…026_long" of a 56-character name.** The full name shows on hover.
4. **The internal-standard row's tooltip is long.** It explains a consequence and its fix, which is what a tooltip is for.

## Re-rating comparison

**My round-19 issues, status:**
1. **A resting tip describes what used to be under the pointer after the layout shifts: fixed.**
   - `p20b_light` and `p20b_dark` each show 0 of 28 transitions wrong (round 19: 16 of 28), for example:
     - Lactate → Glycine at (0.3, 0.15): "(hidden)". Under the pointer is the Identity note.
     - Lactate → Glycine at (0.8, 0.5): "Sample_05_rt_shift / Peak area 0". Peak area moved under the pointer.
     - Glycine → Serine at (0.5, 0.9): "Sample_01 / Peak area 6.55e+03". This is the bar now under the pointer, not Sample_02 drawn 344 px away.
   - The Identity case that hid instead of updating, Alanine → Lactate in the name column, now shows "MM_02 / Qualifier 1 Validated".
   - Round 19's offscreen follow-on is also gone (`p20d`). After a resize, clicking an Identity cell leaves no tip ("B clicked that cell … tip '(hidden)'"; round 19 showed "MM_01 / Peak area 8.1e+03"). After Glycine with the pointer on the grid, a compound change shows nothing (round 19 popped "MM_01 / Peak area 6.73e+03").
   - `probe18c` differs from round 19 in exactly these two lines, both now "(hidden)".
   - On my first `p20d` run a grid click selected nothing. `probe_click.py` showed this was my probe: a click sent to the chart view's frame does not reach the plot, while the viewport and the window handle both select "Sample_01". I reran with the viewport, and the click selects.
2. The 300 ms hide delay: unchanged, by design.
3. Sidebar standard truncation: unchanged.
4. Long internal-standard tooltip: unchanged.

**Improved:** resting tips are now exact under every layout change I could make: a compound change, a panel collapse or expand, and a window resize.

**Regressed:** nothing I could find.
- The screens are pixel-identical on Linux.
- The drive log matches round 19.
- The labelled stale-tip matrix is unchanged: 24 of 24 ↓ transitions plus Apply ("Std_MM_02") and tR regeneration. One caveat: three unlabelled rows in `p20_stale` are flagged by an oracle that checks only Identity. On inspection they are correct, because each is Lactate → Glycine, where Peak area moves under the pointer and its tip shows. The fourth flag is issue 1.

**Lost functionality: none against `origin/main` (5b17daca).** The UI diff against main is 8969 insertions and 3974 deletions. That is round 19's diff plus this round's 13 net lines in `chart_style.py`; it adds no action and removes none. The live menus match round 19:
- File: 12 actions.
- View: 8 actions.
- Review: 11 actions, including Curve Fit with five choices.
- Help: 4 actions.

Both exports completed. Popup click and Return still select a plot.

**What stands between each factor and a 10:** nothing I could find. Issue 1 is a hardening note; I could not reach it with a real pointer.

**Per-platform limits:**
- **2560:** offscreen renders plus my drive and probes at that geometry. Not checked: the native title bar and the macOS menu bar.
- **Windows:** the CI shots are clean in both schemes. `QApplication.widgetAt` on Windows respects other apps' windows, so a covered MANIC should not raise a tip. I did not verify this, nor 125% and 150% scaling.
- **macOS:** the CI shots are clean in both schemes, with the native button order (`ML/28`). Not checked: the native menu bar, a real OS scheme switch, and real Enter/Leave timing.
- **150%:** dark only (`linux-dark-150pct-1280x800/`), and pixel-identical to round 19.

```json
{"F1": 10, "F2": 10, "F3": 10, "F4": 10, "F5": 10, "F6": 10, "F7": 10, "F8": 10, "F9": 10, "overall": 10.0}
```
