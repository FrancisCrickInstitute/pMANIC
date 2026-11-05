# MANIC UI/UX review, round 11 (re-rating at 86a53c3), reviewer: opus

## Evidence

**Screenshots.** I viewed all 620 PNGs in the ten round-11 folders. The two 2560 folders went through 3×3 contact sheets at 1000 px a tile, and the eight others through 4×4 sheets (`sheets/`). I opened full size or cropped wherever a detail mattered: `2560L/05`, `2560L/24`, `2560L/31`, `2560D/27`, `ML/05`, `ML/31`, `WL/05`, the 2560 Summary column (`crops/24_summary.png`), the grid header (`crops/24_header.png`) and the sidebar edge (`crops/24_border_edge.png`, `crops/31d_border.png`). I also measured pixel variance on every first Documentation page. Short names used below:
- `2560L/`, `2560D/`: real captures on the 2560×1410 monitor, light and dark. This is the primary target.
- `WL/`, `WD/`: Windows CI at 1024×720.
- `ML/`, `MD/`: macOS CI at 1024×681.
- `1500L/`, `1500D/`: 1500×940 windows on the same monitor.
- `150L/`, `150D/`: 150% scaling, with a 1280×800 window.

**My own drives.** I ran `pMANIC-review-r11` at 86a53c3 on Qt's offscreen platform with `screen2560.json`. The scripts are in this folder, the output is in `run.out` and `extra/log.txt`, and the shots are in `extra/`.
- **`drive11.py`, labelled data:**
  - fresh window: read the sidebar and the panel state;
  - in the checklist: opened the standard chooser, typed "scyl", pressed Return, then Apply;
  - read the status bar, header, sidebar and badges;
  - Shared Y, View › Scale to Selected Peak, then the peak button again;
  - the Summary button, Ctrl+Alt+R and Ctrl+Alt+S, and the remembered settings;
  - from the compound list: N ×3, A, N, B, the N/A loop, then N with nothing left to review;
  - Peak window: drafted a Left offset and a tR window, read both captions and the primaries, then Return to apply;
  - Settings: every page in turn, read Save/Revert on each, chose Theme › Dark and back, edited Minimum area ratio, switched page while unsaved, then Save;
  - read every menu, opened the detailed view and both summary popups;
  - a full export;
  - resized to 1280×800 and 1024×768 with the Summary open, then back to 2560, measuring clipping, splitter sizes, tile size and columns.
- **`drive11.py`, unlabelled data:**
  - all 8 compounds and their badges;
  - Samples expanded, with and without a compound filter, with geometry measured;
  - 1280 and 1024 with the Summary open.
- **`probeN.py`:** unlabelled N from the compound list.
- **Code:** the string diff 4119119 → 86a53c3 (`labels_*.txt`), and the action labels on `origin/main` against 86a53c3.

**Harness noise, not app bugs:**
- In `drive11.py` the unlabelled N presses went nowhere because the second window was not active offscreen. `probeN.py` activated it first, and N cycled 04 → 05 → 07 → 04, with the menu trigger going on to 05.
- The two "QMenu already deleted" tracebacks in `run.out` come from my menu dump wrapping `QAction.menu()`. This is the same artefact as rounds 8–10.
- `menu_texts` prints only the first shortcut, so Settings looked shortcut-less. The code gives it `QKeySequence.Preferences` and Ctrl+, (`main_window.py:364-368`).

**Not run:**
- real hover and tooltips;
- the native macOS menu bar;
- Windows at 125% and 150%;
- a real OS scheme switch;
- Delete and Recover for compounds and samples;
- session import;
- an EIC regeneration through Apply window;
- the rebuild-from-Raw-Values flow with real files.

## Verdict

The app works end to end on both datasets, and every round-10 layout defect I raised is gone. I verified these live:
- **Samples section:** it hugs its rows at 2560. Heading at y 401, filter at 431, list at 467–731, Peak window at 743 (`extra/11_samples_gap__samples_open.png`).
- **Laptop widths:** at 1024 with the Summary open the sidebar gets its content width (`[279, 494, 243]`), and nothing clips.
- **Dark washes:** rose, lavender and tan are now distinct (`2560D/27`).
- **QC key:** it hides while the Summary shows its Identity legend (`crops/24_header.png`).
- **Unlabelled Summary:** the Identity rows grow and fill the column.
- **Copy:** both draft captions read "All 30 shown · not applied". The popup titles are sentence case. The abundance popup subtitle is just "30 samples".
- **Header:** the Docs icon is gone, and the header fits on one row at 1280.

Also working: the chooser in the checklist, the N/A/B review loop, the "No flagged plots in Pyruvate" toast, Settings with its unsaved dot and the "Also unsaved: Peak validation" link, the live theme, and an export in 24 s that wrote five sheets and showed a toast.

At 2560 it is calm, balanced and uses the space well:
- **Labelled:** 30 tiles at 303×249 in six columns, no scroll, with both Summary charts in full (`2560L/05`).
- **Unlabelled:** 11 tiles at 458×421 in four columns (`2560L/24`).

What remains is small:
- Labelled peaks outside the window are still unflagged. This was declined, and it is the largest review gap left.
- The sidebar's right divider is drawn only below the inspector, so on the primary screen it starts mid-height.
- The first docs page is still blank on CI macOS in dark mode.
- A tooltip calls the rose Below threshold badge "amber".
- At 1024 the header still wraps with the Summary open.

Nothing that exists on `main` is missing.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 9 | One token system across all ten folders. At 2560 the six-column grid, the slim sidebar and the Summary column are quiet and well proportioned (`2560L/05`, `2560D/05`). The verdict washes read cleanly in both schemes (`2560L/27`, `2560D/27`), and Not detected tiles show their raw traces in grey. Held back by the sidebar divider: it starts partway down the window, wherever the inspector ends (`2560L/24`: x 295 from y 683; `2560L/31`: from y 871; `2560L/05`: none; `crops/31d_border.png`). The cause is that `#toolbar`'s `border-right` (`style.qss:795-798`) is painted over by its full-width children. |
| F2 | Layout and hierarchy | 9 | Both round-10 defects are fixed. The Samples section hugs its content, and the Peak window sits right under it (`extra/11_*`). The sidebar keeps its content width at 1024 and the Summary takes the squeeze (`main_window.py:798-826`, `_summary_fits` `:817`). The header holds one row at 1280 (`crops/1280_header.png`). Left: at 1024 with the Summary open, the grid is 494 px, tiles are 230×165, and the Shared Y / Scale to peak control drops to a second header row (`extra/09_narrow__1024.png`). |
| F3 | Onboarding and workflow clarity | 9 | Quiet empty states with one action each (`*/02`, `*/03`). The checklist offers a searchable chooser, then Apply or "Continue without changes". The rebuild link shows only in labelled mode. Unassessed qualifiers explain themselves with a docs link ("Qualifier 1 is not assessed… See Fix a missing qualifier ratio", `*/26`). Gap: labelled peaks outside the window still look clean, so "No flagged plots in Pyruvate" can mislead a new user (Bio_014, 018, 019 and 020 in `2560L/05`). |
| F4 | Consistency and polish | 9 | One chooser, one caption pattern and sentence-case titles everywhere ('Label incorporation — MANIC'). Button order follows the platform (`WL/20` Rebuild/Cancel, `ML/20` Cancel/Rebuild). Appearance has no Save/Revert, and every other page does (`16_settings*`). Left: the partial sidebar divider. The Peak validation tooltip says "an amber Below threshold badge" while the badge is rose #FFCCCC (`settings_window.py:231`, `peak_verdict.py:29`). At narrow widths names are cut two ways: end-ellipsis in tiles ("Sample_04_rati…") and middle-ellipsis in the Summary ("Sample_…io_fail") (`extra/12_narrow_unlab__u1024.png`, `*/35`). |
| F5 | Feedback and state | 9 | Verified live: the N toast, the verdict pills plus washes, menus that name their target ("Accept Bio_004 (Below Threshold)", "Clear Bad Mark (Bio_004)"), the draft captions with a single primary button, the unsaved dot on a Settings page, the "Also unsaved" link, and the export toast. The Summary highlights the selected sample. Gaps: the out-of-window flag (declined), and the first docs page is still blank on CI macOS in dark (`MD/17`, stddev 3.8 against 44–56 elsewhere). Light now renders. Settings › Save gives no confirmation beyond the dot clearing. |
| F6 | Efficiency and flexibility | 9 | Panel toggles with shortcuts, remembered (`settings stored True True`). One-click y-scale toggles, mirrored in View. Ctrl+, opens Settings. N/A/B work from the list and the grid. ‹ › step through the detailed view. The chooser filters by keyboard. Tiles size themselves to fit every sample at 2560 with no setting needed. Gap: at 1024 the remembered Summary stays open and leaves a two-column grid of small tiles with a wrapped header. Yielding it one step earlier would suit a laptop. |
| F7 | Data visualisation | 9 | Workbook-matched verdict washes, distinct in dark now. Grey raw traces on Not detected tiles. Clear Identity heatmap with counts. The label-incorporation and peak-area popups have a precise axis and no repeated title (`*/13`, `*/14`). The detailed view has a TIC and a spectrum (`*/11`, `*/34`). Remaining: the out-of-window flag. |
| F8 | Modern feel | 9 | Self-sizing grid, toggleable remembered panels, a live theme, a searchable chooser, one-key review, docs with Find. It reads as considered software on the 27" screen. The mid-height divider and the CI-macOS-dark blank docs page are the only things that look unfinished. |
| F9 | Taste (not AI slop) | 9 | The round-10 redundancies are gone: the doubled QC key, "Peak area" twice in one popup, the Docs icon. Copy is short and specific ("No amount: exports peak areas", "Weak peaks get a Below threshold badge only when an internal standard is set."). Left: the status bar shows the same sentence on every screen and for every compound, "Deconvolution level 4 · automatic peak shape · balanced noise gate" (`*/05`, `*/24`). It restates Settings › Deconvolution even at the defaults. The "amber" wording is wrong. Four of the seven Settings pages hold a single control (`16_settings_page2`, `_page3`, `_page5`, `_page6`). |

Overall: (9+9+9+9+9+9+9+9+9)/9 = **9.0** (round 10: 8.9).

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| The deconvolution sentence in the status bar, permanently, and the same settings in Settings › Deconvolution | `*/05`, `*/24`, every main-window shot | Partly. It is clickable (it opens Settings) and the setting changes the numbers. But at the defaults it repeats the same 63 characters on every screen. Showing it only when a compound departs from the default, or shortening it to "Deconvolution 4", would remove most of it. |
| Sidebar and Summary toggles in the header, the View menu and Ctrl+Alt+S/R | `*/05`, `main_window.py` View menu | Yes. A menu command with its shortcut, plus a button next to the panel it opens. |
| Shared Y and Scale to peak in the header and the View menu | `*/05` | Yes. The user asked for them visible, and the menu holds the shortcuts. |
| The Qualifier QC key in the header and the Identity legend | `crops/24_header.png`, `*/24` (Summary closed) | Now justified. Only one shows at a time. |
| The internal standard in the sidebar row, the checklist and Settings › Internal standard | `*/04_*`, `16_settings_page4` | Yes. Each is a place where the user acts, and it is one widget throughout. |
| "No amount: exports peak areas" as a chooser heading, and the export prompt | `*/32` | Yes. A label at the moment of choice, and a confirmation at the action. |
| A Peak validation tooltip that names a colour the badge does not have ("amber") | `settings_window.py:231` | No. It is a copy error. Say "a Below threshold badge". |

## Top issues, ranked by user impact

These are the eight that survive verification. I found nothing else worth ranking: the remaining surfaces are clean.

1. **Labelled peaks wholly outside the integration window carry no flag.**
   - Where: Pyruvate Bio_014, 018, 019 and 020 (`2560L/05`, `2560D/05`). N then says "No flagged plots in Pyruvate".
   - Status: declined pending a science-side definition, which is to be a PR follow-up.
   - Fix: settle the definition, then add it as one more badge state. The badge and pill system is ready for it.
   - Gain: F5 +0.2, F3 +0.1, F7 +0.15.

2. **The sidebar's right divider starts mid-height on the primary screen.**
   - Where: `2560L/24` (x 295 runs from y 683), `2560L/31` (from y 871), `2560L/02` (from y 164), `2560L/05` (absent), `2560D/*` the same; `crops/24_border_edge.png`, `crops/31d_border.png`.
   - Cause: `QWidget#toolbar { border-right }` (`style.qss:795-798`) is covered by `#sidebarHeader`, `#sidebarBrowse` and `#sidebarInspector`, which paint `@surface` across the full width (`style.qss:800-806`). The line shows only where no child paints.
   - Fix: inset the toolbar's layout 1 px on the right, so the children stop short of the border. Or move the line to the splitter handle, so it runs the full height on every screen.
   - Gain: F1 +0.2, F4 +0.1, F8 +0.05.

3. **The first Documentation page is blank on CI macOS in dark mode.**
   - Where: `MD/17` (pixel stddev 3.8; every other folder is 44–56). Light now renders (`ML/17`). This is a known limit.
   - Fix: hold the "Loading…" page until `loadFinished` plus one `requestAnimationFrame` round trip through `runJavaScript`, then switch.
   - Gain: F5 +0.1, F8 +0.05.

4. **At 1024 with the Summary open, the grid is cramped and the header wraps.**
   - Where: `extra/09_narrow__1024.png`. The splitter reads `[279, 494, 243]`, giving tiles of 230×165 in two columns. Shared Y / Scale to peak sit on a second header row.
   - Fix: hide the segmented control's labels behind icons below about 560 px of grid width. Or raise `_summary_fits` (`main_window.py:817`) so it needs three grid columns, which yields the Summary at small laptop widths.
   - Gain: F2 +0.1, F6 +0.1.

5. **A tooltip names the wrong colour.**
   - Where: `settings_window.py:231`, "A peak below this ratio gets an amber Below threshold badge". The badge is rose (`peak_verdict.py:29` #FFCCCC; `*/27`).
   - Fix: "…gets a Below threshold badge."
   - Gain: F4 +0.05, F9 +0.05.

6. **The status bar repeats the deconvolution settings on every screen.**
   - Where: every main-window shot.
   - Fix: show it only when the selected compound departs from the default (level 4, Auto, Balanced). Or shorten it to "Deconvolution 4" and keep the detail in its tooltip.
   - Gain: F9 +0.1, F1 +0.05.

7. **Names are cut two different ways at narrow widths.**
   - Where: tile headers use an end ellipsis ("Sample_04_rati…", "Sample_05_rt_s…"). The Summary uses a middle ellipsis ("Sample_…io_fail", "Sample…_shift"). See `extra/12_narrow_unlab__u1024.png`, `1500L/35`, `150L/35`.
   - Fix: use the middle ellipsis in both. The distinguishing suffix sits at the end of these names.
   - Gain: F4 +0.05, F7 +0.05.

8. **Settings has seven pages for about ten controls.**
   - Where: Extraction, Integration, Peak validation and Natural abundance each hold one control, above a 300 px blank and a disabled Save/Revert (`16_settings_page2`, `_page3`, `_page5`, `_page6`).
   - This is clean, and it follows the user's per-topic request. It does mean four clicks to survey four numbers.
   - Fix (optional): group the single-control pages into one "Processing" page with section titles. Keep Appearance, Internal standard, Qualifier ratios and Deconvolution separate.
   - Gain: F2 +0.05, F6 +0.05.

## Re-rating comparison

**My round-10 issues, status:**
1. **Samples section scatters at 2560: fixed.**
   - The section spans y 401–731 with the filter 30 px under its heading. The Peak window follows at 743 (`extra/11_samples_gap__samples_open.png`, `2560L/31`).
2. **Sidebar clipped at laptop widths with the Summary open: fixed.**
   - At 1024 the splitter reads `[279, 494, 243]`, and `clipped sidebar []` for both datasets.
   - "Compound list" and the tR window field show in full (`extra/09_narrow__1024.png`).
3. **Out-of-window labelled peaks unflagged: still open** (declined).
4. **Blank first docs page on CI macOS: partly fixed.** Light renders. Dark is still blank (`MD/17`).
5. **Dark washes for Below threshold and Marked bad too close: fixed.** Rose, lavender and tan are distinct (`2560D/27`, `WD/27`, `MD/27`).
6. **Header crowding and wrap: mostly fixed.** The Docs icon is gone, and the header is one row at 1280. It still wraps at 1024 with the Summary open (issue 4).
7. **Qualifier QC key shown twice: fixed.** The header key hides while the Summary is open (`crops/24_header.png`), and returns when it is closed (`ML/24`).
8. **Draft captions phrased differently: fixed.** Both read "All 30 shown · not applied" (`integration_window_widget.py:772-774`).
9. **Popup titles mix case: fixed.** 'Label incorporation — MANIC', 'Peak area — MANIC'.
10. **Abundance popup repeats "Peak area": fixed.** The subtitle is "30 samples".
11. **Unlabelled Summary two-thirds empty: fixed.** The Identity rows grow (`crops/24_summary.png`).
12. **Checklist scrolls its title away at 150%: fixed.** The dialog is 1020×1008 and the title stays (`150L/04_*_steps`, `150D/23_*_steps`).

**Improved beyond the list:**
- self-sizing tiles: 30 at 303×249 with no scroll at 2560;
- Settings by topic, with an unsaved dot and the "Also unsaved" link when you switch pages;
- Appearance that applies at once, with no Save/Revert;
- the rebuild flow refuses unsupported input up front ("Needs a labelled compound list…", "Needs a workbook with a MANIC Raw Values sheet.");
- Summary tooltips with a background;
- a collapsed "Baseline, tR window · On · 0.22 min" row when the sidebar is short (`ML/31`).

**Regressed:** nothing I could find. The partial divider (issue 2) may be older, but it is visible on the primary screen now that the sidebar hugs its content.

**Lost functionality: none against `main`.**
- Every action label on `origin/main` exists at 86a53c3, mostly in title case now. "View Detailed..." became "Inspect Sample...", and "Select All" became "Select All Plots".
- The menus read live:
  - File: Load, Add Compound, Load Raw Data, Open Recent, Export and Import Session, New Analysis Session, Clear Session, Export Data, Process External Data, Settings, Quit;
  - View: Show Sidebar, Show Summary, Shared Y-Scale, Scale to Selected Peak (labelled only), Find Compound, Previous and Next Compound, Sample List;
  - Review: Inspect, Select All Plots, Deselect All, Show Only Selected, Show All, Next and Previous Flagged, Accept, Mark Bad or Clear Bad Mark, Curve Fit, Baseline Correction;
  - Help: Documentation, Check Data Setup, Check for Updates, About.
- Compact and Comfortable were removed at the user's request. They never existed on `main` (`git grep` finds no density control there), and the self-sizing grid replaces them.
- The header Docs icon is gone, but F1, Help › Documentation and the start-screen link remain.

**What still stands between each factor and a 10:**
- **F1:** the divider (issue 2), and the status-bar sentence as visual noise (issue 6).
- **F2:** the 1024 header wrap and cramped grid (issue 4); optionally, the Settings page count (issue 8).
- **F3:** the out-of-window flag.
- **F4:** the divider, the "amber" copy, and the two ellipsis styles.
- **F5:** the out-of-window flag, the CI macOS dark docs blank, and no confirmation on Save.
- **F6:** yielding the Summary one step earlier on laptops.
- **F7:** the out-of-window flag.
- **F8:** the divider and the docs blank.
- **F9:** the permanent deconvolution sentence and the "amber" copy.

**Per-platform limits:**
- **2560:**
  - real captures this round;
  - my own drive was offscreen at the same geometry;
  - not checked: the native title bar, the macOS menu bar, hover.
- **Windows:**
  - CI at 100% only, clean in both schemes;
  - not checked: 125% and 150%, hover.
- **macOS:**
  - CI and local real captures;
  - not checked: the native menu bar and an OS scheme switch;
  - the CI dark docs page is blank.
- **150%:** the 1280×800 window renders cleanly in both schemes. The 1707×940 logical screen was not driven interactively.

```json
{"F1": 9, "F2": 9, "F3": 9, "F4": 9, "F5": 9, "F6": 9, "F7": 9, "F8": 9, "F9": 9, "overall": 9.0}
```
