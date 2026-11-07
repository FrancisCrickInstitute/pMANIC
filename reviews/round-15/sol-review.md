MANIC scores **9.9/10**. The primary 2560×1410 workspace remains attractive, uncluttered and well suited to chromatogram review. Both datasets completed the load, edit and export workflow. Two small Identity tooltip issues keep this review below 10.0: a cell-to-name transition can lose its tooltip, and cell copy repeats the qualifier identifier. I found no confirmed loss of useful functionality.

| Factor | Score | Justification |
|---|---:|---|
| F1. Visual design | 10 | Restrained typography, spacing and surfaces hold across platforms and appearances. `linux-light-2560x1410/05_labelled_grid.png`; `ci-windows-latest-dark/33_identity_popup__ChartPopupDialog.png`. |
| F2. Layout and hierarchy | 10 | The large workspace gives plots priority and keeps cohort comparisons beside them without redundant panels. `linux-dark-2560x1410/24_unlabelled_grid.png`; `summary_panel.py:20`. |
| F3. Onboarding and workflow clarity | 10 | Loading presents a clear next step, setup checks explain actionable gaps, and documentation renders on macOS dark. `ci-macos-15-dark/17_documentation__DocumentationViewer.png`; `linux-light-2560x1410/04_labelled_loaded_checklist__PostLoadChecklistDialog.png`. |
| F4. Consistency and polish | 9.8 | Main windows and dialogs are coherent; Identity name hover still behaves differently immediately after leaving a cell. `r15_normal/dark-name-after-cell.png`; `targeted_qc_widget.py:254`. |
| F5. Feedback and state | 9.8 | Verdicts, saved changes and loading state remain clear, but the Identity transition can show stale cell detail before losing feedback. `ci-macos-15-dark/27_peak_verdicts.png`; `r15_normal/results.json`; `chart_style.py:225`. |
| F6. Efficiency and flexibility | 10 | Keyboard review, multi-selection, filters, fit overrides, scale controls and resizing remain effective. `ci-windows-latest-dark/10_review_menu__menu.png`; `linux-dark-150pct-1280x800/24_unlabelled_grid.png`. |
| F7. Data visualisation | 9.8 | Charts, axes, status marks and enlarged views remain legible; full-name and qualifier-state recovery has the hover exception in issue 1. `ci-macos-15-light/11_detailed_view__DetailedPlotDialog.png`; `r15_checks/dark-name-tip.png`; `targeted_qc_widget.py:263`. |
| F8. Modern feel | 10 | The workspace and secondary windows feel like one considered desktop application in both appearances. `ci-macos-15-light/29_unlabelled_settings_deconvolution__SettingsWindow.png`; `ci-windows-latest-dark/11_detailed_view__DetailedPlotDialog.png`. |
| F9. Taste, not AI slop | 9.9 | The interface is specific to this work and the duplicate failure count is gone; one unnecessary identifier repetition remains in cell tooltips. `linux-light-2560x1410/24_unlabelled_grid.png`; `r15_normal/dark-cell-tip.png`; `identity_chart.py:177`. |

Reviewed commit `e640bf03afd9ed21e958f4cf28ccd1ac59cc7ddf`. Supplied screenshot paths are relative to `/home/willyg/code/pMANIC-notes/reviews/round-15/shots/`. Probe paths are relative to [this review's scratch folder](/home/willyg/code/uiux-scratch/review-r15-sol). Bare source filenames refer to `/home/willyg/code/pMANIC/.claude/worktrees/review-r15/src/manic/ui/`.

I viewed all 558 supplied PNGs through 54 contact sheets, enlarged relevant originals, and examined the primary monitor before the laptop and scaling evidence. Every Windows/macOS light/dark folder was included. Scores use the weakest observed result; no appearance triggers the rubric's five-point cap. The two deductions below are the only observed gaps to 10.

There are **two confirmed issues to rank**, in impact order. I have not padded the requested top twelve with unsupported concerns.

1. **Identity hover can disappear when moving from a cell onto its sample name.** Hover a failed qualifier cell, move directly left onto that row's name, then stop. The old cell detail can remain briefly and the tooltip then disappears. Moving one more pixel restores the full sample name and both qualifier states. This reproduced with ordinary and long names in light and dark mode. It matters most when the displayed name is shortened.

   The affected location is `r15_normal/dark-name-after-cell.png`; the recovered tooltip is `r15_normal/dark-name-tip.png`. The recorded sequence in [r15_normal/results.json](/home/willyg/code/uiux-scratch/review-r15-sol/r15_normal/results.json) shows an empty `resting_name_tip`, followed by the correct `after_jitter` and `after_second_rest`. The long-name run agrees. The source explains the ordering: [chart_style.py:225](/home/willyg/code/pMANIC/.claude/worktrees/review-r15/src/manic/ui/chart_style.py:225) displays the row tooltip before chart hover processing, while [targeted_qc_widget.py:254](/home/willyg/code/pMANIC/.claude/worktrees/review-r15/src/manic/ui/targeted_qc_widget.py:254) clears the cell and hides the tooltip on cell leave. `_row_tip` can therefore read the previous cell first.

   Fix the transition so cell leave refreshes the current name tooltip rather than clearing it, with one owner deciding the tooltip from the current pointer position. Verify one mouse move from cell to name followed by a pause. The existing test at `tests/test_identity_chart.py:222` sends two moves, which masks this case. Expected gain: F4, F5 and F7 each +0.2.

2. **Identity cell tooltips repeat the qualifier identifier.** `r15_normal/dark-cell-tip.png` reads `Qualifier 1  Failed`, then `Qualifier 1  expected 0.450  ±25%  observed 0.815`. Repeating `Qualifier 1` immediately adds no information. This is a small but concrete instance of the rubric's redundancy tell, visible in both appearances.

   The repetition comes from [identity_chart.py:177](/home/willyg/code/pMANIC/.claude/worktrees/review-r15/src/manic/ui/identity_chart.py:177), which adds the identifier before detail text that already contains it. Render the identifier once, retaining the status and every numeric detail. This is a copy change only. Expected gain: F9 +0.1. The same copy existed at round 14; this is a newly identified finding, not a new regression.

The round-15 changes produce these results:

| Change since round 14 | Status | Evidence |
|---|---|---|
| Identity names recover the full sample and each qualifier's state | Partly fixed | Correct name tips appear and survive resting after another movement; the cell-to-name transition above remains. `r15_checks/light-name-tip.png`; `r15_normal/results.json`; `targeted_qc_widget.py:263`. |
| Sidebar internal-standard name preserves its ending and answers hover | Fixed | A long name displays as `scyllo-In…suffix_d6`; the row tooltip and accessible name contain the whole value. `r15_normal/long-standard-tip.png`; `sidebar_widgets.py:211`; `sidebar_widgets.py:232`. |
| Identity failures are counted once | Fixed | Header detail is empty and the footer alone tallies 16 validated, 2 failed and 4 unassessed qualifier cells. Red rows identify the failed sample. `linux-dark-2560x1410/24_unlabelled_grid.png`; `r15_normal/results.json`; `targeted_qc_widget.py:167`. |
| macOS dark documentation renders | Holds | Every supplied documentation-page PNG contains rendered content. `ci-macos-15-dark/17_documentation__DocumentationViewer.png` and its page captures. |

My round-14 report had no open findings. I rechecked its twelve previously closed issues; all remain fixed:

| Previous issue | Status | Round-15 result and evidence |
|---|---|---|
| 1. Long standard name hides Choose in Settings | Fixed | Choose remains visible beside the elided name. `secondary/long-settings-standard-chosen.png`; `settings_window.py:447`. |
| 2. Long sample names push fit controls outside the table | Fixed | Both columns and all editors fit; full names remain in tooltips. `isolated/long-settings-table.png`; `settings_window.py:753`. |
| 3. Recent filenames hide their folder | Fixed | The rows retain distinct control/experiments folder endings and full-path hover text. `hover/main-long-recent.png`; `start_panel.py:217`. |
| 4. Checklist cannot reveal shortened text | Fixed | Long compound names and both matched filenames remain recoverable. `isolated/long-mm-checklist.png`; `r14_checks/long-compound-checklist.png`; `post_load_checklist_dialog.py:356`. |
| 5. Horizontal scrollbar cuts into the last fit row | Fixed | Four 36 px rows occupy a 144 px viewport with no horizontal scrollbar. `isolated/long-settings-table.png`; `settings_window.py:734`. |
| 6. Deconvolution heading loses its suffix | Fixed | Middle elision preserves the identifying ending. `secondary/long-settings-Deconvolution.png`; `chart_header.py:36`. |
| 7. Zero-area Summary row loses full-name hover | Fixed | The zero row returns its full name and `Peak area  0`. `hover/area-zero-rows.png`; `hover/hover-results.json`; `chart_style.py:220`. |
| 8. Validated Identity marks are faint | Fixed | Marks remain readable in light and dark native captures; the contrast check still passes. `ci-windows-latest-dark/33_identity_popup__ChartPopupDialog.png`; `challenge/challenge-results.json`. |
| 9. Summary single-click selection is inconsistent | Fixed | A real Peak area click selects its sample, and Identity name clicks also select the correct sample. `isolated/peak-area-click.png`; `r15_normal/results.json`; `chart_style.py:231`. |
| 10. Peak-window units require hover | Fixed | The expanded section says `minutes`. `linux-light-2560x1410/05_labelled_grid.png`; `left_toolbar.py:299`. |
| 11. Popup Return hint omits choosing a row | Fixed | The hint describes choosing and selecting; the first/second Return behavior remains intact. `ci-macos-15-light/13_abundance_popup__ChartPopupDialog.png`; `popup-return-results.json`; `chart_popup_dialog.py:692`. |
| 12. Enlargement tooltip promises names already visible | Fixed | It says `Enlarge (or double-click the chart)`. `hover/summary-expand-tip.png`; `chart_header.py:73`. |

I found no broad visual or core-workflow regression from round 14. The score falls from my previous 10.0 because this review exposed the transition case and the small copy duplication. No additional visual redesign is warranted by the evidence.

I compared `origin/main...e640bf03` under `src/manic/ui`, traced the action and Settings definitions, and exercised the core retained paths. No confirmed menu action, shortcut, context command, setting, dialog, popup, filter, multi-select operation, verdict, fit choice, scale option or integration control was removed. Scale controls remain available in the chart header and View menu; Settings remains accessible through the platform-appropriate menu. Comparison artifacts are [ui-retention.diff](/home/willyg/code/uiux-scratch/review-r15-sol/ui-retention.diff) and [retention-inventory.json](/home/willyg/code/uiux-scratch/review-r15-sol/retention-inventory.json). This establishes no confirmed loss, not exhaustive execution of every command combination.

Fresh labelled loading showed 95 compounds, 30 samples and 2850 imported EICs. The current supplied dataset contains thirty CDFs, rather than the brief's older 31-sample count. Unlabelled loading showed eight compounds, eleven samples and 88 EICs. I read the sidebar indicators and counts, compound/tR grid header and status area after loading. The import confirmation is transient; the ordinary status message and default deconvolution indicator are empty afterward.

Both modes passed selection and multi-selection, keyboard acceptance of eligible below-threshold peaks, bad marks with stored-verdict checks, peak-window application with stored-offset checks, extraction-window application, a saved Settings change, Gaussian sample overrides, scale changes, filtering, sample focus/restore, chart popups and detailed views. Further probes covered recovery refresh, baseline/integration controls, documentation Find, detailed-view sample stepping, Pan/Zoom/Reset and Full scan. An unlabelled session round-trip retained its window offset and fit overrides.

Both workbooks opened with openpyxl. Labelled contains Raw Values, Corrected Values, Isotope Ratio, % Label Incorporation and Abundances; unlabelled contains Raw Values, Abundances and Qualifier QC. Both session JSON files parsed. These are checks of interaction, persistence and artifact readability. Scientific calculations and exported numerical correctness were excluded.

The dark tour recorded 62 captures across all 36 steps with zero skips or errors. All 49 broad probe checks passed, as did the separate popup Return check. The Identity/sidebar test run reported 53 passed. The additional transition probes document issue 1 with both name lengths and appearances. Results are collected in [verification-summary.json](/home/willyg/code/uiux-scratch/review-r15-sol/verification-summary.json).

For F9, the other repetitions have clear purposes. Navigation and the grid heading repeat the selected compound to maintain orientation. Sample names recur because each chart must be readable independently. Selection counts beside integration and fitting controls state the action's scope. Tile QC and Identity cells support individual inspection and cohort comparison; the grid key explains colour and the footer tallies cells. Popup legends make enlarged charts independent. Menu/context/shortcut equivalents and drop/picker alternatives provide different access paths. The repeated qualifier identifier in issue 2 has no such purpose. I found no template hero/stepper, ornamental card grid, decorative status chip, gradient or glow. Settled decisions were excluded from findings and scores.

All app work ran offscreen after sourcing the required Qt dependencies. Windows/macOS judgments use the supplied CI screenshots; native interaction was not run on those hosts. Prove It Works shaped the direct mouse, stored-state and workbook checks. Investigation and Unslop were applied in-thread as the assigned review sub-agent, with no further delegation. Throughput checkpoint: n/a, read-only investigation. The requested `codex-harness.md` is absent; the installed Codex/T3 mappings were used. No repository or notes file was edited. This report is saved as [report.md](/home/willyg/code/uiux-scratch/review-r15-sol/report.md).

Not checked live: native file pickers, screen-reader output, installer/update delivery, external rebuild execution, every export option or every cancellation/error path.
Known remaining risk: Identity name feedback can disappear after leaving a cell until the pointer moves again; no core workflow failure was reproduced.

```json
{"F1":10,"F2":10,"F3":10,"F4":9.8,"F5":9.8,"F6":10,"F7":9.8,"F8":10,"F9":9.9,"overall":9.9}
```
