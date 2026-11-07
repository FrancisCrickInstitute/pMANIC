# MANIC UI/UX review, round 14 (re-rating at b99e2e22), reviewer: opus

## Evidence

**Screenshots.** I viewed all 558 PNGs in the nine round-14 folders through contact sheets (`sheets/`: 3×3 tiles, 1000 px for the two 2560 folders and 800 px for the rest). At full size I cropped the 2560 light unlabelled Summary and header (`crops/L24_summary.png`, `crops/L24_header.png`, `crops/L26_top.png`) and the 150% Summary before and after a selection (`crops/150_24v25.png`). Short names:
- `2560L/`, `2560D/`: linux 2560×1410, light and dark (the primary target).
- `WL/`, `WD/`: Windows CI. `ML/`, `MD/`: macOS CI.
- `1500L/`: 1500×940 light. `1024D/`: 1024×720 dark. `150D/`: 150% scaling, 1280×800 window, dark.

**My own drive** (`drive14.py` → `body14.py`, offscreen with `screen2560.json`; log in `extra/log.txt`, shots in `extra/`; it reached DONE):
- **Labelled, 2560.** Fresh load. A on an unflagged plot, with all 30 selected, and with none selected. N ×3, A, then B. A Peak window draft, applied with Return. tR window 0.3 → Apply window ("Regenerated 30 EICs", 2.0 s). A Peak validation edit → Save ("Saved" for about 3 s). All seven Settings pages. Deconvolution level 4 → 3, which brought up the status indicator. Both Summary popups, the detailed view, and a full export (51.7 s, five sheets).
- **Resize** 2560 → 1920 → 1700 → 1500 → 1280 → 1100 → 1024 → 2560. The folded Scale button, and every menu read live.
- **Unlabelled, 2560.** All 8 compounds, with the QC key text and Identity footer logged for each. Glycine with the Summary open, closed and reopened. 1500 and 1024. The Identity popup, the detailed view, export (5.5 s, three sheets), and a fit override.
- **Round-14 probes.**
  - Summary row hover and click in all three charts, on bars, on names and on empty or zero rows, in light and dark.
  - A refused A, then B.
  - The Peak window heading, open and closed.
  - Start-screen recents: one long name in two folders.
- **`probe14.py`.** I renamed two compounds in copies of the test data: a 54-character Alanine and a 56-character internal standard (the CDFs are symlinks).
  - Checklist hovers.
  - Settings Deconvolution and Qualifier ratios headings.
  - The Internal standard page at 720 and 640 px.
  - The sidebar status row.
  - Hover on every Peak area name and bar.
- **Code:** the diff 72561139..b99e2e22 (12 commits, 15 UI files) and `origin/main...b99e2e22` for lost functionality.

**Harness note, not an app bug:** in the main drive, the name hover ran right after a bar hover with the same tooltip text, so it read back as hidden. In `probe14`, with the tooltip hidden between hovers, every name answered.

**Not run:**
- Real OS hover timing, the native macOS menu bar, Windows at 125% and 150%, and a real OS scheme switch.
- Delete and Recover, session import, and the quit prompt (its code is unchanged since round 13).
- The per-sample fit table with long names: my probe's fit-override step failed to find the Gaussian action in the unlabelled Review menu, so that table is judged from code only (`settings_window.py:615-619`).

## Verdict

The app works end to end on both datasets, and all four of my round-13 issues are fixed:
- **The 150% Summary.** Names keep one size and one shortening before and after a selection (`150D/24` vs `150D/25`, `crops/150_24v25.png`: "Sampl…_fail" at the same size in both).
- **The qualifier QC key.** It lists only the states the compound shows: Alanine and Citrate show three, Lactate and Serine show two. It is gone on Glycine, where the note explains the grey traces (`crops/L26_top.png`; log `Glycine: qc_key vis False`).
- **Refused toasts.** A refused A ("MM_01 is not Below threshold") clears when B goes through (log: `after B … toasts []`).
- **The Identity footer.** It is now a tally ("Qualifier cells ✓ 16 ✕ 2 ? 4") beside the one colour key.

The other round-14 changes also hold up in the running app:
- Every Peak area and Label incorporation row answers hover and click by row, including zero rows and the "—" rows ("Bio_027 · No ratio: …"; a click on that empty row selected Bio_027).
- Long compound names elide in Settings and the checklist, with the full name on hover.
- The Internal standard row keeps Choose… in view at 640 px.
- Two recents with one name show which folder each is in ("~/code/ui…6_batch_A" and "…_batch_B").
- The Peak window heading reads "minutes" while open and "tR 5 · Baseline on" while closed.

At 2560 both schemes look calm and are easy to read. The Windows and macOS CI shots are clean in light and dark. What remains is two small inconsistencies in how cut names behave, plus a minor copy nit. Nothing on `main` is missing.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 10 | The 150% defect is gone: one name size and one elision in both states (`crops/150_24v25.png`). The tokens hold across all nine folders. Validated checkmarks now read on their wash in both schemes (`2560L/24`, `2560D/24`; `colors.py:115-116`). The Settings, checklist and popup layouts are unchanged and tidy (`*/16_*`, `*/15_*`, `*/33_*`). |
| F2 | Layout and hierarchy | 10 | At 2560: 30 tiles of 303×251 and 11 tiles of 458×424, with no scroll. Resizing lays out like a fresh launch (1920 → 5 columns, 1500 → 5 columns with no scroll, 1100 → the Summary yields). The same in round 13, and verified again. |
| F3 | Onboarding and workflow clarity | 10 | One action per empty state (`*/02`, `*/03`). The checklist has the pattern how-to (`*/04_*_steps`). Quick Start has a key table (`*/17_…DocumentationViewer.png`). A and B explain refusals. The popup hint now says what the keys do: "↑↓ to choose · Return or click to select its plot" (`*/13`, `*/14`). |
| F4 | Consistency and polish | 9 | One rule now governs Summary name size and elision, and Settings and checklist names elide in the middle with hover. Below 10: (a) the Identity chart's names answer hover with a generic "Click a row to select its plot…" tooltip, while the Peak area names beside them give the name and value (`targeted_qc_widget.py:80-89`). (b) The sidebar's Internal standard value cuts at the end with no hover ("Lactate_2TMS_inte…"), while the compound list right under it cuts in the middle (`probe/02_long_lab__is_set.png`, `crops/is_sidebar.png`; `sidebar_widgets.py:209`). |
| F5 | Feedback and state | 10 | Verified live: refusal toasts clear on success; "Regenerated 30 EICs"; "Saved" then clear; "Exported export.xlsx" with a progress dialog; the draft caption "Bio_002 · not applied"; the deconvolution indicator; the Peak window heading names its unit while open and its state while closed. |
| F6 | Efficiency and flexibility | 10 | Every shortcut is intact (menus read live: Ctrl+O/Shift+O/I/E, Ctrl+Alt+S/R, Ctrl+Shift+Y/P/L/B, Ctrl+F, Ctrl+[ ], Return, Ctrl+A, Esc, N/Shift+N, A, B, F1). A Summary row is now a click target across its whole width, including zero and empty rows, so a missing bar is one click from its plot. |
| F7 | Data visualisation | 10 | The QC key names only the colours on screen, and none for a compound with no assessed qualifier (`2560L/26`, `WD/26`, `MD/26`; `graphs.py:106-124`). The Summary charts keep their labels at 150%. Every Peak area row shows a value, a "0", "<0.01" or a "—", and says why on hover. The detailed view tags the qualifier states in its legend (`*/34`). |
| F8 | Modern feel | 10 | On the 27" screen and on both CI platforms, it feels like current, considered software. Panels yield and return, the theme switches live, review is one key at a time and explains itself, rows answer hover and click, and Settings is compact and confirms a save. |
| F9 | Taste (not AI slop) | 10 | The round-13 tells are gone: the key appears once, it never lists states that cannot occur, and the footer is a terse tally. Copy stays short and specific: "minutes", "Re-extracts all 30 shown samples", "No ratio: this sample has no integrated peak area for this compound." The one item left is a clarity nit, not a template tell (issue 3). I no longer count the two-way Shared Y / Scale to peak segmented control against it: it is the native idiom for a two-state mode, not decoration. |

Overall: (10+10+10+9+10+10+10+10+10)/9 = **9.9** (round 13: 9.6).

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| Sidebar and Summary toggles in the header, the View menu, and Ctrl+Alt+S/R | `*/05` | Yes: a menu command, a shortcut, and a button beside its panel. |
| Shared Y and Scale to peak in the header (or the folded Scale button) and the View menu | `*/05`, `extra/09_lab_scale_menu__scale_shared.png` | Yes: a menu command plus a control at the grid. |
| The qualifier QC key in the header, with a tally in the Identity footer | `2560L/24`, `150D/24` | Yes now: the key names the colours once, and the footer only counts marks. |
| Identity header "1 sample failed" and footer "✕ 2" | `2560L/24`, `crops/L24_summary.png` | Partly. Both count the failure, in different units (samples vs cells), 500 px apart. Issue 3. |
| The qualifier gap note in the grid header or the Identity panel | `extra/12_unl_glycine__closed.png` vs `__open` | Yes: it has one home at a time (`qc_note` hidden while the Summary is open). |
| The internal standard in the sidebar, the checklist and Settings | `*/04_*`, `*/16_settings_page4` | Yes: each is a place to act on it. |
| The deconvolution indicator in the status bar and Settings | log `indicator Deconvolution level 3 · …` | Yes: it appears only away from the defaults. |
| The fit override on the tile caption and the detailed-view heading | round-13 `probe3` (code unchanged) | Yes: the detailed view is a separate window. |

## Top issues, ranked by user impact

Only three issues survived verification. All are small, and none touches the core workflow.

1. **The Identity chart's names do not answer hover the way the other Summary charts do.**
   - Where: the Identity panel at laptop widths and 150%, where the names elide ("Sampl…_fail", `150D/24`, `1500L/24`).
   - Peak area and Label incorporation now attach `SummaryRows` with a `tip`, so hovering a name or bar gives the full sample name and its value (`probe/log.txt`: 11 of 11 names answered). Identity attaches `SummaryRows` without a tip (`targeted_qc_widget.py:85-89`) and keeps a static view tooltip (`:80`). Hovering a cut name there shows "Click a row to select its plot; double-click to enlarge." instead of the name. The full name appears only when you hover a cell.
   - Fix: pass a `tip(row)` that returns the sample name and its qualifier states. This is the same text as the cell tooltip, without the per-cell detail. Then drop the static view tooltip, since the popup's own hint already teaches the click.
   - Gain: F4 +0.3, F7 +0.05.

2. **The sidebar's Internal standard value cuts at the end with no way to read it whole.**
   - Where: `probe/02_long_lab__is_set.png` (`crops/is_sidebar.png`). With a 56-character standard, the row reads "Lactate_2TMS_inte…". The compound list directly below cuts the same name in the middle ("Lactate_2TMS_int…_batch_2026_long"), and Settings does the same with a full-name tooltip.
   - Code: `sidebar_widgets.py:209` builds the value as `ElidedLabel()` with the default `ElideRight` and no hover.
   - Fix: `ElidedLabel(mode=Qt.TextElideMode.ElideMiddle, hover=True)` for the status value, which matches `HeaderName` and the compound list.
   - Gain: F4 +0.2. Real standard names are rarely this long, so the impact is small.

3. **The Identity panel counts one failure twice, in two units.**
   - Where: `2560L/24`, `150D/24`. The header reads "1 sample failed" (`targeted_qc_widget.py:170`), and the footer tally reads "✕ 2" (cells) under the same chart.
   - A reader can take "1" and "2" as a contradiction until they notice the units.
   - Fix: let the header carry the sample count and the footer the cell counts, with the unit on the mark ("✕ 2 cells"). Or drop the header detail when the tally is visible.
   - Gain: F9 +0.05, F3 +0.05.

Below the cut, judged not worth a slot: start-screen recent names are cut to 220 px even when the column could fit more (`start_panel.py:217`). The full path is on hover, and the folder now keeps its distinguishing tail, so this is a deliberate trade.

## Re-rating comparison

**My round-13 issues, status:**
1. **150% Summary names changed size and clipped on selection: fixed.** `150D/24` and `150D/25` show identical name columns ("Sampl…_fail", "Sampl…shift") at one size with ellipses. The labelled 150% shots match (`150D/05` vs `150D/06`).
2. **The QC key on unassessed compounds: fixed.** It is hidden on Glycine (`2560L/26`, `WD/26`, `MD/26`, log). On other compounds it lists only the present states (log: Lactate "Validated, Not assessed"; Alanine three states).
3. **A stale refusal toast survived B: fixed.** Verified on Bio_001 (labelled) and MM_01 (unlabelled): the toast is gone after B (`extra/17_r14_unl__after_B.png`).
4. **The doubled QC key: fixed.** The footer is now a swatch-free tally (`crops/L24_summary.png`).

**Improved beyond the list:**
- Summary rows answer hover and click across their full width, including zero and "—" rows.
- Validated checkmarks are readable on their wash.
- Long names are handled in the Settings headings, the IS row and the checklist (with hover).
- Same-named recents can be told apart.
- The popup hint and the enlarge tooltip are shorter and say what happens.

**Regressed:** nothing I could find. Issue 1 above is an inconsistency that this round's `SummaryRows` change exposed, not a regression: the Identity names had the same static tooltip before.

**Lost functionality: none against `origin/main`.**
- The menus read live match round 13 exactly:
  - File (12 actions)
  - View (Show Sidebar, Show Summary, Shared Y-Scale, Scale to Selected Peak, Find Compound, Previous and Next Compound, Sample List)
  - Review (Inspect, Select All Plots, Deselect All, Show Only Selected, Show All, Next and Previous Flagged, Accept, Mark Bad, Curve Fit with five choices, Baseline Correction)
  - Help (Documentation, Check Data Setup, Check for Updates, About)
- The round-14 diff adds no actions and removes none. It replaces `bar_set.clicked` and `bar_set.hovered` with row-wide handlers that cover the same and more (`chart_style.py:180-209`). Identity cell tooltips are kept (`targeted_qc_widget.py:262`).
- The ratio popup's "↑↓ to read" hint was folded into the generic "↑↓ to choose · Return or click to select its plot". The keys still work.
- Both exports completed with the same sheets as in round 13.

**What still stands between each factor and a 10:**
- **F4:** issues 1 and 2.
- **Every other factor:** nothing material. Issue 3 is a copy nit.

**Per-platform limits:**
- **2560:** offscreen renders plus my drive at that geometry. Not checked: the native title bar, the macOS menu bar, and real hover timing.
- **Windows:** the CI shots are clean in both schemes (`WL/*`, `WD/*`). 125% and 150% are not verified on real Windows; the linux 150% defect from round 13 is fixed.
- **macOS:** the CI shots are clean in both schemes, including the docs in dark (`MD/17*`). Not checked: the native menu bar and an OS scheme switch.
- **150%:** dark only (`150D/*`), and clean.

```json
{"F1": 10, "F2": 10, "F3": 10, "F4": 9, "F5": 10, "F6": 10, "F7": 10, "F8": 10, "F9": 10, "overall": 9.9}
```
