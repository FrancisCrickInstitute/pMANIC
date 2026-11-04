# MANIC UI/UX review, round 3 (re-rating at 795ecbe6), reviewer: opus

Evidence:
- I viewed every PNG in the round-3 tour: `shots/linux-light/`, `linux-dark/`, `linux-light-150pct-1280x800/` and `linux-dark-150pct-1280x800/`. A name below without a folder is from `linux-light`. `150L/` and `150D/` are short for the two 150% folders.
- My own driver is `review-r3-opus/drive.py` (it imports a copy of the tour). It writes `extra/NN_*.png` and `extra/log.txt`, and covered:
  - the sidebar Summary with three plots selected
  - inspector scroll across compound switches
  - grid keys → ↓ Space Return
  - Internal standard = Glycine, then the Below threshold badge and the Review menu with 8 plots selected
  - a popup row click that jumps to its plot
  - 1280×720 and 1024×640 with Samples open and closed
  - the unlabelled QC-fail sample: Review menu, detailed view and Summary
- The GUI ran offscreen with Inter. Native tooltips, real focus rings and hover could not be watched; I read those paths in code.

## Verdict

Round 3 fixes the biggest round-2 problem and most of the small ones:
- The Peak window now stays whole on short and scaled screens. At 150% with Samples open, every integration control is visible (`150L/33`, `150D/29`).
- Collapsing Samples gives the space back straight away (`extra/log.txt`: `[288,281]` → `[268,301]`).
- The browse pane now splits by content (`150D/29`).
- The Review menu and the plot menu now share one API and one wording.
- Both popups list samples top-down in grid order, and clicking a row jumps to that plot (verified: row 20 → `Bio_021` selected).
- The sidebar charts mark the selected samples and use nice ticks (`extra/03`).
- There is a real empty state when no sample is shown (`34`).
- The inspector scroll resets on a compound change.

One new defect stands out. On the 150% Windows-laptop stand-in, the post-load "Check your data setup" dialog overlaps its own text and clips its last line, in both schemes (`150L/04_…__PostLoadChecklistDialog`, `150D/15`). Round 2 rendered this dialog cleanly (`round-2/…150pct…/04`). The cause is the new "Changing a pattern" block, and this is the first dialog a laptop user sees after loading data.

The rest is polish: raw enum text in the detailed legend, a few naming leftovers, and Identity charts that are heavy when nothing is assessed.

Nothing from `origin/main` is lost.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 8 | One token system holds across light, dark and 150% (`05`, `linux-dark/05`, `150D/05`). The detailed view has a proper "Reset all" button and a Pan/Zoom segmented control (`11`, `150D/11`). Not detected tiles are tinted throughout with dimmed traces (`24`, `linux-dark/24`), and popup value labels have a backing (`13`). Held back by the overlapping 150% checklist (`150L/04_…Dialog`), full-width grey "?" slabs in the Identity popup (`31`), and the "174.99" label sitting on its own bar (`11`). |
| F2 | Layout and hierarchy | 7 | Fixed: the Peak window is whole at 1024×768 and 150% (`33`, `150L/33`). The lists share by content (`150D/29`: 3 compounds, then Samples, no dead space). Summary starts collapsed when it won't fit (`05`). Remaining: the 150% checklist has broken layout (`post_load_checklist_dialog.py:166-197`, no scroll area). At 1280×720 with Samples open, the lists get 3 compound rows and 2 sample rows (`extra/12`). There is a ~120 px dead band between the Identity and Total Abundance charts (`extra/18`). |
| F3 | Onboarding and workflow clarity | 8 | The start panel points to the Review menu (`02`). Quick Start has a "Review from the keyboard" table and uses the menu's own labels (`17`, `150D/17`). The checklist names the compound list file, with Open File / Show in Folder and exact reload steps (`04_…Dialog`), and its amber wording now matches Settings. Docked for the wall of numbered text in that dialog and for "(not_assessed)" in the legend (`32`; `detailed_plot_dialog.py:736`). |
| F4 | Consistency and polish | 8 | One review API: Inspect *sample*…, Title Case and counts are the same in both menus (`09_*menu`, `10_*menu`; `graphs.py:905-952`). Baseline Correction moved to Review (`10_*menu`). The Internal standard menu shows a check (`30`), and the menu is titled Help (`main_window.py:373`). Leftovers: "Select All" (`graphs.py:825`) vs "Select All Plots" (`main_window.py:550`), with the two menus in different orders. Missing ratios are blank rows in the label popup but "—" in the abundance popup (`150D/14` vs `150D/13`). |
| F5 | Feedback and state | 8 | Verified: "No samples shown" with a Show all button and a disabled Apply that says "Nothing to apply to." (`34`). Selected samples are accent-marked in the sidebar charts (`extra/03`). Identity cells carry ✓/×/?/– marks (`31`, `extra/18`). "Below threshold" shows as an amber tile tint (`extra/07`). The Review menu counts what it acts on ("Mark 8 Peaks as Bad", `extra/log.txt`), and popups mark the current row. The QC fail tint reads in dark (`150D/24`). Not detected stays subtle in dark (`150D/24`). |
| F6 | Efficiency and flexibility | 8 | Verified live: → ↓ Space Return drive the grid and Return opens Inspect (`extra/05_*Detailed`). Popup rows jump to plots, and the inspector scroll resets on Next Compound (`extra/log.txt` 341→0). Splitter refits on Samples collapse. Batch Accept enables on the eligible subset (`graphs.py:930-940`). On a common 1920×1080 laptop at 150% (1280×720 logical), Samples open leaves 2 visible sample rows (`extra/12`). |
| F7 | Data visualisation | 8 | Popups read in grid order, with backed labels, "<0.01" and "—" (`13`). Sidebar charts have nice ticks and selection marks (`extra/03`). Identity rows are capped (`31`). Spectrum labels show the compound's own ions (`extra/17`: 115.98, 147.03, 72.97). Remaining: an all-unassessed Identity popup is a wall of grey "?" (`31`). The chip reads "expected — —" (`channel_chips.py:29`). Sidebar charts are still nameless stripes (`24`). The labelled spectrum labels only 174.99 for M+0…M+3 (`11`). |
| F8 | Modern feel | 8 | Live scheme switching holds selection, also inside the detailed view (`08_*`, `32`). The empty state, segmented controls, cards and quiet type all read as modern, considered software. The overlapping checklist is the one place it feels unfinished on a laptop. |

Overall: (8+7+8+8+8+8+8+8)/8 = 7.875 → **7.9** (round 2: 7.5, round 1: 6.8)

Per-platform limits:
- macOS: not verified. This covers:
  - the native menu bar, where Settings now sits under File (macOS normally moves a role-tagged Settings to the app menu; check `main_window.py:348`)
  - the ⌘ glyphs
  - Aqua against Fusion metrics
- Windows: not verified. This covers Segoe UI wrap widths in the checklist (likely worse than Inter, so issue 1 probably reproduces), 125% rounding, and the Help menu placement.
- The code is platform-neutral: `QKeySequence` throughout, Fusion, tokens.

## Top 12 issues, ranked by user impact

1. **The post-load checklist overlaps and clips at 150%. This is a regression.**
   - Where: `150L/04_labelled_loaded_checklist__PostLoadChecklistDialog`, `150L/15`, `150D/04`, `150D/15` and `150L/23_…Dialog`. The "Each pattern picks…" hint overprints the third table row. The line "Change patterns before you review…" is cut off at the bottom.
   - Cause: `post_load_checklist_dialog.py:166-197`. The table stretch, the word-wrapped hint labels and the new `_CHANGE_PATTERN_STEPS` block share one layout with no scroll area, while the dialog is capped to the screen height.
   - Fix:
     - Put everything between the header and the button row in a `QScrollArea`, as Add Compound already does (`150D/18`).
     - Or give the MM table a fixed minimum of about 4 rows and move "Changing a pattern" behind a disclosure ("How do I change a pattern?").
     - Add the 150% checklist to the tour assertions.
   - Gain: F2 +0.5, F4 +0.25, F1 +0.25.

2. **On 1280×720 the browse lists are cramped once Samples opens.**
   - Where: `extra/12_w1280x720_samples_open` shows 3 compound rows and 2 sample rows; the splitter is `[288, 281]`. At 1024×640 it drops to 1 row each (`extra/14`). The Peak window is now protected (good), but Display and Summary still take inspector height below it.
   - Fix: when Samples opens on a short window, auto-collapse Summary and Display. Their one-line summaries ("Own scale") already carry the state. Give the freed height to the lists.
   - Gain: F2 +0.25, F6 +0.25.

3. **The detailed-view legend shows a raw enum.**
   - Where: "Qualifier ion 1 m/z 248 (not_assessed)" (`32`, `150L/32`). Code: `detailed_plot_dialog.py:736` uses `assessment.status.value`.
   - Fix: map the status to the same words as the QC key: "validated", "failed", "not assessed".
   - Gain: F3 +0.25, F4 +0.25.

4. **The Identity popup is a wall of grey when nothing is assessed.**
   - Where: `31` and `150D/31`. All 22 cells are full-width grey slabs with "?" or "–", and the chip reads "expected — —" (`channel_chips.py:29`).
   - Fix:
     - When no qualifier for the compound has a ratio and tolerance, replace the grid with one line: "No expected ratios set for Glycine. Add them in Settings › Qualifier Ratios."
     - Render the "–" (absent) cells as empty outlines, not filled grey.
     - Write the chip as "no expected ratio".
   - Gain: F7 +0.25, F3 +0.25.

5. **The two review menus still differ in name and order.**
   - Where: the context menu starts with "Select All · Deselect All · Select Only This Sample…" and puts "Inspect" in the middle (`09_*menu`; `graphs.py:825-856`). The Review menu starts with "Inspect" and says "Select All Plots" (`10_*menu`; `main_window.py:542-553`).
   - Fix: use "Select All Plots" in both and keep the same group order. "Select Only This Sample" can stay context-only.
   - Gain: F4 +0.25.

6. **Sidebar summary charts still can't name a sample in place.**
   - Where: `24` and `extra/03`: 11 or 30 nameless stripes, captioned "Hover or enlarge for sample names" (`sidebar_widgets.py:63`). Total Abundance does show names when the list is short (`extra/18`), so the two charts behave differently.
   - Fix: when the row height allows about 9 px text, show names as Total Abundance does. Otherwise label only the selected samples next to their accent marks.
   - Gain: F7 +0.25.

7. **The label popup leaves missing samples blank.**
   - Where: Bio_018 and Bio_020 are empty rows in `150D/14`, but show "—" in the abundance popup (`150D/13`).
   - Fix: draw the same "—" marker from `chart_popup_dialog.py:136-140` for a stacked row with no data.
   - Gain: F7 +0.1, F4 +0.1.

8. **Dead band in the Summary section.**
   - Where: `extra/18_unl_summary` has about 120 px of empty space between the Identity chart (1 sample) and Total Abundance.
   - Fix: give the Identity chart a height that follows its rows, with no stretch, when the rows are capped.
   - Gain: F2 +0.1.

9. **The Identity sidebar chart filters to the selection, while Total Abundance highlights it.**
   - Where: with one sample selected, Identity shows "1 sample · 1 sample failed" with only that row. Total Abundance shows all 11 with the selected bar in accent (`extra/18`).
   - Fix: pick one rule. Highlighting, as Abundance does, keeps context.
   - Gain: F4 +0.1, F5 +0.1.

10. **Spectrum labelling in labelled mode.**
    - Where: only "174.99" is labelled, and it sits on top of the bar. M+1…M+3 have no labels (`11`, `150D/11`).
    - Fix: for labelled compounds, label M+0…M+n compactly ("M+0…M+3") or offset the label above the tallest bar.
    - Gain: F7 +0.1.

11. **Not detected is faint in dark.**
    - Where: `150D/24` and `linux-dark/24`. The tint is about 3% lighter than the card, and the "Not detected" badge is plain grey text.
    - Fix: give the badge a pill background, as "QC fail" effectively has through its colour, and raise the dark tint a step.
    - Gain: F5 +0.1.

12. **The checklist dialog reads as a manual.**
    - Where: `04_…Dialog`. Below a working table there are seven lines of numbered File → steps.
    - Fix: keep "Compound list: compounds.csv · Open File · Show in Folder". Fold the steps into "How do I change a pattern?" that expands or links to the user guide anchor. This also helps issue 1.
    - Gain: F3 +0.25, F1 +0.1.

## Re-rating comparison

**Round-2 issues, status:**
1. Peak window sliver on short or scaled screens: **fixed.** The Peak window is whole at 1024×768, at 150%, at 1280×720 and at 1024×640 (`33`, `150L/33`, `extra/12`, `extra/14`). Collapsing Samples refits at once (`extra/log.txt`). The cost moved to the lists (issue 2).
2. Browse pane split by fixed stretch: **fixed.** The split now follows content (`150D/29`, `left_toolbar.py:446-481`).
3. Sidebar summary charts: **partly fixed.** Nice ticks, accent marks on selected samples, and Summary collapsed when short are all done (`extra/03`, `05`). Names in place are still missing (issue 6).
4. Review menu and context menu naming: **mostly fixed.** One API and one label set (Inspect, Accept Peak (Below Threshold), Mark Peak as Bad, Curve Fit). "Select All" vs "Select All Plots" and the order remain (issue 5).
5. Opposite popup sort: **fixed.** Both read top-down in grid order (`13`, `14`).
6. Checklist colour copy: **fixed.** It now says "amber Below threshold badge" (`04_…Dialog`).
7. Baseline Correction in the View menu: **fixed.** It is in the Review menu with Ctrl+Shift+B (`10_*menu`).
8. Giant Identity blocks: **fixed** for one sample (`extra/18`, row height capped). A new heaviness appears when nothing is assessed (issue 4).
9. Detailed view loose ends: **fixed.** Pan/Zoom is a segmented control, there is per-chart reset by double-click or menu (`matplotlib_plot_widget.py:627-640`), and compound ions are labelled (`extra/17`). One labelled-mode nit remains (issue 10).
10. Not detected half-tint: **fixed in light** (`24`). Still faint in dark (issue 11).
11. Popup labels struck by gridlines: **fixed.** Labels have a backing (`13`).
12. Small menu and status gaps: **fixed.** The Internal standard menu is checked (`30`), the menu is titled Help with Settings under File, and the inspector scroll resets on compound change (`extra/log.txt`).

**Regressed:**
- The post-load checklist at 150% (issue 1), introduced by the new "Changing a pattern" block (commit d6a6e011). Round 2 rendered the same dialog cleanly at 150%.
- Short-window list height (issue 2) is the trade-off of fixing the Peak window. It is milder than the round-2 problem.

**Lost functionality:** none found. I checked `git diff origin/main...795ecbe6 -- src/manic/ui` and the running app:
- File menu: all 11 items and their shortcuts. Settings moved from the "MANIC" menu to File with the same shortcuts (`main_window.py:348-354`).
- Help: Documentation, Check Data Setup, Check for Updates and About.
- Plot context menu: everything on main is still there. "View Detailed…" is now "Inspect *sample*…", the curve-fit submenu is kept, and every entry is also in Review (`09_*menu`, `extra/09_*ctx`).
- Compound list menu: all 5 entries, unchanged (`compound_list_widget.py:107-152`).
- Sample list menu: Delete and Recover, plus Show only, Hide and Show all (`sample_list_widget.py:140-176`).
- Integration: Reset, Apply and Apply window.
- Display: Shared Y-Scale and Scale to Selected Peak, in the sidebar and in View. Baseline is in Peak window and Review.
- Detailed view: per-chart reset is back by double-click or context menu, next to Reset all, Pan and Zoom.
- Settings: every page, Apply to all compounds, and per-sample curve-fit overrides (`150D/16_page5`).
- Popups: both expand buttons, now also with row → plot.
- Process External Data, Add Compound and About.
- Multi-select (click, Ctrl-click, Ctrl+A, Esc) and peak verdicts. Batch Accept now acts on the eligible subset.

```json
{"F1": 8, "F2": 7, "F3": 8, "F4": 8, "F5": 8, "F6": 8, "F7": 8, "F8": 8, "overall": 7.9}
```
