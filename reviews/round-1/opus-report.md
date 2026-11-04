# MANIC UI/UX review, round 1 (re-rating at 9a09a4c), reviewer: opus

Scope: macOS, light mode only. Dark mode and Windows are not in this commit. Evidence comes from the round-1 tour (`shots/NN_*.png`) and from my own driver, `opus/drive.py`, which writes to `opus/extra/NN_*.png` and logs to `opus/extra/log.txt`. The driver tested drag and drop, the status rows, ⌘F, filter plus ↓/Return, ⌘[ / ⌘], grid ⌘A/Esc/arrows/Space/Return, double-click, density, 1280 and 1024 widths, settings dirty state and Add Compound validation.

## Verdict

This is a real redesign, not a reskin. Every structural problem from round 0 has been addressed:
- The empty window is now a numbered start panel.
- The sidebar has a searchable compound list and plain-word status rows.
- Red is kept for failures.
- Tiles are cards with readable ticks and QC badges.
- The popups show sample names.
- Dialogs share one pattern.
- The grid answers the keyboard.

Nothing was lost. Every menu item, context-menu command, settings page and integration control from round 0 is still reachable. Several now have a second path, such as the View menu with shortcuts, Enter for the detailed view and drag and drop.

Three things still keep it short of polished:
- One new state bug: the Display summary tells the user "No baseline" while baseline correction is on.
- Once data loads, the compound list, the primary navigation, still gets only 5 rows, because the inspector claims the sidebar first. The grid has no compound title either.
- The detailed view and the sidebar summary charts still look like the old app.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 7 | System font throughout (the hard-coded Arial is gone), tokenised palette (`theme.py`), neutral secondary buttons, card tiles with consistent captions (`05_labelled_grid.png`, `16_add_compound`, `18_about`). Held back by the unlabeled stripe charts in the sidebar, the matplotlib-default detailed view (`09`), the all-blue sample list (`24`) and the 8px button misalignment in the Settings footer (`14_settings__*`). |
| F2 | Layout and hierarchy | 6 | Clear Data / Compounds / Samples / Peak window / Display / Summary order, and a grid header with legend, count and density (`05`). But after loading, the compound list shrinks to 5 rows, or 3 with Samples open (`05`, `19`, `24`; `left_toolbar.py:355-363`, `BROWSE_MIN_HEIGHT = 240` at `:43`), Total Abundance is still below the fold, and nothing above the grid names the compound. |
| F3 | Onboarding and workflow clarity | 7 | Two-step start panel with state, shortcuts, Recent, a drop hint and a Quick Start link (`02`, `03`). The status rows are clickable (verified: "Raw data" triggers the load action). Plain status bar ("No data loaded. Start by loading a compound list."). Remaining jargon: "tR window" + "Update", and "Deconvolution level 4 · balanced noise gate". |
| F4 | Consistency and polish | 7 | One dialog kit (`dialog_kit.py`) and one "X — MANIC" title pattern. About is a proper dialog (`18`). Checklist has Apply as primary (`04`). Flaws: Discard and Save sit at y=676 and y=668 on every Settings page (`settings_window.py:843-860`, measured in `log.txt`). The Settings text points to "the toolbar", which no longer exists (`settings_window.py:433`). The sample count ignores the filter while the compound count respects it (`24`). The detailed view uses its own idiom (`09`). |
| F5 | Feedback and state | 6 | Big gains: accent border and caption on selected tiles, "1 of 30 selected" in the header and status bar (`06`, `07`), a dashed focus ring (`10`), a QC fail tint plus "Not detected" badges (`23`), dirty dots on Settings pages (`opus/extra/11_settings_dirty_page.png`), inline validation (`opus/extra/12_*`), and a toast that no longer covers plots. Docked for a wrong-state indicator: the Display summary contradicts the checkbox (`opus/extra/02_display_expanded.png`; `left_toolbar.py:547-558`). |
| F6 | Efficiency and flexibility | 7 | Verified live: ⌘F focuses the filter, ↓ in the filter moves the compound, Return hands focus to the list, ⌘[ / ⌘] step within the filtered set, grid ⌘A/Esc/arrows/Space/Return, double-click opens the detailed view without toggling selection, View menu toggles with ⌘⇧B/Y/P, Compact/Comfortable persisted in QSettings, drop a CSV or folder. Readable at 1024×700 (`opus/extra/09`). Held back by the 5-row compound list and by re-selecting a sample moving it to the end of the grid (`opus/extra/07`, `08`). |
| F7 | Data visualisation | 7 | Tiles have 4 ticks at 2 decimals, the exponent sits in the card corner and the caption is bold. The popups show every sample name with value labels (`11`, `12`). The QC colour key is in the header and under the Identity grid (`21`, `23`). Remaining: mixed number formats in the popup ("6.22e-05", "0.000199", "1"), no legend or names on the sidebar stripe charts, overlapping m/z labels and default styling in the detailed view (`09`), and two giant blocks in the Identity chart when one sample is selected (`22`). |
| F8 | Modern feel | 7 | The main window and dialogs now read as considered, current software (start panel, segmented density control, cards, quiet hierarchy). The detailed view and sidebar charts still feel like the old app. |

Overall: (7+6+7+7+6+7+7+7)/8 = 6.75 → **6.8** (round 0: 3.8)

## Top 12 issues, ranked by user impact

1. **The Display summary contradicts the actual state.**
   - Where: `opus/extra/02_display_expanded.png`, where "Baseline correction" is checked and the header says "No baseline · Own scale". Driver log: Pyruvate through Valine all have DB baseline=1 and checkbox=True, but the summary reads "No baseline". `left_toolbar.py:547-558` sets the checkbox with signals blocked, so `_refresh_display_summary` (`:286-299`) never runs. `_commit_y_scale_policy` (`:582-595`) has the same blind spot.
   - Impact: the section is collapsed by default, so the summary is the only visible state for a setting that changes peak areas.
   - Fix: call `self._refresh_display_summary()` after every blocked `setChecked` (both helpers). Add a test that switches compounds and asserts the summary matches the checkboxes.
   - Gain: F5 +1, F4 +0.5.

2. **The compound list collapses to 5 rows once data loads, or 3 with Samples open.**
   - Where: `05`, `19_compact_1280x800.png`, `24`, `opus/extra/07`. `fit_inspector` (`left_toolbar.py:355-363`) gives the inspector its full minimum height first, and browse falls back to 240px.
   - Impact: this is round 0's #1 issue, only partly fixed. Before data loads the list fills the sidebar (`03`), then it shrinks exactly when the user starts working.
   - Fix: reverse the priority. Browse gets at least the larger of about 10 rows and 45% of the height, and the inspector scrolls. Make Peak window and Summary collapsible like Display, and remember the user's split in QSettings.
   - Gain: F2 +1, F6 +0.5.

3. **Nothing above the grid names the compound being reviewed.**
   - Where: `05`, `10`, `21`. The round-0 "Compound: Pyruvate" pill was removed. Now the only cues are the list highlight, which can scroll out of view (`03_filter_leu` once the filter clears), and 12px status bar text.
   - Fix: put the compound name as a 15–16px semibold title at the left of the grid header (graphs.py header, near `:214`), with "tR 7.09 · 30 samples" as a hint, ahead of the legend chips.
   - Gain: F2 +0.5, F5 +0.5.

4. **Baseline correction is filed under "Display" but changes integration.**
   - Where: `opus/extra/02`. The tooltip at `left_toolbar.py:191-194` says it "subtracts the area under this baseline from the peak area", and it is stored per compound. Shared y-scale and Scale to selected peak really are view options.
   - Fix: move Baseline correction into the Peak window section, next to the offsets, as a per-compound switch. Keep Display for the two y-scale options. That also makes issue 1 less dangerous.
   - Gain: F3 +0.5, F2 +0.5.

5. **The sidebar summary charts still can't be read in place.**
   - Where: `05`, `10`, `21`. Label Incorporation is 30 unlabeled stripes with no isotopologue key and no sample names. Total Abundance is cut off at the bottom of the sidebar at 1600×1000.
   - Fix:
     - Add the M+0…M+n chip row (as in the popup, `12`) under the Label Incorporation header.
     - Add a hover tooltip with sample and value.
     - Make the Summary section collapsible, so issue 2's space can come from here.
   - Gain: F7 +0.5, F2 +0.5.

6. **The popup value labels use mixed formats.**
   - Where: `11_abundance_popup`: "0.91", "0.893", "1", "6.22e-05", "0.000199" under a "×10⁴" axis. Bio_018 and Bio_020 have no label at all. The footer says "Hover a bar for its value" even though every value is printed (`chart_popup_dialog.py:203`).
   - Fix: format every label in the axis unit with fixed precision ("0.91", "<0.01"), print "0" or "—" for empty bars, and drop the hover hint when labels are shown.
   - Gain: F7 +0.5, F4 +0.25.

7. **The sample list works as a visibility filter but looks like a selection.**
   - Where: `24`, `opus/extra/07`.
     - Every visible row is solid blue.
     - The summary stays "23 · all shown" while a filter is active, whereas compounds show "12 of 29".
     - Deselecting and reselecting a sample moves it to the end of the grid (Bio_001 after Std_MM_02 in `opus/extra/07`, `08`). The order comes from `selectedItems()`, so it follows selection order (`left_toolbar.py:506-514`). This is pre-existing but now easier to hit.
   - Fix: give each row a checkbox for "shown", keep the grid in list order, and use the summary "k shown · n match filter".
   - Gain: F5 +0.5, F6 +0.5.

8. **The detailed view is the one screen the redesign didn't reach.**
   - Where: `09`, `opus/extra/05_*DetailedPlotDialog.png`.
     - Three identical Reset/Pan/Zoom bars.
     - Dark-green TIC and navy spectrum outside the palette.
     - Overlapping m/z labels (173.97 / 174.99 / 175.98).
     - A 7px legend.
     - A footer separated with "|".
   - Fix: use one toolbar for all three axes and the `chart_style` tokens for line colours. Label only the top-N spectrum peaks with collision avoidance. Write the footer as "tR 7.090 min · m/z 174.0000 · M+0…M+3".
   - Gain: F7 +0.5, F1 +0.5, F8 +0.5.

9. **The Settings footer is misaligned and number fields stretch to full width.**
   - Where: every `14_settings__*` page and `opus/extra/11`. Discard is at (604, 676) and Save at (740, 668), both 28px tall (`settings_window.py:843-860`, `AlignBottom` combined with different role margins in `style.qss`). A one-number field ("0.200") spans 466px.
   - Fix: remove the per-widget `AlignBottom` or equalise button margins for the secondary and primary roles. Cap numeric fields at about 120px.
   - Gain: F4 +0.5, F1 +0.25.

10. **Some labels are vague or out of date.**
    - "Update tR Window" became just "Update" (`integration_window_widget.py:313`).
    - The Internal Standard settings page says "Select an internal standard in the toolbar" (`settings_window.py:433`), but the control is now the sidebar "Internal standard" row.
    - The status bar deconvolution summary is not clickable.
    - Fix:
      - Rename the button "Re-extract", or label the row "Search window ±0.2 min".
      - Fix the copy to "…in the sidebar (Internal standard row)".
      - Make the status item open Settings › Deconvolution.
    - Gain: F3 +0.5.

11. **Add Compound reports one error at a time and still pre-fills zeros.**
    - Where: `opus/extra/12_add_compound_empty_submit.png`. Only "Enter a compound name." is shown, although tR and Mass0 are empty too (`add_compound_dialog.py:154-170`). Offsets show "0.0000", Atoms and the derivatisation groups show "0".
    - Fix: validate every required field on submit and flag them all. Use placeholders for the offsets.
    - Gain: F3 +0.25, F4 +0.25.

12. **The narrow-width and edge cases fray.**
    - At 1024 wide the legend chips elide the m/z ("M+0 m/…", `opus/extra/09`).
    - With one sample selected, the Identity chart becomes two giant blocks (`22`).
    - Badges truncate captions ("Sample_05_rt_sh…", `21`).
    - The Recent row's "List" label sits off its baseline (`03`).
    - Fix: drop "m/z" before the number at narrow widths, or wrap the chip row. Cap the Identity cell height. Put the badge on its own line, or as a dot, when the caption would elide.
    - Gain: F7 +0.25, F6 +0.25.

## Re-rating comparison

**Improved (round-0 issue → state now):**
- #1 lists and search: filter field with count, ⌘F, ↓/Return, ⌘[ / ⌘]. The list gained 2 rows but is still short (issue 2).
- #2 sidebar structure: sections with headings, no per-row borders, display toggles collapsible and mirrored in a View menu.
- #3 empty state: the start panel fully addresses it.
- #4 popups: every sample name is shown, with values.
- #5 red overuse: fixed. Buttons are styled by role, not text.
- #6 status pills: replaced with plain rows that act as controls.
- #7 QC encoding: header key, Identity key and per-tile badges and tint.
- #8 tile axes: fixed. The 1024 width is readable.
- #9 selection visibility: fixed.
- #10 power-user paths: all delivered and verified live.
- #11 dialog template: delivered.
- #12 status bar and toast: delivered, though the status item is not clickable.

**Regressed:**
- New bug: the Display summary shows a stale baseline and scale state (issue 1).
- Prominence regression: the current compound name lost its always-visible slot (issue 3).
- The label "Update tR Window" became "Update" (issue 10).

**Lost functionality:** none found. Checked against the baseline source and live:
- File menu: all 11 items and the shortcuts (⌘O, ⇧⌘O, ⌘I, ⌘E, ⌘Q) are present.
- MANIC/Help menu: all 5 items (Settings, Documentation, Check Data Setup, Check for Updates, About).
- Plot context menu: all 9 entries, now with shortcut hints (`08_plot_context_menu__menu.png` matches round 0 item for item).
- Compound list context menu: Add Compound, Select as Internal Standard, Delete, Recover Deleted, Clear Internal Standard (`compound_list_widget.py:107-152`).
- Sample list context menu: Delete and Recover (`sample_list_widget.py:117-136`).
- Integration: Apply, Reset and tR window update.
- All three display toggles.
- Double-click on the sidebar charts, plus new expand buttons.
- The Docs and Settings icons.
- All six Settings pages, including per-sample curve-fit overrides and Remove all overrides.
- Process External Data.

Harder to reach:
- The display toggles are one click deeper, behind a collapsed section. The View menu shortcuts offset this.
- The compound name moved to the status bar.

**Tour caveat for later rounds:** `charts()` in `scripts/ui_tour.py:142-148` sorts views by `(v.y(), v.x())`. Views are now nested in cards, so those coordinates are card-local and nearly equal. `views[i]` for i>0 is not reliably the i-th tile. It held for steps 06/07 here, but in my driver `views[6]` was Bio_024. Sort by `v.mapTo(graph_view, QPoint()).y()/x()` instead. The blank documentation capture (QWebEngine, `grab()`) is the same false positive as in round 0.

**What to check once dark mode and Windows land:**
- Dark mode:
  - Matplotlib tiles and the detailed view (`matplotlib_plot_widget.py` still has 4 literal colours) and Qt Charts backgrounds must follow the tokens.
  - The QC-fail pink tint and the grey "Not detected" card must hold contrast.
  - The MANIC logo on a dark background in the start panel and About.
  - Focus and selection accent contrast on dark cards.
  - The documentation viewer's 22 literal colours.
- Windows:
  - Ctrl rather than ⌘ in the start panel buttons and context-menu hints (`shortcut_text` looks platform-aware; the grid tooltip at `graphs.py:210` hard-codes "⌘/Ctrl").
  - Segoe UI metrics in the 20px status rows and the 240px browse minimum at 125/150% scaling.
  - The 5px splitter handle at high DPI.
  - The non-native "MANIC" menu title.
  - Native combo arrows inside the token-styled fields.

```json
{"F1": 7, "F2": 6, "F3": 7, "F4": 7, "F5": 6, "F6": 7, "F7": 7, "F8": 7, "overall": 6.8}
```
