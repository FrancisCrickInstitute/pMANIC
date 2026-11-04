# MANIC UI/UX review, round 0 (baseline), reviewer: opus

## Verdict

MANIC today is a capable in-house science tool with the right core idea: a small-multiples grid of every sample for one compound. Everything around that grid looks and works like typical clunky lab software. The left sidebar stacks eleven bordered boxes. The two lists you navigate with (30 samples, 95 compounds) are three rows tall and have no search. Red marks Cancel, Close, Reset, "Int Std: none" and QC failure alike, so it stops meaning anything. Before anything is loaded the empty window gives no next step, and the summary popups whose job is to show sample names show "…" instead. Settings and the detailed view are the most polished parts. The rest needs a structural redesign of the sidebar and dialogs, not a coat of paint.

Capture caveats (not scored as defects, verified by driving the app):
- `15_documentation__DocumentationViewer.png` is blank only because `widget.grab()` cannot read QWebEngine. A screen grab after load renders the Quick Start correctly (`opus/extra/docs_screen.png`).
- The garbled legend chips after a compound switch ("M+0 m/z 1̶7̶4̶", stale M+2..M+4 chips on a two-channel compound, `opus/extra/legend_valine_after_switch.png`, `opus/extra/narrow_1024x700.png`) come from `channel_chips.py:88-89`. That code removes chips with `deleteLater()`, and the tour's `processEvents()` pump never runs deferred deletes. A real event loop clears them. Hiding each chip before `deleteLater()` would make it robust. The tour should also call `QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)` in `pump()` so later rounds don't show this false positive.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 4 | Tiny 9–10px pill text and pastel red/green pills (`02_empty_labelled.png`), saturated Bootstrap blue/red buttons, a border on every checkbox row, and 19 hard-coded `QFont("Arial")` uses in charts against a system font elsewhere (`graphs.py:1387`, `chart_popup_dialog.py:420`). Settings (`14_settings__*`) is clean. |
| F2 | Layout and hierarchy | 4 | The grid uses space well (`05_labelled_grid.png`). The sidebar gives the same weight to status, 3-row lists, an always-open integration form, three toggles and two squeezed charts. It overflows at 1600×1000: Total Abundance is clipped and its axis is only visible after scrolling (`21_unlabelled_grid.png`, `opus/extra/sidebar_bottom.png`). |
| F3 | Onboarding and workflow clarity | 3 | The empty window is a blank canvas plus non-clickable red pills, and the menu bar is the only path (`02_empty_labelled.png`, `loaded_data_widget.py`). Jargon: "tR Window", "Gate Balanced", "MM pattern". Docs and Quick Start are good but hidden behind an unlabeled book icon. |
| F4 | Consistency and polish | 4 | Cancel and Close are red in every dialog because the stylesheet matches button text (`style.qss:271-279`, `style.qss:378-386`). Alignment varies from dialog to dialog (`16_add_compound`, `17_process_external`). The About box is all bold and shows the version twice (`18_about`). Window titles follow three patterns: "MANIC - Identity", "MANIC Documentation", "MANIC v5.0.0 — Labelled analysis". |
| F5 | Feedback and state | 4 | The selected tile gets only a 50-alpha green wash (`colors.py:23`, `06_sample_selected.png`). The sample list shows every row grey, so selection can't be read from it. The status bar reports only deconvolution jargon. The toast covers the last tile (`05`). An optional internal standard shows as red "Not set" (`04_…Checklist`). |
| F6 | Efficiency and flexibility | 3 | There is no compound search across 95 compounds in a 3-row list (`compound_list_widget.py:29`, `sample_list_widget.py:27`). The grid ignores Ctrl+A, arrows and Esc (verified: Ctrl+A had no effect). Double-clicking a tile does nothing; the detailed view is right-click only. Sidebar charts open their popup only on an undiscoverable double-click. At 1024 wide the x ticks elide to "9…." (`opus/extra/narrow_1024x700.png`). Positives: rubber-band select, Open Recent, menu shortcuts, arrow keys in the compound list. |
| F7 | Data visualisation | 5 | Small multiples, a consistent isotopologue palette and legend chips are good, and the detailed view (`09`) is solid. Problems: 5 x ticks with 3 decimals per tile; ×10ⁿ collides with the top y tick; popups print "…" for every sample name (`11`, `12`, `opus/extra/60_unl__ChartPopupDialog.png`); the legend shows qualifiers grey while tiles draw them green or red (`21`, `23`); the sidebar Identity grid has no key. |
| F8 | Modern feel | 3 | Overall it reads as a 2010s lab tool. The coloured-pill status, Bootstrap buttons, boxed checkbox rows, bare QMessageBox About and grey-on-grey list selection all add to that. |

Overall: (4+4+3+4+4+3+5+3)/8 = 3.75 → **3.8**

## Top 12 issues, ranked by user impact

1. **Primary navigation lists are 3 rows tall with no search.**
   - Where: `05_labelled_grid.png`, `10_another_compound.png`; `compound_list_widget.py:29-30`, `sample_list_widget.py:27-28` (max height 150px).
   - Impact: with 95 compounds the user scrolls a three-row window one row at a time, and each list cuts its fourth row in half.
   - Fix: make the compound list the tallest element in the sidebar, flexing to fill the space with a minimum of about 10 rows, and put a filter field above it (type to filter, Enter to select, ⌘F to focus). Show the row count in the list header ("Compounds 95"). Shrink the sample list into a header such as "Samples 30 · 3 selected" that expands on click, because the grid already shows samples.
   - Gain: F6 +2, F2 +1, F3 +1.

2. **The sidebar is an overloaded column of equal-weight boxes and overflows at 1600×1000.**
   - Where: `02`, `05`, `21`, `opus/extra/sidebar_bottom.png`; `left_toolbar.py:103-283`.
   - Fix: regroup into three sections with headings and no per-row borders:
     - Data: status and lists.
     - Peak window: Left/tR/Right/Apply/Reset plus tR Window, collapsible, with its title showing the scope ("Peak window · 3 selected").
     - Summary: the two charts.
   - Move Baseline correction, Shared y-scale and Scale to selected peak to a compact segmented or toggle row in the grid header next to the legend; they change the plots, so they belong with them. Remove the 1px box around every checkbox.
   - Gain: F2 +2, F1 +1, F8 +1.

3. **The empty and first-run state has no next step.**
   - Where: `02_empty_labelled.png`, `03_compounds_only.png`. The "Compounds" and "Raw Data" pills look like buttons but have no click handler (`loaded_data_widget.py`).
   - Fix: when the grid has no data, fill the plot area with a centred two-step panel:
     - "1 Load compound list… ⌘O", checked once done.
     - "2 Load raw data folder… ⇧⌘O".
     - Below them: Open Recent entries and a "Drop a folder or CSV here" target.
   - In `03` the panel should show step 1 done and step 2 as the primary button. Make the status pills open the same actions.
   - Gain: F3 +3, F8 +1.

4. **The enlarged chart popups hide the sample names they exist to show.**
   - Where: `11_abundance_popup`, `12_label_popup`, `opus/extra/60_unl__ChartPopupDialog.png`. The class docstring says "with sample names visible" (`chart_popup_dialog.py:41`), but `QBarCategoryAxis` elides all 30 labels to "…" (`chart_popup_dialog.py:426-431`).
   - Fix: give each bar a fixed row height (≥20px), size the chart to rows × height inside a QScrollArea, and reserve a left label column at least as wide as the longest sample name. Add a value label at the bar end for Total Abundance.
   - Gain: F7 +1, F5 +0.5.

5. **Red means everything.**
   - Where: Cancel (`16`, `17`, `01`), Close (`11`, `12`), Reset (sidebar), "Int Std: none" pill, "Not set" (`04_…Checklist`), and red bars for not-loaded data. All of these share one red with QC failure and the M+3 trace. Source: text-keyed rules at `style.qss:271-279` and `style.qss:378-386`.
   - Fix: Cancel, Close, Skip and Reset become neutral secondary buttons (light grey fill, dark text). Red stays only for destructive actions (Clear Session, Remove all overrides) and failure verdicts. Show the optional internal standard in neutral grey: "Internal standard: none (optional)". Style buttons by an object name or property, not by their text.
   - Gain: F1 +1, F4 +1, F5 +1.

6. **The status pills are tiny, ambiguous and colour-only.**
   - Where: `02`, `05`; `standard_indicator_widget.py:22-29` (20px high, inline stylesheet, `color: black`).
   - Fix: replace the four pills with a compact data header in normal 12–13px text, for example "Pyruvate · 30 samples · 95 compounds · Int std: none". Use a check or dot icon for loaded/not loaded instead of a red or green fill, and make each item clickable (load data, choose internal standard).
   - Gain: F5 +1, F1 +1, F3 +0.5.

7. **The unlabelled QC encoding is unexplained.**
   - Where: `21_unlabelled_grid.png`, `23_unlabelled_another_compound.png`.
   - The legend chips draw qualifiers grey (`colors.py` `legend_trace_styles`), but tiles draw them green, red or grey by verdict.
   - The sidebar Identity grid has no key and no sample names.
   - Failing samples (Sample_04_ratio_fail, Sample_05_rt_shift) look the same as passing ones at tile level.
   - Fix: put the existing "Validated / Failed / No verdict" key from the popup under the sidebar grid. Label the legend chip "Qualifier 1 · colour = QC". Add a small verdict dot or coloured caption underline to each tile so failures stand out in the grid.
   - Gain: F7 +1, F5 +1.

8. **Tile axes are noisy and break at small sizes.**
   - Where: `05`, `19_compact_1280x800.png`, `opus/extra/narrow_1024x700.png`.
   - Every tile repeats 5 x ticks to 3 decimals ("6.892 6.990 7.088 7.185 7.283"). The ×10⁶ offset overlaps the top y tick. At 1024 wide the ticks elide to "9….". Sample captions are about 9px bold.
   - Fix: show 3 x ticks with 2 decimals, or only the tR tick. Move the exponent into the y-axis or caption ("×10⁶"). Hide y tick labels when Shared y-scale is on. Set captions to 11–12px semibold. Use one chart font family that matches the UI (drop the hard-coded Arial).
   - Gain: F7 +1, F1 +0.5, F6 +0.5.

9. **Selection is hard to see and is not mirrored anywhere.**
   - Where: `06`, `07`; `colors.py:23` (alpha-50 light green), `graphs.py:137`.
   - The sample list paints all rows grey whatever is selected, and nothing outside the "Selected Plots: 3 samples" title says how many are selected.
   - Fix: give the selected tile a 2px accent border plus an accent caption chip. Use the same accent in the sample list. Show "3 of 30 selected" in the status bar with an Esc-to-clear hint.
   - Gain: F5 +1, F1 +0.5.

10. **Power-user paths are missing or hidden.**
    - Where: `08_plot_context_menu__menu.png`, `graphs.py:110-125` (no double-click), `total_abundance_widget.py:253`, `isotopologue_ratio_widget.py:296` (popup on double-click only).
    - Fix:
      - In the grid: Ctrl/⌘+A select all, Esc clear, arrows move focus, Space toggles selection.
      - Double-click a tile to open the detailed view.
      - ↑/↓ or ⌘[ / ⌘] switch compound from anywhere.
      - Add a View menu with checkable Baseline correction, Shared y-scale and Scale to selected peak, each with a shortcut.
      - Show an expand icon on hover over the sidebar charts.
      - List the shortcuts in the context menu.
    - Gain: F6 +2.

11. **Dialogs don't share a template.**
    - Where:
      - `04_…Checklist`: "Skip" renders as the blue primary button and "Apply" as grey.
      - `17_process_external`: input fields start at different x positions and Cancel is red.
      - `16_add_compound`: 14 equal-weight fields, numeric fields prefilled with "0.0000", no grouping.
      - `18_about`: all bold, version shown twice.
      - Window titles use three patterns.
    - Fix: one dialog pattern built on QFormLayout:
      - Left-aligned labels in one column.
      - Primary action on the right, secondary neutral on the left.
      - Default button set explicitly to the primary action.
    - Group Add Compound into Identity (name, formula, label type), Retention (tR, offsets), Mass (m/z, label atoms, derivatisation) and Standards (amounts, MM files), with placeholders instead of zeros. Write the About box as a proper dialog with the logo and normal-weight text. Use "<Dialog> — MANIC" for every window title.
    - Gain: F4 +2, F1 +0.5.

12. **The status bar and toasts waste the feedback channel.**
    - Where: `02` ("Deconvolution: -" with nothing loaded), `05` ("Gate Balanced"), and the toast covering the Std_MM_02 tile in `05` and `06`.
    - Fix:
      - Left of the status bar: data and selection summary.
      - Right: processing settings in plain words ("Peak splitting: auto"). Clicking it opens Settings › Deconvolution.
      - Hide the deconvolution item until a compound is loaded.
      - Anchor toasts bottom-centre above the status bar with a margin, or show them in the status bar, so they never cover a plot.
    - Gain: F5 +1, F3 +0.5.

## Re-rating comparison

Not applicable: round 0 is the baseline.

```json
{"F1": 4, "F2": 4, "F3": 3, "F4": 4, "F5": 4, "F6": 3, "F7": 5, "F8": 3, "overall": 3.8}
```
