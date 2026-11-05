# MANIC UI/UX review, round 5 (re-rating at 6ec219c), reviewer: opus

## Evidence

**Screenshots.** I viewed all 568 PNGs in the eight round-5 folders, first as contact sheets (`sheets/`) and then at full size where a detail mattered. The sheets scale every image to the same width, so a small dialog looks oversized there. I checked real pixel sizes with `sips` before judging any type size. Short names used below:
- `WL/` and `WD/`: Windows light and dark (CI, 1024×720).
- `ML/` and `MD/`: CI macOS light and dark (1024×681).
- `mL/` and `mD/`: local Mac light and dark (1512×949).
- `150L/` and `150D/`: the two 150% folders (1008×633 logical).

**My own drives.** These ran on this Mac against `pMANIC-review-r5` at 6ec219c. Scripts and output are in this folder.
- `drive.py`, writing `extra/` and `extra/log.txt`. On labelled data it:
  - loaded the data and read the status bar, sidebar and canvas header;
  - set Palatinose as the internal standard, which gave Bio_004 a "Below threshold" badge;
  - selected 3 plots including Bio_004, read the Review menu, accepted, read the menu again, then marked Bio_006 bad;
  - changed the left offset for 2 selected samples, applied it, deselected, switched compound and switched back;
  - changed Settings › Peak Validation to 0.05 and saved;
  - opened the sample-list and compound-list context menus;
  - opened the Display and Summary tabs;
  - switched Compact and Comfortable density;
  - resized to 1280×720 and 1024×640;
  - pressed → ↓ Space;
  - opened About;
  - went through the unlabelled dataset's Summary tab for all 8 compounds.
- `export_check.py`: a real export in both modes with the file dialogs stubbed.
- `drag.py`: a simulated drag of a .csv and of a non-list file over the empty start screen.
- `repro.py`: measured idle CPU and drove the sample-list menu in isolation.

**Not run.** Real hover and tooltips, native macOS menu-bar rendering, Windows at 125% and 150%, a real OS-driven scheme switch, the documentation failure state, Delete Sample, and Reset with its confirmation.

## Verdict

**Functionally, the app works end to end, and every check I ran passed:**
- **Fresh load:** all three sidebar rows tick. The canvas header reads "Pyruvate tR 7.09". The deconvolution status shows at once, so round 4's blank-status bug is fixed (`extra/log.txt`).
- **Accept:** Accept acts on the eligible plot. The menu then reads "Clear Acceptance" and an "Accepted" pill appears.
- **Mark bad:** Mark Bad gives a red tint and a "Marked bad" pill. The menu turns to "Clear Bad Mark" and greys out Accept.
- **Peak window:** a two-sample Apply changes those samples only. With mixed values the field shows "0.08 - 0.1", and the change survives a compound switch.
- **Settings:** saving works, and both buttons disable after the save.
- **Context menus:** the sample-list menu opens (round 4's crash is fixed) and offers Delete, Show Only, Hide, Show All and Recover. The compound-list menu has all five entries.
- **Export:**
  - Export Options now comes before the save location.
  - Labelled export wrote 5 sheets in 20 s.
  - Unlabelled export wrote Raw Values, Abundances and Qualifier QC in 7 s.
- **Drop zone:** it accepts a .csv and refuses another file type (`extra/drag_dark_csv.png`).

**What changed the most:**
- The start screen is no longer the template. It shows one line, one button and one footer, and the dashed outline appears only during a drag.
- The count repeats and the status-bar recap are gone.
- Compact density now visibly changes the grid: 6 columns against 5 at 1512 wide (`extra/09_compact.png`).
- Peak-window Reset and Apply are pinned on short windows.
- About is a tidy 360×214 dialog (`WL/21`).
- Documentation renders in every capture.
- QC badges sit in one fixed row on both platforms.

**What remains is mostly taste and the last 10%:**
- The isotopologue colours are still matplotlib's default palette.
- Serine's grid turns completely amber because one qualifier has no expected ratio.
- The grey QC state has three names.
- The review loop has no keyboard shortcut for Accept or Mark.
- Settings still explains in paragraphs behind a "Save this page" model.
- On short windows the field above the pinned Apply row is sliced.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 8 | One token system holds on Windows, macOS, light, dark and 150% (`WL/05`, `WD/05`, `MD/24`, `150D/25`). About is now proportionate (`WL/21`, 360×214). Verdict tints read in both schemes (`extra/02_accept_mark.png`). Held back by: the stock tab10 isotopologue palette and teal bars (`colors.py:25`, `colors.py:29-39`; `WL/13`, `WL/14`); a whole grid tinted amber for a compound-level gap (`extra/15_unlab_summary__c3.png`); a text field sliced under the pinned button row (`extra/12_w1024x640.png`, `150D/33`). |
| F2 | Layout and hierarchy | 8 | The Reset/Apply row is pinned and the lists keep their rows at 1024×640 (`extra/12_w1024x640.png`). Each count now appears once (`WL/05`: sidebar "30 · all shown", header only "3 of 30 selected" when a selection exists). The detailed view gives the EIC panel the most height (`WL/11`). Remaining: the Right offset field is cut in half above the pinned row (`extra/12`); "Baseline correction" is sliced at the 150% edge (`150L/05`); the Mass Spectrum panel is below the fold at 1024×720 (`WL/11`); the Display tab is two checkboxes in a tall empty panel (`extra/07_tabs__Display.png`). |
| F3 | Onboarding and workflow clarity | 9 | The empty canvas asks for exactly one thing ("Drop a compound list here", one button), then the next thing ("Drop the folder of CDF files here", `WL/03`). The checklist is a title, two short sections, Open File and Show in Folder, plus three steps behind a disclosure (`WL/04_…_steps`). Settings › Internal Standard now has the combo itself (`WL/16_…page4`). A 10 needs: the mode chooser's two paragraphs cut to one line each (`01_mode_chooser`), and the footer instruction "Saved session: load its data, then File → Import Session" (`start_panel.py:94`) shown as a link rather than a sentence. |
| F4 | Consistency and polish | 9 | The two review menus match and show Return, Ctrl+A, Esc and Ctrl+Shift+B on Windows (`WL/09_*menu`, `WL/10_*menu`). Dialogs share one sentence-case scale; at real size Settings body ≈ Add Compound body. QC badges sit in the same row on Windows and macOS (`WD/24`, `MD/24`). The internal-standard menu check uses the app's SVG. "No internal standard" is one string, except the menu's title case. Gaps to 10: the grey QC state is named "No verdict" (`graphs.py:258`), "Not assessed" (`identity_chart.py:54`) and "(not assessed)"; Settings is the only dialog with no primary button (`settings_window.py:878-884`); the captured macOS Review menu shows no shortcut column while Windows does (`mL/10_review_menu__menu` against `WL/10_…menu`; the native menu bar is unverified). |
| F5 | Feedback and state | 8 | Verified live: the Accepted, Marked bad, Below threshold, QC fail, QC partial and Not detected pills; the menu labels that flip; "Applies to Bio_006" in accent; the "0.08 - 0.1" mixed-value display; Settings buttons that disable on save; the "Imported 2850 EICs" toast; the deconvolution status present right after load; docs loading states. Held back by: Serine shows "QC partial" plus an amber tint on all 11 tiles because qualifier 2 has no expected ratio in the method (`plot_tile.py:62`, `extra/15_…c3.png`), which hides sample-level failures; export success is a modal listing the full path and every sheet (`main_window.py:3034-3036`) rather than a toast with Show in Folder. |
| F6 | Efficiency and flexibility | 9 | Compact is real: 6 columns against 5, with a 130×95 minimum tile (`plot_tile.py`, `extra/09_compact.png`). → ↓ Space moved focus and added Bio_007 (`extra/log.txt`). Find, Next and Previous Compound exist. Ctrl+A, Esc and Ctrl+Shift+B work. The Apply row is pinned. What stands between this and a 10: Accept Peak, Mark Peak as Bad and Peak-window Apply have no shortcuts (`main_window.py:562`, `:569`), so the core review loop needs the mouse or a menu; and the field sliced above the pinned row. |
| F7 | Data visualisation | 8 | The detailed view is now themed, with a tall EIC panel, readable roughly 10 px ticks on Windows and an M+0…M+3 bracket on the spectrum (`WL/11`, `WD/11`, `MD/32`). The Identity summary is a clear qualifier grid with counts (`extra/15_…c3.png`). Popups use "—" and "<0.01" (`WD/13`). Remaining: the isotopologue colours are matplotlib tab10 with no order cue (`colors.py:29-39`); the stock teal abundance bars (`colors.py:25`); the spectrum is below the fold at laptop size (`WL/11`); the footer adds debug counts, "48 EIC points · 2881 TIC points · 17 MS peaks" (`detailed_plot_dialog.py:828`). |
| F8 | Modern feel | 8 | The drop-zone start, segmented density control, pills, toasts, pinned footers and live scheme switch that keeps the selection (`WD/08`) all read as considered software. The charts still carry the matplotlib look (palette, tick styling), and Settings uses an older per-page Save/Discard model. Both keep this from feeling like a Pro app. |
| F9 | Taste (not AI slop) | 7 | The template start screen is gone, uppercase labels are limited to the sidebar, the checklist and Settings copy is much shorter, and most duplications are removed. What is left is generic: the stock palette, paragraph help in Settings (`settings_window.py:190`), the identical "QC partial" badge on every tile, the mode chooser's choice-card layout with a pre-filled blue first option, the diagnostic footer and "Save this page". That is the "considered and clean, with a few generic patterns left" anchor. |

Overall: (8+8+9+9+8+9+8+8+7)/9 = 8.22 → **8.2** (round 4: 7.8).

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| "QC partial" pill plus amber tint on all 11 tiles when the cause is compound-level (qualifier 2 has no expected ratio) | `extra/15_unlab_summary__c3.png`; `plot_tile.py:62` | No. State it once in the header and keep the per-tile tint for sample-level outcomes. |
| Grey QC state with three names: "No verdict" in the header legend, "Not assessed" in the Identity summary, "(not assessed)" in the detailed legend | `WL/24` header, `extra/15_…c3`, `WD/32`; `graphs.py:258`, `identity_chart.py:54` | No: one state, one word. |
| Two QC legends at once: the header's "Qualifier colour = QC ● Validated ● Failed ● No verdict" and the sidebar's "Qualifier cells ✓ Validated 10 × Failed 0 ? Not assessed 12" | `extra/15_…c3` | Partly. The sidebar version carries counts; the header could drop its legend once the Summary tab is open. |
| Internal standard is set in four places: the sidebar menu, the compound context menu, the checklist and Settings › Internal Standard | `30_*menu`, `extra/06_compound_menu__menu.png`, `04_*Dialog`, `16_…page4` | Partly. The context menu is a shortcut and the checklist is a one-time flow. The Settings page duplicates the sidebar menu; the reference peak could live in that menu. |
| "Applies to all shown samples" (the default scope) above the offsets, and "Re-extracts all 30 shown samples" under tR window | `WL/05`; `integration_window_widget.py:623`, `:629` | The second is justified: it is a different action with a different scope. The first restates the default; show it only when a selection narrows the scope, as "Applies to Bio_001" already does. |
| Sample count in the Samples header and the re-extract caption | `WL/05` | Justified: one is filter state, the other sits where the user acts. |
| Sidebar "Compound list · Not loaded" alongside the canvas "Drop a compound list here" | `WL/02` | Justified: one is persistent status, the other is the call to action. |
| Settings paragraphs: Peak Validation's three lines plus an example line; the Internal Standard paragraph; Deconvolution's one line plus three "?" buttons | `WL/16_…page1`, `…page4`, `…page5`; `settings_window.py:190` | Mostly no. Keep the example; drop the paragraph or move it to hover help. |
| Stock tab10 isotopologue palette and teal bars | `colors.py:25`, `:29-39`; `WL/13`, `WL/14` | Generic. |
| Diagnostic footer "48 EIC points · 2881 TIC points · 17 MS peaks" | `WL/11`; `detailed_plot_dialog.py:828` | No: developer data. |
| Mode chooser: two large choice buttons, the first filled blue, each with a two-line paragraph | `01_mode_chooser` (all folders) | A template choice card. A neutral pair with one line each would do. |
| "Save this page" and "Discard changes", both grey | `WL/16_*`; `settings_window.py:878-884` | Implementation wording. |
| The Review menu and plot context menu carry the same commands | `09`, `10` | Yes: a menu plus a context menu. |

## Top 12 issues, ranked by user impact

1. **A compound-level QC gap paints the whole grid amber.**
   - Where: unlabelled Serine (`extra/15_unlab_summary__c3.png`). Qualifier 2 has no expected ratio, so all 11 tiles carry "QC partial" and the amber tint. The badge set is `plot_tile.py:62`.
   - Why it matters: the one sample that really fails, Sample_04_ratio_fail, no longer stands out.
   - Fix: when every sample's "partial" has the same compound-level cause, show one header note ("Qualifier 2 has no expected ratio · Settings › Qualifier Ratios") and draw no tile tint or badge for it. Keep tints for per-sample outcomes.
   - Gain: F5 +0.5, F9 +0.25, F1 +0.1.

2. **The review loop has no keyboard path for verdicts.**
   - Where: Accept Peak (Below Threshold), Mark Peak as Bad, Clear Acceptance and Clear Bad Mark have no shortcuts (`main_window.py:562`, `:569`; the Review menu shows none in `WL/10_…menu`). Peak-window Apply has none either.
   - Fix:
     - single-key grid shortcuts scoped to the grid, as Inspect already is (`setShortcutContext(Qt.WidgetShortcut)` near `main_window.py:536`): A to accept or clear, B to mark bad or clear;
     - ⌘↩ / Ctrl+Enter for Apply in the Peak window;
     - show them in both menus.
   - Gain: F6 +0.5, F8 +0.1.

3. **On short windows the field above the pinned Apply row is sliced in half.**
   - Where:
     - `extra/12_w1024x640.png`: Right offset is a sliver above Reset/Apply.
     - `150D/33`: tR is cut through its text.
     - `150L/05`: "Baseline correction" is cut at the bottom edge.
   - Fix: the pinned-row helper (`left_toolbar.py`, the new "Keeps a row of a scroll area's content whole" class) should snap the scroll body to whole rows, or fade the last partial row. Better still, pin the Apply row together with the three offset fields as one group, since they are what Apply acts on.
   - Gain: F2 +0.25, F1 +0.1, F6 +0.1.

4. **The grey QC state has three names.**
   - Where: "No verdict" (`graphs.py:258`, header legend), "Not assessed" (`identity_chart.py:54`, Summary legend), "(not assessed)" (detailed view legend), and the popup chips "no expected ratio" and "not in the method".
   - Fix: one umbrella word, "Not assessed", everywhere. Keep the specific reason only on the Identity popup chips.
   - Gain: F4 +0.25, F9 +0.1.

5. **The isotopologue palette is matplotlib tab10, and the bars are stock teal.**
   - Where: `colors.py:29-39`, `colors.py:25`; every grid, `WL/13`, `WL/14`.
   - Why it matters: M+0…M+n are ordered, but the hues carry no order, and the default palette is the clearest remaining "science tool" tell.
   - Fix: an ordered ramp tuned in both schemes (for example deep blue for M+0 stepping through to warm for the heaviest M+n), with the existing dark-mode contrast retune (`colors.py:49-59`). Give abundance bars the neutral data ink plus the accent.
   - Gain: F7 +0.5, F9 +0.25, F1 +0.25.

6. **Settings still explains in paragraphs, behind a per-page save.**
   - Where: Peak Validation has a three-line paragraph plus an example (`settings_window.py:190`, `WL/16_…page1`). Internal Standard has a paragraph over two fields (`…page4`). Footer buttons are "Save this page" and "Discard changes", both secondary (`settings_window.py:878-884`).
   - Fix:
     - one line per page, with the rest as hover help (the "?" buttons already exist on Deconvolution);
     - rename the buttons "Save" and "Revert";
     - make Save primary when the page is dirty.
   - Gain: F9 +0.25, F4 +0.1, F8 +0.1.

7. **The detailed view hides the spectrum and shows debug data.**
   - Where: at 1024×720 the Mass Spectrum is just a title and a sliver below the fold (`WL/11`, `MD/11`). The footer reads "48 EIC points · 2881 TIC points · 17 MS peaks" (`detailed_plot_dialog.py:828`).
   - Fix:
     - On short screens, put the TIC and spectrum on tabs or a two-column row under the EIC, so nothing needs scrolling.
     - Footer: tR, observed apex and the active integration window only.
   - Gain: F7 +0.25, F2 +0.1.

8. **Export success is an old-style modal wall.**
   - Where: `main_window.py:3034-3036` prints the full path, the sheet count and every sheet name in a QMessageBox (verified live in `export.out`).
   - Fix: a status toast, "Exported manic_data_export.xlsx · Show in Folder", using the existing toast (`main_window.py:234`).
   - Gain: F5 +0.1, F8 +0.1, F9 +0.1.

9. **The internal standard has four editors.**
   - Where: the sidebar menu (`30`), the compound context menu (`extra/06_compound_menu__menu.png`), the checklist (`04`) and Settings › Internal Standard (`16_…page4`). The last also holds the reference peak.
   - Fix: keep the sidebar menu, the context menu and the checklist. Move "Reference peak" into the sidebar menu as a submenu and delete the Settings page.
   - Gain: F9 +0.1, F2 +0.1.

10. **The mode chooser is a choice-card template.**
    - Where: `01_mode_chooser__AnalysisModeDialog` in every folder. Two big buttons, the first pre-filled primary blue, each followed by a two-line paragraph.
    - Fix: two equal options with one-line captions ("Labelled · isotope tracing, M+0…M+n", "Unlabelled · quantifier and qualifier ions"). Don't pre-fill one as primary unless it is a remembered choice.
    - Gain: F9 +0.1, F3 +0.1.

11. **The default scope caption restates the default.**
    - Where: "Applies to all shown samples" (`integration_window_widget.py:623`) sits above the offsets whenever nothing is selected (`WL/05`).
    - Fix: no caption in the default state. Keep the accent caption ("Applies to Bio_006", "Applies to 3 selected samples") when a selection narrows the scope.
    - Gain: F9 +0.1, F2 +0.1.

12. **The Display tab is nearly empty, and the macOS Review menu lost its shortcut column.**
    - Display (`extra/07_tabs__Display.png`) is two checkboxes in a full-height panel. Move them to the View menu, or onto the header next to Compact/Comfortable, and drop the tab.
    - The captured macOS Review menu shows no shortcuts (`mL/10_review_menu__menu`, `MD/10_…menu`), while the macOS context menu shows ↵ ⌘A ⎋ (`MD/09_…menu`) and Windows shows them in both. Check that the native menu bar shows them; if not, set the shortcuts on the shared actions rather than per menu.
    - Gain: F4 +0.1, F2 +0.1.

## Re-rating comparison

**Round-4 issues, status:**
1. **Template start screen: fixed.** One line, one button and a footer of links; the dashed outline and tint appear only during a drag, and a non-list file is refused (`WL/02`, `WL/03`, `extra/drag_dark_csv.png`). The footer still has one instruction sentence (issue 10's neighbour, `start_panel.py:94`).
2. **Repeated counts and compound name: fixed.**
   - The status bar holds only the deconvolution state.
   - The header adds "N of M selected" only while there is a selection.
   - "Apply" no longer carries a count.
   - One default caption remains (issue 11).
3. **Peak-window buttons cut on short windows: fixed for the buttons.** They are pinned (`extra/12`, `150L/29`). The cut moved to the field above them (issue 3), so this counts as partly fixed.
4. **Compact a no-op: fixed.** 6 columns against 5 at 1512 wide, with a 130×95 minimum tile (`extra/09_compact.png`).
5. **Uppercase labels everywhere: fixed.** Uppercase is now sidebar-only; dialogs use sentence-case section titles (`WL/04_…`, `WL/18`).
6. **Settings explaining instead of acting: partly fixed.** Internal Standard has its combo, and Integration is one line ("Applies to plots. Export asks again."). Peak Validation and Internal Standard still lead with paragraphs (issue 6).
7. **Dialog type scale: fixed.** At real size the Settings body matches the other dialogs. About is 360×214 with a normal Close (`WL/21`). Part of my round-4 claim came from upscaled contact sheets.
8. **Checklist as manual: fixed.** The description and hover hint are gone; three steps sit behind the disclosure, plus "Details in the user guide" (`WL/04_…_steps`).
9. **"No internal standard" written four ways: fixed,** apart from the menu's title case. The sidebar shows "None" as a value, which is fine.
10. **Detailed view defaults: mostly fixed.** It is themed in both schemes, with a tall EIC panel and readable ticks (`WL/11`, `MD/32`). Still open: the tab10 palette, the spectrum below the fold, and the debug footer (issues 5 and 7).
11. **Documentation blank in captures: fixed.** All docs captures render in all eight folders.
12. **Cross-platform badge position and jagged menu check: fixed.** Badges sit in one row under the title on both platforms (`WD/24`, `MD/24`), and the menu check is the app's SVG.

**Bugs from the brief, verified live:**
- The sample-list right-click menu opens and works (`extra/log.txt`).
- The deconvolution status is present right after load (`extra/log.txt`, "after load status").

**Improved beyond the list:**
- Export Options is now its own dialog and comes before the save location (`extra/08_export__ExportOptions.png`).
- Peak-window fields show ranges for mixed values ("0.08 - 0.1").
- Settings Save and Discard disable once saved.

**Regressed:** nothing functional. The sliced-field artefact (issue 3) is the visual cost of pinning the buttons.

**Lost functionality: none found.**
- I compared `QAction`, `addAction`, `QCheckBox`, `QPushButton` and `QRadioButton` labels in `src/manic/ui` between `origin/main` and 6ec219c (`labels_*.txt`). Every label only on main has a renamed or moved equivalent:
  - "View Detailed..." → "Inspect Sample...";
  - "Select All" → "Select All Plots";
  - "Accept peak (below threshold)" and "Mark peak as bad" → title case;
  - "Use compound setting" → "Use Compound Setting";
  - "Update tR Window" → "Apply window";
  - "Restore Selected" → "Restore selected" (`recovery_dialog.py:62`);
  - "Save" → "Save this page".
- Since round 4, "Show All Samples" left the View menu but remains in Review, in the plot context menu and in the sample-list menu.
- The sidebar status rows stopped being load buttons. They were added on this branch, not on main, and loading stays in File, on the start panel and by drop.
- Live checks:
  - all five compound-list menu entries;
  - the sample-list menu;
  - multi-select;
  - accept, mark and clear;
  - the per-sample curve fit editor (Settings › Deconvolution, `WL/16_…page5`);
  - Shared y-scale and Scale to selected peak (`extra/07_tabs__Display.png`);
  - the internal-standard menu;
  - both exports.

**Per-platform limits.**
- **Windows** was judged from CI at 100% and 1024×720; it renders cleanly in both schemes. Not verified:
  - 125% and 150% scaling;
  - the native dark title bar;
  - hover and tooltips.
- **macOS:**
  - The native menu-bar rendering of the Review menu shortcuts is not verified (issue 12).
  - The tour forces the scheme, so a real OS switch was not tested.
- **150%** is the harsh 1008×633 stand-in, not a real laptop.

**Note on my driver.** An early run seemed to "hang" in the sample-list menu. My stub patched `QMenu.exec` but not `exec_`, so a real modal menu was waiting for a click. It is not an app bug: with the stub fixed the menu works. Idle CPU was about 0.1 s per second, which is my pump loop.

```json
{"F1": 8, "F2": 8, "F3": 9, "F4": 9, "F5": 8, "F6": 9, "F7": 8, "F8": 8, "F9": 7, "overall": 8.2}
```
