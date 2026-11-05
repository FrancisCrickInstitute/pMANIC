# MANIC UI/UX review, round 12 (re-rating at fd447a30), reviewer: opus

## Evidence

**Screenshots.** I viewed all 558 PNGs in the nine round-12 folders through contact sheets (`sheets/`: 3×3 at 1000 px a tile for the two 2560 folders, 3×3 at 900 px for the rest). I opened full size or cropped where a detail mattered: `2560L/05`, `2560L/24`, `2560L/22`, `2560L/27`, `2560D/24`, and the header, status bar and sidebar edge of `2560L/05` and `2560L/24` (`crops/`). I measured the sidebar divider column and the pixel spread of every first Documentation page. Short names:
- `2560L/`, `2560D/`: linux 2560×1410, light and dark (primary target).
- `WL/`, `WD/`: Windows CI, 1028×749. `ML/`, `MD/`: macOS CI, 1024×656.
- `1500L/`: 1500×940 light. `1024D/`: 1024×720 dark. `150D/`: 150% scaling, 1280×800 window, dark.

**My own drive** (`drive12.py` → `body12.py`, offscreen with `screen2560.json`; log in `extra/log.txt`, shots in `extra/`):
- **Labelled, 2560:** fresh load; read the sidebar, header, status bar, splitter and tile geometry. N ×3, A, B from the grid. Peak window: drafted Left offset 0.1, read the caption, pressed Return, deselected and reselected. tR window 0.3 → Apply window (EIC regeneration; it ran). Settings: Peak validation tooltip, edit, page switch with the "Also unsaved" link, Save; Deconvolution level 4 → 3, Save, read the status bar. Both Summary popups and the detailed view. Full export.
- **Resize:** 2560 → 1920 → 1700 → 1500 → 1280 → 1100 → 1024 → 2560 with the Summary open, logging splitter, columns, tile size, scroll and header row; then the Scale menu.
- **Every menu**, read live with shortcuts.
- **Unlabelled, 2560:** all 8 compounds with the qualifier note and Summary state; Glycine with the Summary closed and reopened; 1500 and 1024 with names and the Samples list; Identity popup, detailed view, export.
- **`probe2.py`:** launched at 1500×940, then 2560, back to 1500; 1024 with the Summary forced open (Ctrl+Alt+R), then 900.
- **Code:** the diff 86a53c3..fd447a30 (18 commits, 15 UI files), and the action labels on `origin/main` against fd447a30.

**Harness notes, not app bugs:** my first run crashed because `multiprocessing` spawn re-imported a script with no `__main__` guard. The second run, with the guard, completed with exit 0. After B on Bio_001 my `charts()` helper listed Bio_002 first, so the peak-window step acted on Bio_002. The screenshot (`extra/02_lab_keys.png`) shows Bio_001 still in place with its Marked bad wash.

**Not run:** real hover and tooltips, the native macOS menu bar, Windows at 125% and 150%, a real OS scheme switch, Delete and Recover, session import, the rebuild from Raw Values with real files.

## Verdict

The app works end to end on both datasets, and every round-11 issue I raised that is in scope is fixed. I verified these live or by measurement:
- **Sidebar divider:** x 295 now runs from y 24 to y 1380 in every 2560 shot (`2560L/02`, `/05`, `/24`, `/31`).
- **Status bar:** empty at the defaults. After I set Pyruvate to level 3 it read "Deconvolution level 3 · automatic peak shape · balanced noise gate" (`crops/decon_status.png`).
- **Peak validation tooltip:** "…gets a Below threshold badge." It no longer names a colour.
- **Laptop widths:** at 1100 and 1024 the Summary closes on its own, the grid keeps 3 and 2 columns of large tiles, and the header stays one row. Widened back to 2560, the Summary returns. `view/summary_open` stayed unset throughout, so nothing was saved.
- **Forced-open Summary at 1024:** the two toggles fold into one "Scale ▾" button (`probe2/01_p1__1024sum.png`). The menu mirrors and drives Shared Y and the View action.
- **Names:** middle ellipsis in the tiles, the Summary and the lists. The sample list has no horizontal scroll bar.

Also working:
- Regeneration, which showed "Regenerated 30 EICs".
- Labelled export in 46 s behind a "Data Export" progress dialog (five sheets), and unlabelled export in 6 s (three sheets).
- The draft captions and the Settings unsaved link.
- "No flagged plots in Pyruvate" after N.

At 2560 the app is calm and well balanced:
- Labelled: 30 tiles at 303×251 in six columns with no scroll (`2560L/05`).
- Unlabelled: 11 tiles at 458×424 in four columns, with the Summary kept together at the top (`2560L/24`).

What remains is small:
- The first docs page is still blank on CI macOS in dark (a known limit).
- The quit prompt names a menu item that does not exist.
- The Summary keeps its launch width when the window shrinks.
- A few small inconsistencies in chart markers and review feedback.

Nothing that exists on `main` is missing.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 9 | One token system in all nine folders. The full-height divider closes the last structural seam (`2560L/24`, measured x 295, y 24–1380). The status bar is clean at the defaults (`crops/05_labelled_grid_bottom.png`), and the channel legend is now plain swatches (`crops/05_labelled_grid_topleft.png`). Below 10: the Summary's row labels and axis ticks are about 11 px on a 27" screen, small next to 13–14 px tile titles (`2560L/05`, `2560L/24`). In the label-incorporation Summary, missing rows show "—" while the peak-area Summary shows nothing for the same samples (`extra/02_lab_keys.png`). |
| F2 | Layout and hierarchy | 10 | At 2560 the grid fills its space with no scroll in both modes. The sidebar hugs its content and the Summary sits at the top. The Summary yields below room for three columns, and the header never wraps (log: 1100 → `[296, 800, 0]`, 3×174 tiles; `probe2/01_p1__1024sum.png`). Nothing left that I would move. |
| F3 | Onboarding and workflow clarity | 10 | Empty states have one action each (`*/02`, `*/03`). The checklist offers the chooser and "How do I change a pattern?" (`*/04`, `*/15`). Quick Start now gives seven short steps plus a key table (`1500L/17_…DocumentationViewer.png`). Unassessed qualifiers explain themselves with a docs link (`*/26`). The out-of-window flag is now a settled decision and no longer scored. |
| F4 | Consistency and polish | 9 | One ellipsis style, sentence-case titles, and platform button order (`WL/20` Rebuild/Cancel, `ML/20` Cancel/Rebuild). Below 10: the quit prompt says "Use File > Export Method..." but the menu item is "Export Session..." (`main_window.py:1139`, menu at `:333`). The peak-area Summary has no marker for zero or <0.01 samples (Bio_004, 014, 018–020, 027 in `extra/02_lab_keys.png`), while the label chart beside it shows "—" and its popup shows "<0.01" and "0" (`*/13`). |
| F5 | Feedback and state | 9 | Verified: the N toast, A/B washes and badges, menus that name their target ("Clear Bad Mark (Bio_001)", "Mark Bio_002 as Bad"), draft captions ("Bio_002 · not applied", "All 30 shown · not applied"), the "0.08 - 0.1" range when nothing is selected, the regeneration and export toasts, the export progress dialog, and the departure-only deconvolution indicator. Below 10: the first docs page is blank on CI macOS dark (`MD/17`, stddev 1.8 against 42–52 elsewhere). A on a plot that is not Below threshold does nothing and says nothing, while N says "No flagged plots" (`main_window.py:675-679`). Settings › Save gives no confirmation beyond the dot clearing. |
| F6 | Efficiency and flexibility | 9 | Remembered panel toggles with shortcuts. The Summary yields on small windows without overwriting the user's choice. The Scale menu keeps both scale modes one click away at narrow widths. Ctrl+F, Ctrl+[ ], N/A/B, Ctrl+E and F1 all work. Below 10: the Summary keeps its launch width. Opened at 2560 (384 px) then resized to 1500, the grid gets 812 px: 3 columns of 256×177 tiles and 2.1 screens of scroll. Launched at 1500 (Summary 300 px), the same window fits all 30 tiles in 5 columns with no scroll (log `[resize (1500, 940)]` against `probe2 [fresh 1500]`). |
| F7 | Data visualisation | 9 | Verdict washes match the workbook in both schemes (`2560L/27`, `2560D/27`). Not-detected traces are grey. The Identity heatmap has counts. The popups have precise axes, and the detailed view has a TIC and a spectrum (`*/11`, `*/34`). Below 10: the missing-value marker gap above. In unlabelled mode the legend draws the qualifier swatches grey while their traces are green or red. With the Summary open the only colour key is the Identity footer ("Qualifier cells ■ Validated…"), which describes cells, not lines (`2560L/24`). |
| F8 | Modern feel | 9 | Self-sizing grid, panels that yield and return, a live theme, the folding Scale menu, one-key review, docs with Find. It reads as considered software on the 27" screen. The blank first docs page on CI macOS dark is the one visibly unfinished surface. |
| F9 | Taste (not AI slop) | 9 | The round-11 tells are gone: the permanent deconvolution sentence and "amber". Copy is short and specific ("Weak peaks get a Below threshold badge only when an internal standard is set.", "Applies to plots. Export asks again."). Below 10: the quit prompt is wrong and wordy (see F4). The segmented "Shared Y / Scale to peak" pill is the one generic-looking control left in the header. |

Overall: (9+10+10+9+9+9+9+9+9)/9 = **9.2** (round 11: 9.0).

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| Sidebar and Summary toggles in the header, the View menu and Ctrl+Alt+S/R | `*/05` | Yes: a menu command with its shortcut, plus a button beside the panel. |
| Shared Y and Scale to peak in the header (or the Scale menu) and the View menu | `*/05`, `probe2/01_p1__1024sum.png` | Yes: the user asked for them visible; the menu holds the shortcuts. |
| The Qualifier QC key in the header and the Identity footer | `*/24` (Summary open: key hidden) | Yes: only one shows at a time. |
| The qualifier gap note in the grid header and the Summary | `extra/12_unl_glycine__closed.png` | Yes: verified only one home at a time (`qc_note vis False` with the Summary open, `True` with it closed). |
| The internal standard in the sidebar, the checklist and Settings | `*/04_*`, `16_settings_page4` | Yes: each is a place to act. |
| The deconvolution indicator in the status bar and Settings | `crops/decon_status.png` | Yes now: it shows only when a compound departs from the default, and it is clickable. |
| A quit prompt that points to "File > Export Method..." | `main_window.py:1139` | No: a wrong menu name. Say "File > Export Session…", or shorten to "This session is not saved." with an Export Session… button. |

## Top issues, ranked by user impact

These are the eight that survived verification. The other surfaces are clean.

1. **The quit prompt names a menu item that does not exist.**
   - Where: `main_window.py:1139`, "This session is not saved. Use File > Export Method... to keep the compound settings before quitting." The menu item is "Export Session..." (`main_window.py:333`; `docs/01_user_guide.md:330`). The same string is on `main`.
   - Fix: "This session is not saved. File › Export Session… keeps it." Better: add an "Export Session…" button to that prompt beside Quit and Cancel.
   - Gain: F4 +0.1, F9 +0.1, F3 +0.05.

2. **The Summary keeps its launch width when the window shrinks, so the grid gives up columns.**
   - Where: log `[resize (1500, 940)] splitter [296, 812, 384]`, 3 columns of 256×177, scroll 1025. Against `probe2 [fresh 1500] splitter [296, 896, 300]`, 5 columns of 170×130, no scroll. `summary_width_for(self.width())` applies only when no width is saved (`main_window.py:813-817`).
   - Fix: when the window narrows, cap the Summary at `summary_width_for(new width)` unless the user dragged the handle. The user's drag is the only width worth saving.
   - Gain: F6 +0.15, F2 +0.05.

3. **The first Documentation page is blank on CI macOS in dark mode.**
   - Where: `MD/17_documentation__DocumentationViewer.png` (stddev 1.8). Light and every other folder render (42–52). This is a known limit.
   - Fix: keep the "Loading…" page until `loadFinished` plus one `requestAnimationFrame` round trip through `runJavaScript`, then switch.
   - Gain: F5 +0.1, F8 +0.1.

4. **The peak-area Summary shows nothing for zero or <0.01 samples.**
   - Where: Bio_004, 014, 018–020 and 027 in `extra/02_lab_keys.png` and `2560L/05`. The label-incorporation chart beside it marks missing rows "—", and the popup prints "<0.01" and "0" (`*/13`). Sample_05 and Sample_07 in `2560L/24` are the same.
   - Fix: draw the same "—" (or "<0.01") at the axis for an empty bar, as the label chart does.
   - Gain: F7 +0.1, F4 +0.05.

5. **A (and B on a disallowed plot) is silent when it cannot act.**
   - Where: `main_window.py:675-679` triggers the action only if enabled. In the drive, A on Bio_001 (not Below threshold) changed nothing and showed no toast, while N showed "No flagged plots in Pyruvate".
   - Fix: when the action is disabled, show its reason as a status toast, e.g. "Bio_001 has no Below threshold badge to accept".
   - Gain: F5 +0.1.

6. **In unlabelled mode, line colours have no key while the Summary is open.**
   - Where: `2560L/24`. The legend draws Qualifier ion 1 and 2 as grey swatches, while their traces are green (Validated) or red (QC fail). The header QC key hides while the Summary is open, and the Summary footer ("Qualifier cells ■ ✓ Validated 16…") describes heatmap cells.
   - Fix: word the Summary footer as the key for both, e.g. "Qualifier lines and cells: ■ Validated ■ Failed ■ Not assessed". Or draw the legend's qualifier swatches neutral with a dash pattern only, and keep the QC key in the header in both states.
   - Gain: F7 +0.1.

7. **The Summary's text is small on the 27" screen.**
   - Where: `2560L/05` and `2560L/24`. Row labels and ticks are about 11 px, while tile titles are 13–14 px and the Summary column has room (`2560L/24`: the column's lower half is empty).
   - Fix: at 2560 use the tile-title size for Summary row labels. The roomy rows already allow it.
   - Gain: F1 +0.1, F7 +0.05.

8. **Settings › Save gives no confirmation beyond the dot clearing.**
   - Where: drive log "saved: save enabled False pending" with no status message.
   - Fix: a status toast naming what changed, e.g. "Saved Peak validation". Or a brief "Saved" in place of the disabled Save.
   - Gain: F5 +0.05.

## Re-rating comparison

**My round-11 issues, status:**
1. **Out-of-window labelled peaks unflagged:** now a settled decision. Not scored or raised.
2. **The sidebar divider started mid-height: fixed.** x 295 runs y 24–1380 in every 2560 shot.
3. **Blank first docs page on CI macOS dark: still open** (known limit; `MD/17`).
4. **The 1024 grid was cramped and the header wrapped: fixed.**
   - The Summary yields below room for three columns (1024: `[296, 724, 0]`, 2 columns of 345×237; 1100: 3 columns).
   - Forced open, the header stays one row with the Scale menu.
5. **The "amber" tooltip: fixed.** No "amber" remains in `src/manic/ui`.
6. **The permanent deconvolution sentence: fixed.** It shows only away from the defaults, and is verified to appear after a change.
7. **Two ellipsis styles: fixed.** Middle ellipsis everywhere: `HeaderName` in `chart_header.py`, and the tile headers in `1024D/35` show whole names at that width.
8. **Seven Settings pages:** now a settled decision. Not raised.

**Improved beyond the list:**
- the channel legend as plain swatches;
- the Summary kept together at the top for short cohorts;
- roomier Summary rows;
- a qualifier note with one home;
- Quick Start cut to short steps plus a key table;
- the time-tick freeze fixed (no hang in any drive, including seven resizes).

**Regressed:** nothing I could find.

**Lost functionality: none against `main`.**
- Every action label on `origin/main` exists at fd447a30. The only differences are case changes ("Accept peak (below threshold)" → "Accept Peak (Below Threshold)", "Mark peak as bad" → "Mark Peak as Bad", "Use compound setting" → "Use Compound Setting") and the renames already noted in round 11 ("View Detailed..." → "Inspect Sample...", "Select All" → "Select All Plots").
- The diff 86a53c3..fd447a30 removes no action, shortcut, button or combo. The removed `_controls_row` is replaced by the Scale menu, which keeps both scale modes.
- The menus read live:
  - File: Load (Ctrl+O), Add Compound, Load Raw Data (Ctrl+Shift+O), Open Recent, Export Session, Import Session (Ctrl+I), New Analysis Session, Clear Session, Export Data (Ctrl+E), Process External Data, Settings, Quit;
  - View: Show Sidebar (Ctrl+Alt+S), Show Summary (Ctrl+Alt+R), Shared Y-Scale (Ctrl+Shift+Y), Scale to Selected Peak (Ctrl+Shift+P), Find Compound (Ctrl+F), Previous and Next Compound (Ctrl+[ ]), Sample List (Ctrl+Shift+L);
  - Review: Inspect (Return), Select All Plots (Ctrl+A), Deselect All (Esc), Show Only Selected, Show All, Next and Previous Flagged (N, Shift+N), Accept (A), Mark Bad or Clear Bad Mark (B), Curve Fit, Baseline Correction (Ctrl+Shift+B);
  - Help: Documentation (F1), Check Data Setup, Check for Updates, About.

**What still stands between each factor and a 10:**
- **F1:** the small Summary text (issue 7), and the missing-value marker (issue 4).
- **F2:** nothing.
- **F3:** nothing.
- **F4:** the quit-prompt menu name (issue 1), and the missing-value marker (issue 4).
- **F5:** the macOS dark docs blank (issue 3), silent A/B (issue 5), and no Save confirmation (issue 8).
- **F6:** the Summary keeping its launch width (issue 2).
- **F7:** the missing-value marker (issue 4), and the line-colour key (issue 6).
- **F8:** the macOS dark docs blank (issue 3).
- **F9:** the quit prompt (issue 1), and the generic segmented pill in the header.

**Per-platform limits:**
- **2560:**
  - offscreen renders plus my own offscreen drive at the same geometry;
  - not checked: the native title bar, the macOS menu bar, hover.
- **Windows:**
  - CI at 100% only, clean in both schemes (`WL/*`, `WD/*`; the Summary yields at 1028 wide);
  - not checked: 125% and 150%, hover.
- **macOS:**
  - CI only, clean except `MD/17`;
  - not checked: the native menu bar and an OS scheme switch.
- **150%:** the 1280×800 window renders cleanly in dark (`150D/*`). Light at 150% was not captured this round.

```json
{"F1": 9, "F2": 10, "F3": 10, "F4": 9, "F5": 9, "F6": 9, "F7": 9, "F8": 9, "F9": 9, "overall": 9.2}
```
