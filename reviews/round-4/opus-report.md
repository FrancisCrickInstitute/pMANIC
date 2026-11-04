# MANIC UI/UX review, round 4 (re-rating at 5cf5d336), reviewer: opus

## Evidence

**Screenshots.** I viewed every PNG in all eight round-4 folders: `ci-windows-latest-light/`, `ci-windows-latest-dark/`, `ci-macos-15-light/`, `ci-macos-15-dark/`, `mac-light/`, `mac-dark/`, `mac-light-150pct-1280x800/` and `mac-dark-150pct-1280x800/`. I went through them as contact sheets, then opened full size where a detail mattered. Short names used below:
- `WL/` and `WD/`: Windows light and dark.
- `ML/` and `MD/`: CI macOS light and dark.
- `mL/` and `mD/`: local Mac light and dark.
- `150L/` and `150D/`: the two 150% folders.

**My own driver.** `review-r4b-opus/drive.py` imports a copy of the tour with only `ROOT` changed. It ran on this Mac in light mode and wrote `extra/NN_*.png` and `extra/log.txt`. It covered:
- setting the internal standard to Palatinose, which gives Bio_004 a "Below threshold" verdict;
- selecting Bio_004 with two passing plots, reading the Review menu, triggering Accept, then reading the menu again;
- Compact against Comfortable density;
- the arrow keys → ↓ Space;
- the documentation viewer, after a 4 s wait;
- 1280×720 and 1024×640 windows with Samples open;
- the labelled detailed view.

**Not run.**
- Hover, native tooltips and real focus rings were not watched.
- Halfway through, the disk filled up (ENOSPC on the temp volume), so I could not run more shell commands. The `git diff 795ecbe6..5cf5d336` check for removed actions did not run. The `origin/main` comparison below ran before that.

## Verdict

Round 4 closes almost every round-3 issue, and nothing is broken on any platform:
- The post-load checklist now scrolls under a fixed footer, with the pattern steps behind a disclosure (`150L/04`, `150D/04_…steps`).
- The two review menus match in order and wording (`09_*menu` = `10_*menu`).
- The Identity popup now shows one line instead of a grey wall (`31`).
- Missing samples show "—" (`WL/14`, Bio_018).
- The spectrum carries an "M+0…M+3" bracket (`WL/11`).
- "Not detected" is a real pill in dark mode (`WD/24`).
- Live check: with three plots selected and one below threshold, the menu reads "Accept Peak (Below Threshold)". After Accept it reads "Clear Acceptance", and Bio_004 shows a green "Accepted" pill (`extra/log.txt`, `extra/03_…after_accept`).

**Windows.** The first real Windows screenshots render cleanly in both schemes at 1024×720. Segoe UI fits, nothing clips, and the dialog button order follows the platform.

**What holds the score back is taste (F9).** The new factor shows:
- The start screen is close to the textbook template: logo, hero title, numbered stepper card, three helper paragraphs, then a row of links.
- On the loaded screen, "30 samples" appears seven times.
- Uppercase letter-spaced section labels are used on every surface.
- Settings and the checklist still explain in paragraphs.
- The charts use the default matplotlib palette.

**Smaller defects.**
- On short windows, the Peak window's Reset and Apply buttons are cut through the middle.
- The Compact toggle barely changes anything at common window sizes.

**Means.** F1..F8 mean: **8.0** (round 3: 7.9). Overall with F9: **7.8**.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 8 | One token system holds across Windows, macOS, light, dark and 150% (`WL/05`, `WD/05`, `150D/05`). The tile tints (Below threshold amber, QC fail red, Not detected grey with a pill) read in both schemes (`extra/01`, `WD/24`). Held back by: the About dialog's oversized body and Close button (`WL/21`); Settings in 11–12 px type next to 15–16 px dialogs (`WL/16_*` vs `WL/18`); and Peak-window buttons cut through the middle on short windows (`extra/09`, `150L/29`). |
| F2 | Layout and hierarchy | 8 | Fixed: the checklist is a scroll body with a fixed footer at 150% (`150L/04`). The lists keep 4 compound and 3 sample rows at 1024×640 (`extra/09`). At full height the inspector uses collapsible Peak window / Display / Summary sections whose headers carry state ("tR 7.09 · Baseline on", "Own scale", `extra/01`). Remaining: buttons sliced at short heights (`extra/09`, `150L/33`), and repeated counts in sidebar, header and status bar (issue 2). |
| F3 | Onboarding and workflow clarity | 8 | The start panel states both steps with shortcuts and marks the done step ("95 compounds loaded", `mL/03`). Quick Start has a keyboard table (`extra/07`). The checklist names the file and has Open File and Show in Folder (`WL/04_…`). Docked for wordiness: the checklist hint and disclosure (`post_load_checklist_dialog.py:45-57`), and a Settings page that sends you to the sidebar (`WL/16_…page4`). |
| F4 | Consistency and polish | 8 | The review menus are identical in order and labels, and the shortcut column shows Return, Ctrl+A, Esc and Ctrl+Shift+B on Windows (`WL/09_*menu`, `WL/10_*menu`). One accept/clear wording rule drives both menus (`graphs.py:170-178`, `graphs.py:968-990`). Leftovers: "no internal standard" is written four ways (issue 9); the Settings type scale differs from the other dialogs (issue 7); the QC-fail badge sits in a different place on Windows than on macOS (`WL/24` vs `mL/24`). |
| F5 | Feedback and state | 8 | Verified live: Accept applies to the eligible subset, the label flips to "Clear Acceptance", and the tile gets an "Accepted" pill (`extra/log.txt`, `extra/03_…`). "Applies to 3 selected samples" is shown in accent (`07`). The empty state, "No samples shown · Show all samples", works (`34`). The toast "Imported 2850 EICs" appears. The documentation pane is blank in 4 of 8 captures; it renders after 4 s locally (`extra/07`), so this is a capture race, not a product bug (issue 11). |
| F6 | Efficiency and flexibility | 8 | Verified: → ↓ Space moved focus from Bio_001 to Bio_002 to Bio_008 and selected it (`extra/log.txt`). Ctrl+A, Esc, Return and Ctrl+Shift+B are shown in the menus. A pinned switcher appears on short windows. Compact density is nearly a no-op at 1512×949: the same 6×5 grid with tick text 1 px smaller (`cmp_density.png`; `plot_tile.py:27-29`). The Peak-window buttons are cut through at 1024×640. |
| F7 | Data visualisation | 8 | Popups use grid order with "—" and "<0.01" (`WL/13`, `WL/14`). The spectrum has an M+0…M+3 bracket (`WL/11`). The legend says "(not assessed)" in plain words (`WD/32`). The Identity popup gives one clear line when nothing can be assessed (`WL/31`). The summary charts name their samples (`150D/12`). The detailed view is still matplotlib defaults: a squashed EIC panel, about 8 px tick labels on Windows, "m/z 174.0000", and the default tab10 isotopologue palette (`WL/11`). |
| F8 | Modern feel | 8 | Live scheme switching keeps the selection (`WD/08`). Segmented controls, quiet cards, state-carrying section headers and toasts all read as modern, considered software on Windows and macOS. The template start screen and the paragraph-heavy dialogs are where it slips back into "in-house tool". |
| F9 | Taste (not AI slop) | 6 | Real character lives in the plot grid: isotopologue lines, ×10ⁿ in the tile corner, and verdict tints and pills that carry meaning. The chrome around it is generic: a template start panel (`start_panel.py:91-181`), seven repeats of the sample count, uppercase letter-spaced labels on every group, helper paragraphs in Settings and the checklist, "You can also drop…" (`start_panel.py:153`), stock blue primary buttons and the stock matplotlib palette. That puts it between "competent but template-like" (5) and "considered with a few generic patterns" (7). |

Overall: (8+8+8+8+8+8+8+8+6)/9 = 7.78 → **7.8**. The F1..F8 mean is **8.0** (round 3: 7.9).

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| Template layout: logo, hero title and subtitle, numbered stepper card, three helper paragraphs, then a row of two links | `02_empty_labelled` (all folders); `start_panel.py:91-181` | No. |
| "Load" shown in three places: sidebar "Compound list · Load…", start card "Load list… ⌘O", status bar "No data loaded. Start by loading a compound list." | `mL/02`, `WL/02` | Sidebar row: yes, it is a persistent status. Status bar line: no. |
| Sample count shown seven times on one screen: sidebar "✓ 30 samples"; header "tR 7.09 · 30 samples"; Samples "30 · all shown"; "Applies to all 30 samples"; "Apply to 30 samples"; "Re-extracts all 30 shown samples"; status bar "Pyruvate · 30 samples" | `WL/05` | Justified: the sidebar (load status), the Samples section (filter state) and the Apply button (it acts). Not justified: the status bar line repeats the header, and "Applies to all…" repeats the button below it. |
| Compound name shown three times: list selection, canvas header, status bar | `WL/05` | The status bar copy is not justified. |
| Checklist heading followed by a description that restates it, plus a hint explaining hover | `WL/04_…Dialog`; `post_load_checklist_dialog.py:126-134` | No. |
| The checklist's pattern steps repeated in Quick Start step 4 | `extra/07` | Acceptable: docs are a separate surface. |
| Settings › Internal Standard shows "Internal standard: none" and a footnote sending you to the sidebar | `WL/16_…page4` | No. The page duplicates state it cannot change. |
| "Optional" label next to a combo whose first item is "No internal standard"; sidebar says "None (optional)" | `WL/04_…Dialog`, `WL/05` | Weak. |
| Uppercase letter-spaced labels on every group: LABELLED ANALYSIS, COMPOUNDS, SAMPLES, PEAK WINDOW, INTERNAL STANDARD, STANDARD MIXTURE (MM) FILES, IDENTITY, RETENTION, MASS AND LABELLING, IONS, STANDARDS, COMPOUND SETTINGS, PER-SAMPLE CURVE FIT, RECENT | everywhere | Uniform sameness. |
| Wordy help that restates labels: "Minutes before (left) and after (right) tR that bound the peak." under Left/Right offsets; the Integration page's "The change will only apply to graphs in the GUI…See documentation…" | `WL/18`, `WL/16_…page2` | No. |
| Stock matplotlib tab10 palette for M+0…M+4; stock teal bars | `WL/13`, `WL/14` | Generic, though readable. |
| Review menu and plot context menu carry the same commands | `09`, `10` | Yes: menu plus context menu. |
| "Double-click a chart to reset it" next to a "Reset all" button | `WL/11` | Yes: they do different things. |

## Top 12 issues, ranked by user impact

1. **The start screen is the template layout (F9).**
   - Where: `02_empty_labelled` and `03_compounds_only` in every folder; `start_panel.py:91-181`, with "You can also drop…" at `:152-157` and "Have a saved session?" at `:159-165`.
   - Fix:
     - Drop the hero subtitle, the numbered badges and the three hint paragraphs.
     - Keep two plain rows ("Compound list [Load… ⌘O]", "Raw data folder [Load… ⇧⌘O]") and the Recent list.
     - Show one drop-target outline that appears on drag, instead of a sentence about dropping.
     - Remove the status-bar instruction.
   - Gain: F9 +0.5, F1 +0.1.

2. **The sample count and compound name are repeated across sidebar, inspector, canvas header and status bar.**
   - Where: `WL/05` and `extra/01`.
   - Fix:
     - The status bar shows only transient or extra state (the selection count, the deconvolution summary). Drop "Pyruvate · 30 samples", which the header already shows.
     - Hide the "Applies to all N samples" caption when the scope is all samples; the button says it. Keep the accent "Applies to 3 selected samples" only when a selection narrows the scope.
     - Fold "Re-extracts all 30 shown samples" into the button: "Apply window to 30".
   - Gain: F9 +0.5, F2 +0.25.

3. **Peak-window controls are cut through the middle on short windows.**
   - Where:
     - `extra/09_w1024x640_samples_open`: the Reset / "Apply to 2 samples" row is cut off at the bottom.
     - `150L/29` and `150D/29`: the same row is clipped through its text.
     - `150L/33`: the inspector ends at "Right offset".
     - These are the window sizes laptop users hit.
   - Fix: pin the Reset / Apply row as a footer under the scrolling fields (the switcher is already pinned), or snap the scroll so a button row is never half shown.
   - Gain: F2 +0.25, F6 +0.25, F1 +0.1.

4. **The Compact density toggle barely changes anything at common sizes.**
   - Where: `extra/03` against `extra/04`, cropped in `cmp_density.png`. Both give 6×5 tiles of the same size; only the tick text drops from 11 to 10 px. Code: `plot_tile.py:27-29` (`DENSITY_MIN_TILE`, `DENSITY_TEXT`) and `graphs.py:679`.
   - Fix: make Compact visibly denser:
     - smaller minimum tile, about 130×95;
     - x tick labels only on the bottom row, and y ticks reduced to min and max;
     - a 12 px caption.
     - Or move it to the View menu and free the header slot.
   - Gain: F6 +0.25, F9 +0.25.

5. **Uniform uppercase letter-spaced group labels and grey helper text on every surface.**
   - Where: the sidebar, `WL/04_…Dialog`, `WL/18`, `WL/16_…page5` and `mL/02` (RECENT).
   - Fix:
     - Keep the uppercase style for the sidebar's own sections only.
     - Dialogs use sentence-case semibold group titles.
     - Delete helper lines that restate their label (offsets, "Selected samples · Select tiles in the plot area to set their fit here").
   - Gain: F9 +0.25, F1 +0.1.

6. **Settings pages explain instead of acting.**
   - Where:
     - Internal Standard (`WL/16_…page4`): "Internal standard: none" plus a footnote pointing at the sidebar.
     - Integration (`…page2`): two sentences about the GUI and export.
     - Deconvolution (`…page5`): a four-line paragraph under the controls.
   - Fix:
     - Put the internal-standard combo on that page (the same control as the checklist), or fold the reference-peak control into the sidebar's internal-standard menu and drop the page.
     - Integration: "Applies to plots. Export asks again."
     - Deconvolution: one line per control, shown as hover help.
   - Gain: F9 +0.25, F3 +0.1.

7. **The dialog type scale is inconsistent.**
   - Where:
     - Settings nav and body are 11–12 px, tiny on Windows (`WL/16_*`).
     - Add Compound, Process External and the checklist use 15–16 px (`WL/18`, `WL/20`, `WL/04_…Dialog`).
     - About uses about 26 px body text with an outsized Close button (`WL/21`, `150L/21`).
   - Fix: one scale from `dialog_kit`: 13 px body, 15 px group title, 20 px dialog title. About: logo, version and one 13 px line.
   - Gain: F4 +0.25, F1 +0.25.

8. **The checklist still reads as a manual.**
   - Where: the description restates the title (`post_load_checklist_dialog.py:126-134`). The hint below the table explains hovering (`WL/04_…Dialog`). The disclosure opens a nine-line numbered paragraph (`:45-57`, `WL/04_…steps`).
   - Fix:
     - Title only.
     - Drop the hover hint; the tooltip exists.
     - Disclosure content becomes three short lines ("Edit the mmfiles cell · File › Clear Session · Reload both files") plus "Details in the user guide".
   - Gain: F9 +0.25, F3 +0.1.

9. **"No internal standard" is written four ways.**
   - Where: sidebar "None (optional)"; checklist and Process External combo "No internal standard" plus a separate "Optional" label; the internal-standard menu "No Internal Standard" (`30`); Settings "Internal standard: none".
   - Fix: one string, "No internal standard", everywhere. Drop the extra "Optional" label.
   - Gain: F4 +0.1, F9 +0.1.

10. **The detailed view is still matplotlib defaults.**
    - Where: `WL/11`, `WD/11`. The EIC panel has about 90 px of plot height with three equal-height panels. Windows tick labels are about 8 px. The footer shows "m/z 174.0000" and repeats "M+0…M+3" from the spectrum label. The isotopologue palette is tab10.
    - Fix:
      - Give the EIC panel about half the height.
      - Ticks at 10 px or more.
      - m/z to 2 decimal places.
      - Drop the repeated M-range from the footer.
      - Consider a palette tuned for M+n order: one hue ramp light to dark, readable in both schemes.
    - Gain: F7 +0.25, F9 +0.1.

11. **The documentation pane is blank in half the tour captures.**
    - Where: `ML/17`, `MD/17`, `WD/17` and `mL/17` (right pane is a flat fill; measured pixel stddev 0). `WL/17`, `mD/17` and both 150% folders render. My 4 s capture renders (`extra/07`).
    - Cause: the tour grabs the `QWebEngineView` before `setHtml` finishes (`documentation_viewer.py:166`, `:337`; `scripts/ui_tour.py:455-457`). Users may also see a blank pane briefly.
    - Fix: wait for `loadFinished` in the tour, and show a light placeholder in the viewer until it loads.
    - Gain: reliable proof that docs render on Windows dark; F5 +0.1.

12. **Small cross-platform differences.**
    - The "QC fail" badge sits at the right of the title row on Windows (`WL/24`, `WD/24`) but on a second line on macOS (`mL/24`, `ML/24`), so the verdict moves between platforms.
    - The internal-standard menu check renders as a jagged double tick on macOS (`mL/30`, `150D/30`).
    - Fix: a fixed badge row under the title on every platform; use the app's SVG check for the menu.
    - Gain: F4 +0.1.

## Re-rating comparison

**Round-3 issues, status:**
1. Checklist overlapping at 150%: **fixed.** It is a scroll body with a fixed footer, and the steps sit behind "How do I change a pattern?" (`150L/04`, `150D/04_…steps`). It renders cleanly on Windows at 1024×720 (`WL/04_…`).
2. Cramped lists on short windows: **fixed for the lists** (4 compound and 3 sample rows at 1024×640, `extra/09`). The cost moved to the Peak window, whose buttons are now cut through (issue 3). Counts as partly fixed.
3. Raw enum in the detailed legend: **fixed.** It reads "(not assessed)" (`WD/32`).
4. Grey Identity popup: **fixed.** One line, "No expected ratios set for Glycine. Add them in Settings › Qualifier Ratios.", with chips "no expected ratio" and "not in the method" (`WL/31`).
5. Menu names and order: **fixed.** Both menus run Inspect / Select All Plots / Deselect All / Show Only / Show All / Accept / Mark / Curve Fit (`WL/09_*menu`, `WL/10_*menu`).
6. Sidebar charts without names: **fixed.** The Summary charts name each sample and scroll (`150D/12`).
7. Blank rows in the label popup: **fixed.** It shows "—" (`WL/14`, Bio_018).
8. Dead band in Summary: **not verified.** The tour does not open Summary with the unlabelled data, and my driver could not reach it before the disk filled.
9. Identity chart filtering instead of highlighting: **not verified live.** The brief says it now highlights.
10. Spectrum labelling: **fixed.** "M+0…M+3" bracket (`WL/11`).
11. Not detected faint in dark: **fixed.** A pill plus a stronger tint (`WD/24`, `150D/24`).
12. Checklist as manual: **partly fixed.** The steps are folded away, but the hint and the paragraph wall remain (issue 8).

**Improved beyond the list:**
- Group Accept acts on the eligible subset, then reads "Clear Acceptance" (verified).
- The scope caption survives re-plots (`07` → `08_*`).
- Comfortable density uses larger chart text.
- On tall windows the inspector's collapsible sections carry their state in the header (`extra/01`).
- CI now produces real Windows and macOS screenshots.

**Regressed:** the Peak-window buttons cut through at short heights (issue 3), the side effect of giving the lists their rows. Nothing else.

**Lost functionality: none found.**
- I compared the action and menu labels in `main_window.py`, `graphs.py`, `compound_list_widget.py` and `sample_list_widget.py` between `origin/main` and 5cf5d336.
- Every main entry is still present, sometimes renamed:
  - View Detailed… → Inspect *sample*…
  - Select All → Select All Plots
  - Accept peak (below threshold) → Accept Peak (Below Threshold)
  - Curve fit → Curve Fit
  - Use compound setting → Use Compound Setting
- Added: the View and Review menus, Find Compound, Next/Previous Compound, and Show All Samples on the sample list.
- The compound-list menu (all 5 entries), Recover Deleted Samples and the curve-fit submenu (`09_*menu`) are intact.
- Settings has all six pages, plus Qualifier Ratios in unlabelled mode (`WL/27`). The per-sample curve-fit override and "Remove all overrides" are there (`WL/16_…page5`).
- Live: multi-select, keyboard selection, peak verdicts, the internal-standard menu, density, both popups and the detailed view all work.
- Gap: the line-level diff since round 3 (`795ecbe6..5cf5d336`) could not run because the disk was full, so removals inside unchanged labels are unchecked.

**Per-platform limits.**
- Windows was judged from the CI runners at 100% scaling, 1024×720. Not verified on Windows:
  - 125% and 150% scaling;
  - the native dark title bar;
  - hover and tooltips;
  - a real OS-driven scheme switch (the tour forces the scheme).
- macOS (local Retina and CI): the native menu bar, where Settings sits, and ⌘ glyphs in the menu bar itself are not in the captures. Menu shortcut glyphs render as expected (`mL/09_*menu`).
- 150% is the harsh 1008×633 stand-in, not a real laptop.

```json
{"F1": 8, "F2": 8, "F3": 8, "F4": 8, "F5": 8, "F6": 8, "F7": 8, "F8": 8, "F9": 6, "overall": 7.8}
```
