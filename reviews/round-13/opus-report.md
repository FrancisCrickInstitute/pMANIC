# MANIC UI/UX review, round 13 (re-rating at 72561139), reviewer: opus

## Evidence

**Screenshots.** I viewed all 558 PNGs in the nine round-13 folders through contact sheets (`sheets/`: 3×3 at 1000 px a tile for the two 2560 folders, 900 px for the rest). I opened these at full size: `2560L/05`, `2560L/24`, `2560L/26`, and `2560L/16_settings__SettingsWindow*`. I cropped the Peak area Summary before and after a selection in four folders, plus the round-12 150% shots (`crops/`). Short names:
- `2560L/`, `2560D/`: linux 2560×1410, light and dark (primary target).
- `WL/`, `WD/`: Windows CI, 1028×749. `ML/`, `MD/`: macOS CI, 1024×656.
- `1500L/`: 1500×940 light. `1024D/`: 1024×720 dark. `150D/`: 150% scaling, 1280×800 window, dark.

**My own drive** (`drive13.py` → `body13.py`, offscreen with `screen2560.json`; log in `extra/log.txt`, shots in `extra/`; exit 0):
- **Labelled, 2560:** fresh load. A on an unflagged plot, A with all 30 selected, A with nothing selected, N ×3, A, B. Peak window draft and Return. tR window 0.3 → Apply window. Peak validation edit → Save ("Saved" note), then all seven Settings pages measured. Deconvolution level 4 → 3. Both Summary popups, the detailed view, and a full export (59 s, five sheets).
- **Resize** with the Summary open: 2560 → 1920 → 1700 → 1500 → 1280 → 1100 → 1024 → 2560. Then the folded Scale button at 1100, and every menu read live.
- **Unlabelled, 2560:** all 8 compounds. Glycine with the Summary open, closed and reopened. 1500 and 1024. The Identity popup, the detailed view, and export (6 s, three sheets). A per-sample fit override, Documentation early and late.
- **`probe3.py`:** a Gaussian fit override on Sample_01, then its detailed view. The quit prompt with the tour's close guard removed (logged through the `_confirm` hook).
- **Code:** the diff fd447a30..72561139 (24 commits, 12 UI files), and the action labels and shortcuts on `origin/main` (5b17dac) against 72561139.

**Harness notes, not app bugs:**
- In `probe3`, A and B after closing the detailed view reached no window, because the harness did not reactivate the window. The same keys worked in the main drive after `activateWindow()`.
- In the main drive, my `charts()` helper reorders after B, so the fit override landed on Sample_01 instead of the plot I opened. `probe3` redid it on the right plot.

**Not run:** real hover and tooltips (including the new full-name hovers), the native macOS menu bar, Windows at 125% and 150%, a real OS scheme switch, Delete and Recover, session import.

## Verdict

The app works end to end on both datasets, and all eight of my round-12 issues are fixed:
- **Quit prompt:** it reads "This session is not saved. File > Export Session... keeps it." (`probe3/log.txt`).
- **Summary width on resize:** after a 2560 launch, a resize to 1500 gives `[296, 896, 300]`, 5 columns of 169×130 tiles and no scroll. That is the fresh-launch layout.
- **Documentation on macOS dark:** the first page now renders on CI (`MD/17_documentation__DocumentationViewer.png`).
- **Peak area markers:** short bars read "0" or "<0.01" (`2560L/05`).
- **A and B:** they now explain themselves ("Bio_001 is not Below threshold", "No selected plot is Below threshold").
- **QC key:** it stays beside the traces while the Summary is open (`2560L/24`).
- **Summary text:** names are 12 px or larger at 2560.
- **Settings:** Save shows a "Saved" note that clears after about 3 s. Short pages are 260 px tall instead of sitting over a void.

The folded Scale button now reads "Shared Y" and shows as checked when Shared Y is on. The detailed view names the override ("Alanine in Sample_01 · Gaussian").

At 2560, both modes are calm, dense and readable. What remains is small and mostly off the primary target:
- At 150% scaling, the Peak area Summary's names change size, lose their ellipsis and clip at the left edge once a sample is selected.
- The qualifier QC key lists Validated and Failed on compounds where nothing is assessed.
- A stale toast survives a successful B.

Nothing that exists on `main` is missing.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 9 | One token system in every folder. The Settings pages are now compact (`2560L/16_settings__SettingsWindow_page2.png`, 720×260), and the Summary type at 2560 matches the tiles (`2560L/05`, `2560L/24`). Below 10: at 150%, selecting a sample shrinks the Peak area names, drops their ellipsis and clips them ("ample_04_ratio_fail") at the card edge. Before the selection, the larger font over-elides them to "Sampl...ssing" (`150D/24` vs `150D/25`, `crops/150_peakarea_24v25.png`; `chart_style.py:136`, `total_abundance_widget.py:187-200`). |
| F2 | Layout and hierarchy | 10 | At 2560: 30 tiles of 303×251 in 6 columns and 11 tiles of 458×424 in 4 columns, with no scroll. A resize now lays out like a fresh launch (log: 1920 → `[296,1316,300]` 5 columns; 1500 → 5 columns, no scroll; 1100 → Summary yields, 3 columns). Nothing I would move. |
| F3 | Onboarding and workflow clarity | 10 | One action per empty state (`*/02`, `*/03`). The checklist has the pattern how-to (`*/04_*_steps`). Quick Start is short and has a key table (`2560L/17_…DocumentationViewer.png`). The unassessed-qualifier note links to its fix (`2560L/26`). A and B now teach what they need ("Select a plot first"). |
| F4 | Consistency and polish | 9 | The quit prompt now takes its menu name from the action (`main_window.py:1159`). Popup headings elide in the middle like the grid's. Button order follows the platform (`WD/28` Save/Revert, `MD/16_*` Revert/Save). Below 10: the same Summary chart uses two type sizes and two elision results for one cohort depending on whether a plot is selected (`150D/24` vs `150D/25`). The Identity rows beside it keep the large elided form, so one column holds two label styles. |
| F5 | Feedback and state | 10 | All three round-12 gaps are closed and verified live: the A/B reasons, the Settings "Saved" note (`extra/05_lab_settings__saved.png`), and the docs Loading note that waits for the drawn page (`MD/17`). Also verified: the regeneration toast "Regenerated 30 EICs", the export progress dialog and "Exported export.xlsx", the draft captions ("Bio_002 · not applied"), the fit caption "Sample_01 · Gaussian" on the tile and in the detailed view, and the departure-only deconvolution indicator. A small blemish remains (issue 3), but no state is missing or wrong. |
| F6 | Efficiency and flexibility | 10 | The Summary-width issue is fixed (see F2). The folded Scale button names the active scale. Every shortcut is intact: Ctrl+O/Shift+O/I/E, Ctrl+Alt+S/R, Ctrl+Shift+Y/P/L/B, Ctrl+F, Ctrl+[ ], Return, Ctrl+A, Esc, N/Shift+N, A, B and F1. Menus name their target ("Mark Bio_002 as Bad"). |
| F7 | Data visualisation | 9 | The Peak area rows now say why a bar is missing, matching the popup (`2560L/05` against `*/13`). The QC key stays beside the traces (`2560L/24`). The detailed view tags qualifiers "(Validated)" in its legend. Below 10: the 150% label defect (F1). For a compound whose qualifier is not assessed, the key still offers green "Validated" and red "Failed" while every qualifier trace is grey (`2560L/26`, `WD/26`; `graphs.py:790`). |
| F8 | Modern feel | 10 | Panels that yield and return like a fresh launch, a live theme, one-key review that explains refusals, a compact Settings window that confirms saves, and docs that never flash blank. On the 27" screen and on both CI platforms it reads as considered, current software. The 150% label glitch is a defect, not a gestalt problem. |
| F9 | Taste (not AI slop) | 9 | Copy is short and specific: "Bio_001 is not Below threshold", "Saved", "File > Export Session... keeps it.", "Applies to plots. Export asks again." Below 10: with the Summary open, the qualifier QC key appears twice at once, as the header key and the Identity footer (`2560L/24`). On Glycine and Serine the header key lists two states that cannot occur, directly above a note saying the qualifier is not assessed (`2560L/26`). The segmented "Shared Y / Scale to peak" pill is still the most generic control in the header. |

Overall: (9+10+10+9+10+10+9+10+9)/9 = **9.6** (round 12: 9.2).

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| Sidebar and Summary toggles in the header, the View menu and Ctrl+Alt+S/R | `*/05` | Yes: menu command plus shortcut plus a button beside its panel. |
| Shared Y and Scale to peak in the header (or the Scale button) and the View menu | `*/05`, `extra/09_lab_scale_menu__scale_shared.png` | Yes: the folded button now also states the active scale, which is useful at narrow widths. |
| The qualifier QC key in the header **and** the Identity footer, both visible now | `2560L/24`, `150D/24` | Partly. The header key explains line colours and the footer counts cells, but both show the same three states and colours, 1,400 px apart. Keep the header key and cut the footer to counts only ("16 ✓ 2 × 4 ?"). Or drop the footer's swatches. |
| The QC key on a compound with no assessed qualifier, with the "not assessed" note under it | `2560L/26`, `WD/26` | No. Two of its three entries cannot appear. Hide the key when no qualifier on the compound has an expected ratio (`graphs.py:790`). |
| The qualifier gap note in the grid header or the Identity panel | `extra/12_unl_glycine__closed.png` vs `__open` | Yes: verified one home at a time (`qc_note` hidden while the Summary is open). |
| The internal standard in the sidebar, the checklist and Settings | `*/04_*`, `16_settings_page4` | Yes: each is a place to act. |
| The deconvolution indicator in the status bar and Settings | log `indicator Deconvolution level 3 · …` | Yes: it appears only away from the defaults. |
| The fit override in the tile caption and the detailed-view heading | `probe3/01_p__fit.png`, `probe3/01_p__DetailedPlotDialog.png` | Yes: the detailed view is a separate window where the user acts on that sample. |

## Top issues, ranked by user impact

The other surfaces are clean. These four issues survived verification.

1. **At 150% scaling, the Peak area Summary's names change size and clip once a sample is selected.**
   - Where: `150D/24_unlabelled_grid.png` against `150D/25_unlabelled_sample_selected.png` (`crops/150_peakarea_24v25.png`).
   - Before the selection, the names are large and middle-elided down to five characters ("Sampl...ssing", "Samp...w_is").
   - After a selection, the font drops by about a third and the names are not elided. The longest names lose their first letters at the card edge ("ample_04_ratio_fail").
   - The labelled 150% Summary and the 1500 and 2560 folders do not show it (`crops/linux-light-1500x940_pa_24v25.png`, `crops/150_four.png`). Round 12's 150% shots kept one size across a selection (`crops/r12_150_peakarea_24v25.png`), so this is a regression.
   - Code: `fit_name_font` now uses `plotArea().height() / rows * 0.6` (`chart_style.py:136`), and `_fit_names` sizes the font and then elides (`total_abundance_widget.py:187-191`). The selection path (`set_highlighted` → `chart_area.show_rows`, `:193-200`) re-lays the chart, and the names are not re-elided at the new font.
   - Fix: elide in the same pass as the font, from the final plot height, after every `plotAreaChanged`. Make the Peak area and Identity name columns share one font and one elision. Elide names that share a prefix from the left of the distinguishing part ("…04_ratio_fail"), not "Sampl…_fail". Windows laptops at 150% are a primary platform for this rubric.
   - Gain: F1 +0.3, F7 +0.2, F4 +0.2.

2. **The qualifier QC key shows on compounds where no qualifier is assessed.**
   - Where: `2560L/26`, `WD/26`, `ML/26` (Glycine; Serine is the same). The header reads "Qualifier QC: ● Validated ● Failed ● Not assessed" above the note "Qualifier 1 is not assessed: the compound list gives it no expected ratio." Every qualifier trace is grey.
   - Code: `_qc_key_wanted = unlabelled and multi_trace and len(channels) > 1` (`graphs.py:790`) ignores whether any qualifier has a ratio.
   - Fix: want the key only when at least one qualifier on the compound is assessed. Then one line, the note, explains the grey traces.
   - Gain: F9 +0.2, F7 +0.1.

3. **A toast that refused an action survives the next successful action.**
   - Where: `extra/02_lab_keys.png`. A on Bio_001 → "Bio_001 is not Below threshold". B then marks Bio_001 bad (wash and "Marked bad" badge), and the old toast stays for up to 7 s under the newly marked plot.
   - Code: B succeeds through `action.trigger()` (`main_window.py:678`), which neither clears nor replaces the toast.
   - Fix: close any review toast when a review action succeeds, or confirm B with "Marked Bio_001 as bad · Undo (B)".
   - Gain: F5 +0.05, F9 +0.05.

4. **The qualifier key appears twice while the Summary is open.**
   - Where: `2560L/24`. The header key "Qualifier QC: ● Validated ● Failed ● Not assessed" now stays, and the Identity footer "Qualifier cells ✓ Validated 16 × Failed 2 ? Not assessed 4" repeats the same states with the same colours.
   - Fix: keep the header key, which explains the traces and the cells alike, and reduce the footer to counts ("16 ✓ · 2 × · 4 ?") without swatches.
   - Gain: F9 +0.1.

## Re-rating comparison

**My round-12 issues, status:**
1. **The quit prompt named a missing menu item: fixed.** Verified live: "This session is not saved. File > Export Session... keeps it."
2. **The Summary kept its launch width: fixed.** 2560 → 1500 gives `[296, 896, 300]`, 5 columns, no scroll. That equals the fresh 1500 launch from round 12. At 1280 it narrows to 244 px before closing at 1100.
3. **Blank first docs page on macOS dark: fixed.** `MD/17` renders Quick Start.
4. **No Peak area marker for 0 or <0.01: fixed.** `2560L/05` (Bio_004 "<0.01", Bio_014 "0"). Unlabelled Sample_05 and Sample_07 read "0" (`2560L/24`).
5. **Silent A/B: fixed.** Three messages verified ("Bio_001 is not Below threshold", "No selected plot is Below threshold", and "Select a plot first" in code at `main_window.py:686`).
6. **No line-colour key with the Summary open: fixed.** It brought issue 2 and issue 4 above.
7. **Small Summary text: fixed at 2560 and 1500.** At 150% the change is the cause of issue 1.
8. **No Save confirmation: fixed.** "Saved" appears and clears (log `hint Saved True`, then `''` 3.5 s later).

**Improved beyond the list:**
- Settings is as tall as its pages: 260 px, and 351 px for Deconvolution.
- The folded Scale button states and marks the active scale.
- The chooser and recovery lists elide in the middle (`*/32`).
- The detailed view names a fit override.
- The docs headings drop their category.

**Regressed:**
- The 150% Peak area labels (issue 1).
- The QC key now shows on unassessed compounds while the Summary is open, the default state (issue 2). Before, it showed only with the Summary closed.

**Lost functionality: none against `main` (5b17dac).**
- Every action label on `main` exists at 72561139. The only differences are case changes ("Accept Peak (Below Threshold)", "Mark Peak as Bad", "Curve Fit", "Use Compound Setting") and the earlier renames ("Select All" → "Select All Plots", "View Detailed..." → "Inspect Sample...").
- Every shortcut on `main` is still bound, and new ones were added.
- The fd447a30..72561139 diff removes no action, button, combo or setting. The Scale button keeps both modes, and the Settings minimum size moved from a fixed 400 px to the page list's height.
- The menus read live:
  - File: Load (Ctrl+O), Add Compound, Load Raw Data (Ctrl+Shift+O), Open Recent, Export Session, Import Session (Ctrl+I), New Analysis Session, Clear Session, Export Data (Ctrl+E), Process External Data, Settings, Quit;
  - View: Show Sidebar (Ctrl+Alt+S), Show Summary (Ctrl+Alt+R), Shared Y-Scale (Ctrl+Shift+Y), Scale to Selected Peak (Ctrl+Shift+P), Find Compound (Ctrl+F), Previous and Next Compound (Ctrl+[ ]), Sample List (Ctrl+Shift+L);
  - Review: Inspect (Return), Select All Plots (Ctrl+A), Deselect All (Esc), Show Only Selected, Show All, Next and Previous Flagged (N, Shift+N), Accept (A), Mark Bad (B), Curve Fit (Use Compound Setting, Auto, Gaussian, Bi-Gaussian, EMG), Baseline Correction (Ctrl+Shift+B);
  - Help: Documentation (F1), Check Data Setup, Check for Updates, About.

**What still stands between each factor and a 10:**
- **F1:** the 150% Summary labels (issue 1).
- **F2, F3, F5, F6, F8:** nothing material. For F5, issue 3 is a polish item.
- **F4:** two label styles in one Summary column at 150% (issue 1).
- **F7:** issue 1, and the QC key on unassessed compounds (issue 2).
- **F9:** the doubled qualifier key (issue 4), the key on unassessed compounds (issue 2), and the generic segmented pill.

**Per-platform limits:**
- **2560:**
  - offscreen renders plus my own drive at that geometry;
  - not checked: the native title bar, the macOS menu bar, hover.
- **Windows:**
  - CI at 100%, clean in both schemes (`WL/*`, `WD/*`; the Summary yields at 1028);
  - not checked: 125% and 150%. Issue 1 was seen at 150% on linux, and the real Windows 150% case is unverified but likely the same.
- **macOS:**
  - CI clean in both schemes, including docs in dark;
  - not checked: the native menu bar and an OS scheme switch.
- **150%:** dark only (`150D/*`), clean apart from issue 1.

```json
{"F1": 9, "F2": 10, "F3": 10, "F4": 9, "F5": 10, "F6": 10, "F7": 9, "F8": 10, "F9": 9, "overall": 9.6}
```
