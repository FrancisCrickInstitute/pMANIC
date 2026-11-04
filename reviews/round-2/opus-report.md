# MANIC UI/UX review, round 2 (re-rating at 6fc71eb5), reviewer: opus

Evidence:
- The round-2 tour: `shots/linux-light/`, `shots/linux-dark/` and `shots/linux-dark-150pct-1280x800/`. I viewed every PNG; names below without a folder are from `linux-light`.
- My own driver, `/tmp/review-r2-opus/drive.py` and `drive2.py`, writes `extra/NN_*.png` and `extra2/NN_*.png` with a `log.txt` in each folder. It covered:
  - the Review, View and plot context menus in both modes
  - the Display section, toggled across 4 compounds
  - grid keyboard (→ ↓ Space)
  - Next Compound
  - unchecking and rechecking a sample
  - 1024×768 with Samples open and closed, and inspector scroll
  - 1280×720 and Compact density
  - the unlabelled QC-fail sample: Review menu, context menu, Identity popup and detailed view
  - the Qualifier Ratios settings page
  - dark mode at 1600 with the sidebar scrolled to the bottom

The GUI ran offscreen (Inter font). Native tooltips and real keyboard focus could not be observed there; I checked those paths in code.

## Verdict

Round 2 is a real step up. Dark mode is complete: main window, every dialog, the matplotlib detailed view, popups, menus and the logo all follow the tokens, and nothing is unreadable (`linux-dark/*`, `08_live_scheme_switch__*`). Almost every round-1 finding is fixed, and I verified the fixes live:
- The Display summary now tracks its checkbox across compound switches (`extra/log.txt`).
- The grid header names the compound (`05`).
- Baseline correction moved into Peak window, with its own summary.
- The sample list has "shown" checkboxes and keeps grid order after uncheck and recheck (`extra/log.txt`).
- Popup labels use one precision, with "—" for empty bars.
- The detailed view has a single toolbar and themed colours.
- The Settings footer is aligned, and Add Compound flags every missing field.
- The docs render and match the UI labels.

The new Review menu gives every review command a menu-bar path.

The weak spot is the fix for "browsing room": the sidebar now protects the lists so hard that on a 768-tall window, or a 150% laptop with Samples open, the Peak window gets a 96 px scroll pane. In that state the integration controls (tR, offsets, Apply) sit below the fold of a sliver (`extra/06`, `linux-dark-150pct-1280x800/28`). Collapsing Samples does not give the space back until the window is resized.

Nothing from `origin/main` is lost.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 8 | One token system holds in light and dark at 100% and 150% (`05`, `linux-dark/05`, `linux-dark-150pct-1280x800/05`). Dialogs share one kit (`04`, `17`, `19`, `20`, `15_*`), and the detailed view is now on-palette (`10`, `linux-dark/10`). Held back by the stripe-only sidebar summary charts (`extra2/02`), the "Not detected" card whose tint stops at a white plot area (`23`, `25`), and Pan/Zoom drawn as bare text (`10`). |
| F2 | Layout and hierarchy | 6 | At 1600×1000 it is good: compound title, about 11 compound rows, Peak window then Display then Summary (`05`). But at 1024×768 with Samples open the inspector is 96 px tall (`extra/06`; splitter `[521, 96]` in `extra/log.txt`; `left_toolbar.py:419-445`). The 150% laptop shot shows only "Left offset" (`linux-dark-150pct-1280x800/28`). Collapsing Samples keeps the 96 px until a resize (`extra/07`; `left_toolbar.py:354-357` never refits). A 3-item filtered compound list holds about 280 px of empty space while the sample list scrolls 5 rows (`28`; `left_toolbar.py:146`). |
| F3 | Onboarding and workflow clarity | 8 | Two-step start panel with state and Recent (`02`, `03`). Docs render and match the labels (`16`). Plain labels: "Apply to 30 samples", "Apply window", "Applies to 3 selected samples" (`07`). Add Compound shows all errors at once (`18`). Remaining: the checklist says weak peaks are "shown in red" while Settings says "amber Below threshold badge" (`04` vs `15_settings__SettingsWindow_page1`; `post_load_checklist_dialog.py:130`, `settings_window.py:182`). Baseline Correction is still listed in View. |
| F4 | Consistency and polish | 7 | The Settings footer is aligned on every page (`15_*`), there is one window-title pattern, and dark dialogs match light. The new Review menu, though, names the same commands differently from the plot menu: "Inspect Sample_04…" vs "View Detailed…", Title Case vs sentence case, "Curve Fit" vs "Curve fit" (`extra/11_*review_menu_fail` vs `extra/11_*ctx`; `main_window.py:535-569`, `graphs.py:859-909`). The two summary popups sort samples in opposite directions (`12` vs `13`). |
| F5 | Feedback and state | 8 | The Display and Peak window summaries match their checkboxes, verified over 4 compounds (`extra/log.txt`, `extra/02`). Apply carries the target count ("Apply to 1 sample", `06`), and the Review menu labels do too ("Mark 3 peaks as bad", `09_*menu`). Also: a selection count in the header and status bar, QC fail tint and "Not detected" badges in both schemes (`23`, `linux-dark/23`), and "11 shown · 11 match" on the sample filter (`28`). Docked for the stale split after collapsing Samples, and for "Not detected" being hard to see in dark (`linux-dark/23`). |
| F6 | Efficiency and flexibility | 7 | Every review command now has a menu-bar path with native shortcut text (`extra/11_*review_menu_fail`). Verified: grid keyboard selection (`extra/03`), Next Compound (`extra2/log.txt`), Space toggling on sample checkboxes (`sample_list_widget.py:119-132`), sample order kept, and Compact giving 4 columns at 1024 (`extra/09`). Small screens fail exactly where laptops live: 768 px tall or 150% with Samples open buries the integration controls (`extra/06`, `linux-dark-150pct-1280x800/28`). |
| F7 | Data visualisation | 8 | Popups put one formatted value per sample, with "<0.01" and "—" (`12`), and the label popup has a chip key (`13`). Legend chips wrap instead of eliding (`11`). The detailed view has a single toolbar, a themed TIC, a "×10⁶" exponent and a "·" footer (`10`). Unlabelled detailed view says "(failed)" in the legend (`extra/14`). Remaining: sidebar charts show no names and odd ticks "0.0 / 1.9 / 3.8" (`extra2/02`). The single-sample Identity chart is two giant blocks (`24`, `extra/12`). Value labels are struck by gridlines ("0.97", `12`). Spectrum labels sit on the baseline while the M+1…M+3 cluster is unlabelled (`10`). |
| F8 | Modern feel | 8 | Live scheme switching with selection kept (`08_*`), the start panel, segmented density, cards and quiet hierarchy: this reads as current, considered software in both schemes. The sidebar summary charts and the cramped laptop inspector are the parts that still feel in-house. |

Overall: (8+6+8+7+8+7+8+8)/8 = 7.5 → **7.5** (round 1: 6.8)

Per-platform limits:
- macOS: not verified. This covers the native menu bar (where the Review menu sits, and the "Help" naming at `main_window.py:363-364`), ⌘ glyphs in the Review menu, and the Fusion controls against Aqua.
- Windows: not verified. This covers Segoe UI metrics in the status rows, 125% rounding, and the non-native "MANIC" menu.
- Code reads platform-correct: `QKeySequence` throughout, `shortcut_text` (`sidebar_widgets.py:33`), and no hard-coded ⌘ left. Nothing in the code or the 150% render shows a broken layout specific to one platform.

## Top 12 issues, ranked by user impact

1. **On short or scaled screens the Peak window gets a 96 px sliver.**
   - Where: `extra/06_w1024x768_samples_open.png` (splitter `[521, 96]`) and `linux-dark-150pct-1280x800/28` (only "Left offset" visible). The causes are in `left_toolbar.py`:
     - `browse_floor` (`:419-430`) multiplies 10 compound rows by 5/3 when Samples is open.
     - `fit_inspector` (`:432-445`) then caps the inspector at `total - 96`.
     - `_on_samples_section_toggled` (`:354-357`) never restarts `_fit_timer`, so collapsing Samples leaves the sliver (`extra/07`; a manual refit gives `[364, 253]`, `extra2/log.txt`).
   - Fix:
     - Reserve the Peak window body height (about 260 px) for the inspector before applying the browse floor.
     - On short heights, let the floor shrink to about 6 compound rows plus 4 sample rows.
     - Call `self._fit_timer.start()` in `_on_samples_section_toggled`.
   - Gain: F2 +1, F6 +0.5.

2. **The browse pane splits by fixed stretch, not by content.**
   - Where: `28` in all three folders. Three filtered compounds sit above about 280 px of empty space while the sample list shows 5 rows and scrolls. Cause: `browse_layout.addWidget(self.compound_list, 3)` at `left_toolbar.py:146` against Samples at 2 (`:357`).
   - Fix: when the visible rows need less height than the stretch share, cap the compound list at its content height and give the remainder to Samples, and the other way round.
   - Gain: F2 +0.5.

3. **The sidebar summary charts still can't be read in place.**
   - Where: `extra2/02_summary_scrolled_1600.png`.
     - Label Incorporation shows 30 unnamed stripes.
     - Total Abundance shows unnamed bars with ticks "0.0 / 1.9 / 3.8".
     - Total Abundance is reachable only by scrolling the inspector, even at 1600×1000 (`05`).
   - Names exist only as hover text (`isotopologue_ratio_widget.py:281-294`, `total_abundance_widget.py:185-193`).
   - Fix:
     - Use `set_nice_ticks` (already used in the popup) for the sidebar axis.
     - Mark the selected samples' bars with the accent colour, so the chart answers "where is my sample".
     - Collapse Summary by default when the inspector is shorter than Peak window plus Summary.
   - Gain: F7 +0.5, F2 +0.25.

4. **The Review menu and the plot context menu name the same commands differently.**
   - Where:
     - The Review menu says "Inspect Sample_04_ratio_fail…", "Accept Peak (Below Threshold)", "Mark Peak as Bad" and "Curve Fit" (`extra/11_*review_menu_fail`; `main_window.py:535-569`).
     - The context menu says "View Detailed…", "Accept peak (below threshold)", "Mark peak as bad" and "Curve fit" (`extra/11_*ctx`, `09_*menu`; `graphs.py:859-909`).
     - The Quick Start tells the user to choose "View Detailed…" (`16`).
   - Fix: define each label once, for example in a module constant used by both menus. Pick one verb ("Inspect…" or "View Detailed…") and one case style.
   - Gain: F4 +0.5.

5. **The two summary popups sort samples in opposite directions.**
   - Where: `12_abundance_popup` runs Std_MM_02 at the top down to Bio_001 at the bottom. `13_label_popup` runs Bio_001 at the top down to Std_MM_02. Code: `chart_popup_dialog.py:288-290` and `:505-507` reverse both the values and the names, so the abundance chart ends up flipped against the label chart.
   - Fix: make both popups list samples in sidebar and grid order, top to bottom.
   - Gain: F7 +0.25, F4 +0.25.

6. **The QC copy disagrees about colour.**
   - Where: the checklist says "Weak peaks are only flagged (shown in red) when an internal standard is set" (`04`; `post_load_checklist_dialog.py:130`). Settings › Peak Validation says the plot "gets an amber Below threshold badge" (`15_settings__SettingsWindow_page1`; `settings_window.py:182`). Red is the QC-fail colour (`23`).
   - Fix: change the checklist line to "…get an amber Below threshold badge…".
   - Gain: F3 +0.25, F4 +0.25.

7. **Baseline Correction moved in the sidebar but not in the menu.**
   - Where: the sidebar puts it in Peak window (`05`). The View menu still lists it first among the display toggles with ⇧⌘B / Ctrl+Shift+B (`main_window.py:464-466`; `left_toolbar.py:322-327`, whose docstring says "Every view toggle … baseline correction included").
   - Fix: move the action to the Review menu, next to the peak commands, and keep the shortcut.
   - Gain: F3 +0.25, F4 +0.25.

8. **The Identity chart with one sample is still two giant blocks.**
   - Where: `24` (sidebar) and `extra/12_unl_identity_popup` (popup, two red slabs about 80 px tall).
   - Fix: cap the cell height at about 24 px and top-align the grid. The "Qualifier cells" footer already carries the counts.
   - Gain: F7 +0.25.

9. **Two loose ends in the detailed view.**
   - Pan and Zoom are bare text with no button shape. The offscreen tour could not show their checked state, so verify it on a real display (`10`, `linux-dark/10`; `matplotlib_plot_widget.py:170-190`).
   - The spectrum labels low-intensity peaks on the baseline (73.02, 147.00, 207.01, 280.99), while M+1…M+3 next to 174.99 have no labels (`10`).
   - Fix: style Pan and Zoom as the segmented control already used for density. Label the compound's own isotopologue m/z values first, then the top N others above a minimum intensity.
   - Gain: F7 +0.25, F1 +0.25.

10. **The "Not detected" card is a half-tint.**
    - Where: the grey card fill stops at a white plot area in light (`23`, `25`: Sample_05_rt_shift). In dark the tint is nearly invisible (`linux-dark/23`).
    - Fix: tint the plot background too, or dim the traces to 50% and keep the badge. Check contrast in dark.
    - Gain: F1 +0.25, F5 +0.25.

11. **Popup value labels collide with gridlines.**
    - Where: "0.97" for Bio_011 and Bio_012 is struck through by the x = 1.0 gridline (`12`, `linux-dark/12`, `linux-dark-150pct-1280x800/12`).
    - Fix: give labels a panel-coloured backing, or draw gridlines beneath the label layer.
    - Gain: F7 +0.1.

12. **Small menu and status gaps.**
    - The Internal standard menu has no check mark on the current choice; the current item only looks greyed (`29`).
    - On Windows and Linux the app menu is titled "MANIC" and holds Settings, Documentation and About (`main_window.py:363-364`), where Windows users look under Help (and Tools or File for Options).
    - The inspector keeps its scroll offset across compound switches, so after scrolling to Summary the next compound opens with Peak window off-screen (`extra2/05`).
    - Fix: make the Internal standard menu checkable, title the non-native menu "Help" with Settings under File, and reset the inspector scroll on compound change, or keep Peak window pinned.
    - Gain: F4 +0.25, F6 +0.25.

## Re-rating comparison

**Improved (round-1 issue → now), verified live or in the shots:**
- #1 stale Display summary: fixed. The summary matches across 4 compound switches with Shared y-scale on (`extra/log.txt`, `extra/02`).
- #2 five-row compound list: fixed at 1000 px tall (11 rows, `05`). It overshoots at 768 (issue 1 above).
- #3 no compound title: fixed. The header reads "Pyruvate tR 7.09 · 30 samples" and switches to "1 of 30 selected" (`05`, `06`).
- #4 Baseline correction filed under Display: fixed in the sidebar. The Peak window summary reads "tR 7.09 · Baseline on". The View menu still lists it (issue 7).
- #5 sidebar summary charts: partly fixed. The chip key is added and hover names exist (issue 3).
- #6 popup formats: fixed (`12`).
- #7 sample list looked like a selection: fixed. Checkboxes, "k shown · n match", and order kept (`28`, `extra/log.txt`).
- #8 detailed view: mostly fixed (`10`). See issue 9.
- #9 Settings footer and wide fields: fixed (`15_*`).
- #10 vague labels: fixed. "Apply window", the sidebar wording in Settings, and the status bar deconvolution item is linked (commit 0d4b336c).
- #11 Add Compound errors: fixed. All errors show together, the form scrolls, and offsets use placeholders (`18`).
- #12 narrow-width fraying: legend chips wrap and badges move below the caption. The Identity giant blocks remain (issue 8).
- Also new: complete dark mode with live switching, dialogs that shrink on short screens (`linux-dark-150pct-1280x800/18`), docs that render (`16`), and a transparent, theme-coloured logo (`linux-dark/20`).

**Regressed:**
- Short or scaled screens: the inspector now loses to the browse floor (issue 1). In round 1 the opposite priority at least kept Peak window usable.
- A filtered compound list wastes space while Samples scrolls (issue 2).
- Two names now exist for each review command (issue 4).

**Lost functionality:** none found. Checked against `git diff origin/main...6fc71eb5 -- src/manic/ui` and live:
- File menu: all 11 items and shortcuts, unchanged (`main_window.py:280-353`).
- MANIC/Help menu: all 5 items.
- Plot context menu: all 9 entries with the Curve fit submenu (`09_*menu`, `extra/11_*ctx`). They are also in the new Review menu.
- Compound list context menu: all 5 entries (`compound_list_widget.py:107-148`).
- Sample list context menu: Delete and Recover, plus new Show only/Hide/Show all (`sample_list_widget.py:157-199`). ExtendedSelection is kept, and Space toggles the checked rows.
- Integration: Reset and Apply. "Update tR Window" is now "Apply window".
- Display toggles: all three, in the sidebar and the View menu.
- Settings: all pages, Apply to all compounds and per-sample overrides. Reset and Save are now "Discard changes" and "Save this page".
- Detailed view: Reset, Pan and Zoom are now one set for all three charts, the same function with fewer copies.
- Popups: both expand buttons and double-click.
- Process External Data and Check Data Setup.

```json
{"F1": 8, "F2": 6, "F3": 8, "F4": 7, "F5": 8, "F6": 7, "F7": 8, "F8": 8, "overall": 7.5}
```
