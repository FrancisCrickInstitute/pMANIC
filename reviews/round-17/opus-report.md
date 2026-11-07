# MANIC UI/UX review, round 17 (re-rating at e33c52c9), reviewer: opus

## Evidence

**Screenshots.** I viewed all 558 PNGs in the nine round-17 folders as 4×4 contact sheets (`sheets/`, 640 px tiles). I also pixel-diffed every shot against round 16 (`imgdiff.py`):
- The four Linux folders at 2560, 1500 and 1024 are pixel-identical to round 16. One shot in the 150% folder (`24_unlabelled_grid`) differs only in a 205×31 strip at the toast.
- The CI folders differ in 8 or 9 unlabelled shots each, inside the grid area. A side-by-side of the Windows-light `24_unlabelled_grid` (`cmp_24_unlabelled_grid.png`) shows why: CI regenerates the synthetic data, so peak heights change (Sample_06_partial is ×10⁵ in round 16 and ×10⁴ in round 17). The chrome, layout and copy are the same. macOS-light `05_labelled_grid` differs only where the toast sits.

Short names below: `2560L/`, `2560D/` (Linux 2560×1410, light and dark, the primary target); `WL/`, `WD/` (Windows CI); `ML/`, `MD/` (macOS CI); `1500L/`; `1024D/`; `150D/` (150%, 1280×800 window, dark).

**Code.** `git diff 4f1b3999..e33c52c9 -- src` is one hunk of three lines in `chart_popup_dialog.py:769-771`. On a `QEvent.ToolTip` over a popup row, the viewport filter now returns True, so the graphics scene no longer answers the rest by hiding the tip. The other changes are tests only. I ran `test_identity_chart.py`, `test_plot_grid_ui.py` and `test_compound_list_context_menu.py` offscreen with the pytest cache off: 53 passed, and `git status` stays clean.

**My own drive.** I ran `drive17.py` → `body17.py` offscreen with `screen2560.json`; the log is in `extra/log.txt`. It reached DONE, and `run.out` has no traceback. With timings stripped, its log is identical line for line to round 16's. That covers:
- Labelled at 2560: the fresh load and its status; A, N and B refusals; a Peak window draft and apply; the tR window apply ("Regenerated 30 EICs", 2.0 s); a Peak validation save; all seven Settings pages; the deconvolution change and its indicator; both popups; the detailed view.
- Export: labelled 60.6 s, toast "Exported export.xlsx"; unlabelled 5.5 s.
- Resizing 2560 → 1024 → 2560, and the Scale menu and every menu bar menu read live.
- Unlabelled: all 8 compounds, Glycine with the Summary open and closed, narrow names, the Identity popup, the detailed view and a fit override.
- The round-14 probes, including Open Recent.

**Round-17 probe** (`probe17.py`, `probe17b.py`; logs in `probe17/`, `probe17b/`). The probe moves a real pointer (`QTest.mouseMove` on the dialog window), so Qt itself sends the rest event. It opens the Identity popup through the Summary's expand button, at 2560 and at 1500. For the rows Sample_04_ratio_fail, Sample_05_rt_shift, Sample_07_missing, MM_01 and Sample_09_overlap:
- Hover a qualifier-1 cell, then rest 1.5 s.
- Move to the qualifier-2 cell, then rest 1.5 s.
- Move onto the row name, reading at 150 ms and at 400 ms.
- Move in one step to the next row's cell, then rest.
- Leave into the footer. Rest on a cell, then press Esc.
- Press Down twice.

It also opens the Peak area popup and rests on every bar and every name.

**Not run:**
- Real OS hover timing.
- The native macOS menu bar.
- Windows at 125% and 150%.
- A real OS scheme switch.
- Delete and Recover, session import, and the quit prompt. Their code has not changed since round 13.

## Verdict

The round-16 finding is fixed, and I verified it in the running app.
- **The enlarged Identity popup keeps a cell's tip while the pointer rests.** After a 1.5 s rest the tip still reads, for example, "Sample_04_ratio_fail / Qualifier 1  Failed / expected 0.450  ±25%  observed 0.815". This holds at 2560 and 1500, on Failed, Not assessed and Validated cells, in both qualifier columns.
- **One move to another row's cell shows that cell's tip, and it stays after a rest.**
- **Leaving clears the tip.** Moving into the footer hides it within Qt's 300 ms hide delay (still shown at 200 ms, hidden at 800 ms). Esc closes the popup and the tip goes with it.
- **No scene item loses its tooltip.** The new filter branch fires only over a row, and the popup's only other tooltip belongs to the status-legend label, which sits outside the chart viewport.

The core workflow works end to end on both datasets, with results the same as round 16. Every Linux screen is pixel-identical to round 16. The CI screens differ only in regenerated synthetic data. Nothing on `main` is missing.

Judged strictly for clutter, I found no new duplication, and none without a reason (see the F9 table).

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 10 | Unchanged and pixel-identical at 2560: one type scale, quiet hairlines, and colour only for traces and verdicts (`2560L/24_unlabelled_grid.png`, `2560D/05_labelled_grid.png`). The Windows and macOS CI shots render the same tokens in both schemes (`WD/33`, `MD/27`). |
| F2 | Layout and hierarchy | 10 | At 2560: 30 tiles of 303×251 and 11 tiles of 458×424, with no scroll (log lines 5 and 76). Resizing to 1024 and back lays out like a fresh launch, and the Summary yields at 1100 (log 56-62). |
| F3 | Onboarding and workflow clarity | 10 | One action per empty state (`*/02`, `*/03`, `*/36`). The checklist has a pattern how-to (`*/04_*_steps`). Quick Start has a key table (`*/17_…DocumentationViewer.png`). Refusals explain themselves ("No flagged plots in Pyruvate", log 10). |
| F4 | Consistency and polish | 10 | The popup now treats a rest the way the Summary does: the tip stays while the pointer rests and goes on leave (`chart_popup_dialog.py:769-771`, probe17). That closes the last behaviour gap between the Summary and its enlarged view. |
| F5 | Feedback and state | 10 | Verified live: the refusal toasts, "Regenerated 30 EICs", "Saved" then cleared, "Exported export.xlsx" with a progress dialog, the draft caption, and the deconvolution indicator. Hover tips in the popup now survive a rest and clear on leave and on Esc. |
| F6 | Efficiency and flexibility | 10 | Every shortcut is intact (menus read live, log 69 ff.). In the popup, ↑↓, Return and clicking a row select its plot (`*/33` footer, `chart_popup_dialog.py:788-806`), and a tip no longer vanishes while you read it. |
| F7 | Data visualisation | 10 | The popup cell tip is complete and persistent: qualifier, state, then "expected … ±25% observed …" (probe17). The qualifier key lists only the states present (`*/24`), and the detailed view tags qualifier states in its legend (`*/34`). |
| F8 | Modern feel | 10 | It feels like current, considered software on the 27" screen and on both CI platforms. Panels yield and return, the theme switches live (`*/08_*`), review goes one key at a time, and tips behave as people expect in both the Summary and the popup. |
| F9 | Taste (not AI slop) | 10 | The copy is unchanged and short: "Re-extracts all 11 shown samples", "Qualifier cells ✓ 16 ✕ 2 ? 4", "Hover a cell for details · ↑↓ to choose · Return or click to select its plot" (`*/33`). I found no template layouts, decorative chips or ornamental icons. |

Overall: (10×9)/9 = **10.0** (round 16: 10.0).

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| Sidebar and Summary toggles in the header, the View menu, and Ctrl+Alt+S/R | `*/05` | Yes: a menu command, a shortcut, and a button beside its panel. |
| Shared Y / Scale to peak in the header (or the folded Scale button) and the View menu | `*/05` | Yes: a menu command plus a control at the grid. |
| The qualifier QC key in the grid header, with a tally in the Identity footer | `2560L/24`, `*/33` | Yes: the key names the colours, and the footer only counts marks. |
| The Identity popup key, with swatches and labels | `*/33_identity_popup` | Yes: the popup is a separate window, away from the grid header's key. |
| The popup footer hint, "Hover a cell for details · ↑↓ to choose · Return or click…" | `*/33`, `*/13`, `*/14` | Yes: it is the only place these popup keys are taught. |
| The internal standard in the sidebar, the checklist and Settings | `*/04_*`, `*/16_settings_page4` | Yes: each is a place to act on it. |
| The deconvolution indicator in the status bar and in Settings | log 43 | Yes: it appears only when the settings differ from the defaults. |
| The qualifier gap note in the grid header or in the Identity panel | log 79-80, 113 | Yes: it has one home at a time. |

## Top issues, ranked by user impact

No issue survived verification. Below the cut, none affecting a score:
1. **Moving from a popup cell onto a row name keeps the cell's tip for up to 300 ms.** It is still shown at 150 ms and gone at 400 ms (probe17b). Hover-leave calls `QToolTip.hideText()` (`chart_popup_dialog.py:604-611`), and Qt delays that hide by 300 ms, as it does for every Qt tooltip. In the popup a full name has no tip of its own (`row_tip`, `chart_popup_dialog.py:733-739`), so the end state is right. No fix needed.
2. **The sidebar standard keeps only "Lactate_…026_long" of a 56-character name.** This is unchanged from round 15. It follows from the sidebar's width, and the full name is on hover.
3. **The internal-standard row's tooltip is long.** This is unchanged. It explains a consequence and its fix, which a tooltip is for.

## Re-rating comparison

**My round-16 issues, status:** round 16 listed no issue above the cut. Its three items below the cut:
1. Leaving the chart hides the tip after Qt's 300 ms delay: unchanged, by design. The popup now behaves the same way (probe17, "leave to footer").
2. Sidebar standard truncation: unchanged.
3. Long internal-standard tooltip: unchanged.

**The round-16 finding this round targets (the popup tip vanished on rest): fixed.**
- After a 1.5 s rest the tip is still up, with the same text, on every row and in both columns, at 2560 and 1500 (probe17).
- It hides on leave and on close.
- The repo test `test_the_popup_cell_tip_stays_up_while_the_pointer_rests_on_the_cell` passes.

**Improved:** the popup's rest behaviour (above). The test fixes make the suite order-independent: the header-fold test applies the app's font itself, and the context-menu test releases the right button where it pressed it. Users see neither change, but they protect the layout and the context-menu checks.

**Regressed:** nothing I could find.
- The Linux screens are pixel-identical to round 16.
- The drive log is identical to round 16's.
- The Peak area popup shows no stray tip on any bar or name, at rest or on leave (probe17).
- Down-arrow in the Identity popup moves the row marker as before.

**Lost functionality: none against `origin/main`.** The UI diff against main grew by three lines (8924 → 8927 insertions). It adds no action and removes none. The menus read live match round 16:
- File: 12 actions.
- View: 8 actions.
- Review: 11 actions, including Curve Fit with five choices.
- Help: 4 actions.

Both exports completed (five labelled sheets, three unlabelled).

**What stands between each factor and a 10:** nothing I could find. All nine factors score 10.

**Per-platform limits:**
- **2560:** offscreen renders plus my drive and probes at that geometry. Not checked: the native title bar, the macOS menu bar, and real OS hover timing.
- **Windows:** the CI shots are clean in both schemes (`WL/*`, `WD/*`). Not verified on real Windows: 125% and 150% scaling.
- **macOS:** the CI shots are clean in both schemes. The dialogs use the native button order: Cancel before Add compound, and Revert before Save (`ML/18`, `MD/16_*`). Not checked: the native menu bar and an OS scheme switch.
- **150%:** dark only (`150D/*`), and clean. The dialogs scale without clipping (`150D/09`, `150D/20`, `150D/32`).

```json
{"F1": 10, "F2": 10, "F3": 10, "F4": 10, "F5": 10, "F6": 10, "F7": 10, "F8": 10, "F9": 10, "overall": 10.0}
```
