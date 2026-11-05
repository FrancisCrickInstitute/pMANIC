# MANIC UI/UX review, round 6 (re-rating at 1581a94), reviewer: opus

## Evidence

**Screenshots.** I viewed all 472 PNGs in the eight round-6 folders as 3×3 contact sheets (`sheets/`), then looked at full size wherever a detail mattered (150% grid and checklist, Windows Process External, the macOS Review menu, the CI macOS docs page). Short names used below:
- `WL/` and `WD/`: Windows light and dark (CI, 1024×720).
- `ML/` and `MD/`: CI macOS light and dark (1024×681).
- `mL/` and `mD/`: the local Mac (1512×949).
- `150L/` and `150D/`: the 150% folders (1008×633 logical).

**My own drives.** These ran on this Mac against `pMANIC-review-r6` at 1581a94, with real windows. Scripts and output are in this folder.
- `drive.py`, which writes `extra/` and `extra/log.txt`. On labelled data it:
  - did a fresh load and read the sidebar, header and status bar;
  - set Palatinose as the internal standard, which gave Bio_004 "Below threshold";
  - changed the left offset for 2 selected plots and applied it with Ctrl+Return, then checked that the edited samples kept 0.1 and an untouched one kept 0.08;
  - toggled View › Shared Y-Scale;
  - changed Settings › Peak Validation and saved it;
  - opened the sample-list and compound-list menus;
  - opened Summary at 1512, 1280 and 1024 wide, and resized the main window to 1280×720 and 1024×640;
  - switched to Compact;
  - opened the detailed view with Return;
  - opened Documentation;
  - exported the session;
  - opened the Clear Session prompt and About.

  On unlabelled data it went through all 8 compounds in the grid and in Summary.
- `keys.py` covers the verdict keys and both data exports.
  - The verdict keys first. While other tours held focus, my window could not become active. Once I forced activation (`QApplication.setActiveWindow`), I pressed A, A, B and B on Bio_004. The badges went Accepted, Below threshold, Marked bad, Below threshold, so both keys toggle correctly (`keys2.out`).
  - Then the exports, answering Yes to the prompts:
    - labelled wrote 5 sheets in 15 s, with the toast "Exported export.xlsx · Show in Folder";
    - unlabelled wrote Raw Values, Abundances and Qualifier QC in 2.6 s (`keys.out`).
- I also diffed the UI action labels between `origin/main`, 6ec219c and 1581a94 (`labels_*.txt`).

**Not run:**
- real hover and tooltips;
- the native macOS menu-bar rendering of the View and Review menus (only the captured popups);
- Windows at 125% and 150%;
- a real OS-driven scheme switch;
- Delete Sample and Recover;
- Import Session.

## Verdict

**Functionally, every path I drove works.**
- **Fresh load:** all sidebar rows tick, and the header reads "Pyruvate tR 7.09". The status bar shows "Imported 2850 EICs" and the deconvolution state.
- **Verdict keys:** A accepts and clears, B marks bad and clears, and B typed into a text field types instead of marking.
- **Peak window:** Ctrl+Return applies only to the selection, and mixed values show as "0.08 - 0.1".
- **Settings:** the dirty page gets a dot and a primary Save, and both buttons disable after saving.
- **Exports:** both data exports and the session export finish with a toast that has Show in Folder.
- **Serine:** the grid has lost its amber wall. Serine has one header note with a guide link instead.
- **Clear Session:** it states once what it removes and has a red Clear Session button.

Almost all of my round 5 list is fixed. The app now reads as a considered, quiet, consistent tool on Windows and macOS, in light and dark, and at 150%.

What separates it from a 10 is a short list of finish problems:
- the Identity summary counts qualifiers the method doesn't have;
- a compound with no assessable qualifier gets no grid note, while a partial gap does;
- the session file still lands in a subfolder the user never chose;
- the keyboard table in the docs omits the new keys;
- macOS hides the ⌘⇧B hint;
- Settings is a large window of mostly empty pages;
- the abundance bars are still stock teal;
- the labelled spectrum wastes most of its width.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 9 | One token system holds across all eight folders (`WD/24`, `MD/24`, `150D/33`). The amber wall is gone (`extra/18_unlab__c3.png`), and nothing is sliced above the pinned Apply group (`extra/11_w1024x640.png`, `150D/33`). The detailed view is clean and themed (`150L/11`). Held back by: stock teal abundance bars (`colors.py:24`, `WL/13`); Settings as an 880×720 window of mostly empty pages (`settings_window.py:814`, `WL/16_*`); a lone scrollbar next to the Baseline checkbox at 150% (`150D/33`). |
| F2 | Layout and hierarchy | 9 | The offsets and Reset/Apply form one group that never splits (`extra/11_w1024x640.png`). Summary on short windows gives one chart full height and folds the other (`extra/09_summary__summary_1024.png`). The detailed view puts TIC and spectrum side by side under a tall EIC (`WL/11`). Remaining: Settings pages hold one or two rows each (`WL/16_…page3`, `…page4`). At 150% the checklist's "How do I change a pattern?" disclosure falls below the fold (`150D/04_…Dialog`). |
| F3 | Onboarding and workflow clarity | 9 | Mode chooser: two equal options, one line each (`WL/01`). The empty canvas asks for one thing (`WL/02`). The checklist is short with steps behind a disclosure (`WL/04_*steps`). A partial QC gap explains itself in the header with a guide link (`extra/18_unlab__c3.png`). Gaps to 10: Glycine, where no qualifier can be assessed, gets no grid note (`identity_chart.py:116-118`, `extra/18_unlab__c2.png`). The Quick Start keyboard table omits A, B, Ctrl/⌘+Return and Ctrl+Shift+Y/P (`docs/00_quick_start.md:14-22`). The start footer is still an instruction sentence (`start_panel.py:93`). |
| F4 | Consistency and polish | 9 | "Not assessed" is the one grey-state name in the header, Summary and popup (`WD/24`, `WL/31`). Settings now has a primary Save with a dirty dot like the other dialogs (`extra/05_settings_change__settings_dirty.png`). The Review and context menus match. Gaps: macOS shows no ⌘⇧B on Baseline Correction while Windows shows Ctrl+Shift+B (`MD/10_review_menu__menu` against `WL/10_…menu`; `main_window.py:572-576` lacks `setShortcutVisibleInContextMenu`). The Identity legend mixes glyphs ("■ – ? Not assessed", `extra/sheets/sum7_crop.png`). The detailed legend uses a lower-case "(not assessed)" (`WD/32`). |
| F5 | Feedback and state | 9 | Verified live: Below threshold, Accepted and Marked bad pills; menu labels that flip ("Clear Bad Mark"); "Applies to Bio_006" only when a selection narrows scope; "0.08 - 0.1"; Settings dirty dot; the import toast; export toasts with Show in Folder. Gaps to 10: Identity "Not assessed 12" counts 11 cells for a Qualifier 2 that Lactate, Uncalibrated and scyllo-Inositol don't have (`identity_chart.py:64`, `extra/sheets/sum7_crop.png`). The session file is written to `manic_session_export/` under the chosen folder, not to the chosen path (`main_window.py:2026-2030`, `extra/15_export__session_exported.png`). On CI macOS the first Documentation page was captured blank (`ML/17_documentation…`, `MD/17_…`). |
| F6 | Efficiency and flexibility | 9 | A and B verdict keys, verified with focus; Ctrl/⌘+Return applies; Ctrl+Shift+Y/P scale toggles; Find, Previous and Next Compound; Sample List Ctrl+Shift+L; Compact 6 columns; pinned editors on short windows. To reach 10: a "next flagged sample" key (jump to the next Below threshold, QC fail or Not detected tile) for the review loop, a key to focus the Peak window fields, and the keys listed in the docs table. |
| F7 | Data visualisation | 9 | The detailed view has a tall EIC with TIC and spectrum beside each other, readable ticks and a tR/integration footer (`150L/11`, `WD/32`). The Identity grid is clear (`extra/18_unlab__sum3.png`). The isotopologue colours are the user's choice and are not scored down. Remaining: in the labelled spectrum all bars sit at 174–177 on a 60–400 m/z axis, with the "M+0…M+3" label crowding them (`150L/11`, `WL/11`). The Identity grid draws a column for an absent qualifier. The abundance bars are stock teal (`colors.py:24`). |
| F8 | Modern feel | 9 | Toasts with an action, a Save/Revert footer with a dirty dot, the segmented density control, pinned editors, a live scheme switch, and one-key verdicts. This reads as modern desktop software. The large, near-empty Settings window and the matplotlib-styled tick type in tiles still look older than the rest. |
| F9 | Taste (not AI slop) | 8 | The template remnants are gone: the choice-card mode chooser, the paragraph Settings, "Save this page", the debug footer, the default-scope caption and the amber wall. What is left is small and named in the table below: stock teal bars, the code-like "Qualifier colour = QC" legend on every unlabelled header, the footer instruction sentence, the over-sized Settings window, and the Identity "–" column. Clean and specific, with a few generic edges, so 8 rather than 9. |

Overall: (9+9+9+9+9+9+9+9+8)/9 = 8.89 → **8.9** (round 5: 8.2).

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| Identity grid "Qualifier 2" column of "–" for compounds with one qualifier, counted into "Not assessed 12" | `extra/sheets/sum7_crop.png`, `sum6_crop.png`; `identity_chart.py:64` | No. It shows state that doesn't exist and inflates the count. |
| "Qualifier colour = QC ● Validated ● Failed ● Not assessed" on every unlabelled compound header, next to the Summary legend with counts | `WD/24`, `extra/18_unlab__sum3.png`; `graphs.py:245` | Partly. The grid needs a key, but "=" notation reads like code, and both legends are visible while Summary is open. |
| Footer sentence "Saved session: load its data, then File → Import Session" | `WL/02`; `start_panel.py:93` | No. It is an instruction where a link or a menu hint would do. |
| Settings: an 880×720 window where three pages hold one or two rows | `WL/16_*`; `settings_window.py:814` | No. The empty space is a template proportion, not one chosen for the content. |
| Stock teal abundance bars | `WL/13`; `colors.py:24` | Generic (not the declined isotopologue palette). |
| Deconvolution summary in the status bar and on Settings › Deconvolution | `WL/05`, `WL/16_…page5` | Yes. One is persistent status that opens the other on click. |
| Internal standard in the sidebar, the compound menu, the checklist and Settings (read-only) | `WL/05`, `extra/07`, `WL/04`, `extra/05_…InternalStandard.png` | Yes. Settings now only names the standard next to the reference peak it qualifies. |
| Review menu and plot context menu carry the same commands | `WL/09`, `WL/10` | Yes. A menu plus a context menu. |
| Sidebar "Compound list · Not loaded" and canvas "Drop a compound list here" | `WL/02` | Yes. Status versus the call to action. |
| "Re-extracts all 30 shown samples" under the tR window | `WL/05` | Yes. A different action with a different scope, stated where the user acts. |

## Top 12 issues, ranked by user impact

1. **The Identity summary reports qualifiers the method doesn't have.**
   - Where: Lactate, Uncalibrated and scyllo-Inositol have only Qualifier 1 (`testdata/unlabelled_synthetic/compounds.csv`). Summary still draws a "Qualifier 2" column of "–" cells and counts them under "Not assessed 12", when only one sample (Sample_05, not detected) is really unassessed. See `extra/sheets/sum7_crop.png` and `sum6_crop.png`. The cell status is `QualifierStatus.ABSENT` → "–" (`identity_chart.py:64`).
   - Fix: build columns from the compound's own qualifiers and count only real cells. Drop "–" from the legend unless an absent cell can actually appear.
   - Gain: F5 +0.25, F7 +0.25, F9 +0.1.

2. **A compound with no assessable qualifier gets no grid note.**
   - Where: `qualifier_gap_note` returns `None` unless at least one qualifier is checkable (`identity_chart.py:116-118`). Serine (one of two qualifiers missing a ratio) gets the header note. Glycine, whose only qualifier has no ratio, shows a grey line on every tile and the legend, with no explanation outside Summary and the popup (`extra/18_unlab__c2.png` against `c3`).
   - Fix: emit the same one-line header note when no qualifier can be checked ("Qualifier 1 is not assessed: the compound list gives it no expected ratio. See Fix a missing qualifier ratio.").
   - Gain: F5 +0.25, F3 +0.1, F4 +0.1.

3. **The session file still goes where the user didn't put it.**
   - Where: Export Session saves `<chosen folder>/manic_session_export/<name>.json` (`main_window.py:2026-2030`; verified, `extra/log.txt`, `extra/15_export__session_exported.png`). The toast now says so ("Exported mysession.json to manic_session_export"), which fixes the lie but not the surprise. This behaviour is inherited from main.
   - Fix: write to the exact path from the save dialog. The writer is UI plumbing, not science.
   - Gain: F5 +0.25, F8 +0.1.

4. **The docs keyboard table misses the new keys.**
   - Where: `docs/00_quick_start.md:14-22` lists arrows, Space, Return, Esc, Ctrl+A, Ctrl+[ ] and Ctrl+F. It does not list A, B, Ctrl/⌘+Return (Peak window) or Ctrl+Shift+Y/P (View scales).
   - Fix: add the four rows. That makes the docs and the menus the same list.
   - Gain: F3 +0.1, F6 +0.1.

5. **macOS hides the Baseline Correction shortcut.**
   - Where: the captured macOS Review menu shows ↵, ⌘A, ⎋, A and B, but no ⌘⇧B on Baseline Correction (`MD/10_review_menu__menu`, `ML/10_…`). Windows shows Ctrl+Shift+B (`WL/10_…menu`). `baseline_action` (`main_window.py:572-576`) is the one Review action without `setShortcutVisibleInContextMenu(True)`. The native menu-bar rendering is still unverified.
   - Fix: set it, as `grid_key` and `verdict_key` already do.
   - Gain: F4 +0.1.

6. **Settings is a big window of nearly empty pages.**
   - Where: `resize_to_screen(self, 880, 720)` (`settings_window.py:814`). Mass Tolerance, Natural Abundance and Internal Standard each hold one or two rows above about 500 px of blank space (`WL/16_*`, `extra/05_settings_change__InternalStandard.png`).
   - Fix: size the window to its tallest page (about 600×420), or merge the one-row pages into a single "General" page with section titles. Keep Deconvolution separate.
   - Gain: F2 +0.1, F8 +0.1, F9 +0.25.

7. **The labelled spectrum spends most of its width on empty m/z.**
   - Where: in Pyruvate in Bio_001 every bar sits at 174–177 on a 60–400 axis, and the "M+0…M+3" bracket label sits on top of them (`150L/11`, `WL/11`, `mL/11`). The unlabelled spectrum reads well, because its peaks are spread out (`WD/32`).
   - Fix: open the labelled spectrum zoomed to the isotopologue cluster ±20 m/z, with "Reset all" returning to the full scan. Place the bracket label above the tallest bar.
   - Gain: F7 +0.25.

8. **The abundance bars are stock teal.**
   - Where: `abundance_colour = QColor(0, 128, 128)` (`colors.py:24`); `WL/13`, `WD/13`. This is not the isotopologue palette the user chose to keep.
   - Fix: neutral data ink from the theme for bars, and the accent for the selected or hovered sample, so the popup shares the grid's selection language.
   - Gain: F7 +0.1, F9 +0.1, F1 +0.1.

9. **The first Documentation page can flash blank.**
   - Where: both CI macOS captures of Quick Start are empty (`ML/17_documentation__DocumentationViewer.png`, `MD/17_…`; pixel stddev 6–8 against 45–58 elsewhere), while every other page and every other folder rendered. The viewer leaves "Loading…" on `loadFinished` (`documentation_viewer.py:206-215`), which can come before Chromium's first paint. Locally it rendered at once (`extra/14_docs__docs_immediate.png`), so this may be CI-only.
   - Fix: keep the status page until the first frame (for example a `requestAnimationFrame` round-trip through `runJavaScript`, or a short single-shot delay after `loadFinished`).
   - Gain: F5 +0.1.

10. **The start footer is still an instruction sentence.**
    - Where: "Saved session: load its data, then File → Import Session" (`start_panel.py:93`, `WL/02`, `WL/03`).
    - Fix: drop the sentence. Make Import Session's disabled state carry the hint as a tooltip ("Load the session's compound list and raw data first"), or show an "Import session…" link once data is loaded.
    - Gain: F9 +0.1, F3 +0.1.

11. **The unlabelled QC legend reads like code and doubles up in Summary.**
    - Where: "Qualifier colour = QC ● Validated ● Failed ● Not assessed" under every unlabelled header (`graphs.py:245`, `WD/24`). It is shown alongside the Summary Identity legend with counts (`extra/18_unlab__sum3.png`).
    - Fix: label it "Qualifier QC: ● Validated ● Failed ● Not assessed" and hide it while the Summary tab, which carries its own counted legend, is open.
    - Gain: F9 +0.1, F4 +0.1.

12. **150% short screens still bury two things.**
    - The checklist's "How do I change a pattern?" disclosure falls below the fold behind the MM table (`150D/04_labelled_loaded_checklist__PostLoadChecklistDialog.png`). Fix: cap the table at about 5 visible rows when the dialog is short.
    - In the sidebar, the Samples list shows one row and the lower inspector gets its own scrollbar beside the lone Baseline checkbox (`150D/33`). Fix: give Baseline and tR window their own collapsible "More" row, or hide the scrollbar when only one row is clipped.
    - Gain: F2 +0.1, F1 +0.1.

## Re-rating comparison

**My round 5 issues, status:**
1. **Compound-level QC gap painted the grid amber: fixed.** Serine shows one header note with a "Fix a missing qualifier ratio" link, and no tile tint or badge. Sample_04_ratio_fail stands out again in Alanine (`extra/18_unlab__c3.png`, `WD/24`). A new gap is the all-unassessed case (issue 2).
2. **No keyboard path for verdicts: fixed.** Verified with focus: A accepts and clears, B marks and clears, and both are scoped to the grid (B in a text field types). Ctrl+Return applies the Peak window. Both menus show A and B. The docs table lags (issue 4).
3. **Field sliced above the pinned Apply row: fixed.** The offsets and Reset/Apply are one group, whole at 1024×640 and at 150% (`extra/11_w1024x640.png`, `150D/33`).
4. **Grey QC state with three names: fixed.** "Not assessed" in the header, the Summary and the popup. The reasons stay on the popup chips. A lower-case "(not assessed)" remains in the detailed legend, and the Summary legend now mixes "– ?" (issue 1).
5. **Palette: declined by the user, not scored.** The teal abundance bars remain (issue 8).
6. **Settings paragraphs and "Save this page": fixed.** One-line leads, "?" help, Revert/Save, a primary Save when dirty and a dirty dot on the page (`extra/05_settings_change__settings_dirty.png`). The window size is new feedback (issue 6).
7. **Detailed view below the fold and debug footer: fixed.** TIC and spectrum sit side by side, and the footer shows only tR, apex and integration. The labelled spectrum range is the remaining nit (issue 7).
8. **Export modal: fixed.** Data and session exports end in a toast with Show in Folder, verified live in both modes.
9. **Internal standard with four editors: fixed.** Settings › Internal Standard names the standard read-only next to the reference peak.
10. **Choice-card mode chooser: fixed.** Two equal outlined options with one-line captions (`WL/01`).
11. **Default-scope caption: fixed.** No caption by default; "Applies to Bio_006" or "Applies to 3 selected samples" appears when a selection narrows the scope.
12. **Display tab and the macOS shortcut column: mostly fixed.**
    - The Display tab is gone. Shared Y-Scale (Ctrl+Shift+Y) and Scale to Selected Peak (Ctrl+Shift+P) are in View and work (`extra/04_view_menu__sharedY.png`).
    - The macOS popups now show the shortcut column.
    - Baseline Correction still lacks its macOS hint (issue 5).

**Improved beyond the list:**
- Clear Session states once what it removes, with a red Clear Session button.
- Unlabelled Summary no longer clips the qualifier columns.
- Add Compound shows ion errors under each row (`WL/28`).
- Summary on short windows folds the second chart to its title (`extra/09_summary__summary_1024.png`).

**Regressed:** nothing functional. The only new oddities are the Identity "–" column (issue 1) and the blank first docs capture on CI macOS (issue 9).

**Lost functionality: none found.**
- Every label present only on `origin/main` has a renamed or moved equivalent (`labels_main.txt` against `labels_1581a94.txt`):
  - "View Detailed..." → "Inspect Sample...";
  - "Select All" → "Select All Plots";
  - "Accept peak (below threshold)" and "Mark peak as bad" → title case;
  - "Curve fit" → "Curve Fit";
  - "Use compound setting" → "Use Compound Setting" (`graphs.py:1072`);
  - "Update tR Window" → "Apply window";
  - "Restore Selected" → "Restore selected" (`recovery_dialog.py:57`);
  - "Shared y-scale" and "Scale to selected peak" → View menu, title case, now with shortcuts;
  - the recovery dialogs' "Cancel" → a `button_box`.
- Since round 5, the "Clear filter" button became the line edit's native clear button (`sidebar_widgets.py:291`, visible in `WL/29`).
- Live checks:
  - all five compound-list entries;
  - the sample-list menu (Delete, Show Only, Hide, Show All, Recover);
  - multi-select;
  - accept, mark and clear by menu and by key;
  - the Curve Fit submenu;
  - Baseline Correction;
  - both scale toggles;
  - the internal-standard menu;
  - both data exports and the session export;
  - the detailed view by Return.

**Per-platform limits.**
- **Windows** was judged from CI at 100% and 1024×720, and is clean in both schemes. Not verified: 125% and 150% scaling, the native dark title bar, hover and tooltips.
- **macOS:**
  - The native menu-bar rendering of the View and Review menus (shortcut column, ⌘⇧B) was not verified.
  - The tour forces the scheme, so a real OS switch was not tested.
  - Keyboard verdicts were verified only after forcing activation, because other tours held focus on this machine. That is a property of the test environment, not of the app.
- **150%** is the harsh 1008×633 stand-in, not a real laptop.

```json
{"F1": 9, "F2": 9, "F3": 9, "F4": 9, "F5": 9, "F6": 9, "F7": 9, "F8": 9, "F9": 8, "overall": 8.9}
```
