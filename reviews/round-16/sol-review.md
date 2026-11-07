MANIC scores **9.9/10**. The 2560×1410 workspace remains clean, attractive and effective for chromatogram review. Both datasets completed the core editing and export workflow. Both round-15 findings are fixed. One newly identified issue remains in the enlarged Identity popup: its cell tooltip disappears when the pointer rests, making the observed ratio harder to read. I found no confirmed loss of useful functionality.

| Factor | Score | Justification |
|---|---:|---|
| F1. Visual design | 10 | Typography, spacing and restrained surfaces hold across the supplied appearances and platforms. `linux-light-2560x1410/05_labelled_grid.png`; `ci-windows-latest-dark/33_identity_popup__ChartPopupDialog.png`. |
| F2. Layout and hierarchy | 10 | The primary monitor gives plots priority while keeping cohort comparisons compact and nearby. `linux-dark-2560x1410/24_unlabelled_grid.png`; `summary_panel.py:20`. |
| F3. Onboarding and workflow clarity | 10 | Empty states give one clear next action; setup checks and validation messages explain actionable gaps. `ci-macos-15-light/02_empty_labelled.png`; `linux-light-2560x1410/04_labelled_loaded_checklist__PostLoadChecklistDialog.png`. |
| F4. Consistency and polish | 9.8 | Main windows and dialogs are coherent, but popup Identity tooltips lack the resting-pointer protection now present in Summary. `popup_verified/dark-rest.png`; `chart_popup_dialog.py:763`; `chart_style.py:234`. |
| F5. Feedback and state | 9.8 | Load state, selection, verdicts and saved changes are clear; the popup can remove the qualifier detail while it is being read. `ci-macos-15-dark/27_peak_verdicts.png`; `popup_verified/results.json`; `chart_popup_dialog.py:617`. |
| F6. Efficiency and flexibility | 10 | Keyboard review, multi-selection, fit overrides, scale controls and responsive layouts remain usable. `ci-windows-latest-dark/10_review_menu__menu.png`; `linux-dark-150pct-1280x800/24_unlabelled_grid.png`. |
| F7. Data visualisation | 9.8 | Charts, axes and state marks remain legible; the enlarged Identity chart's observed-ratio detail disappears after hover settles. `ci-macos-15-light/11_detailed_view__DetailedPlotDialog.png`; `popup_verified/dark-initial-tip.png`; `chart_popup_dialog.py:763`. |
| F8. Modern feel | 10 | The dense workspace, secondary windows and native-platform captures feel like one considered desktop app. `ci-macos-15-dark/29_unlabelled_settings_deconvolution__SettingsWindow.png`; `ci-windows-latest-light/11_detailed_view__DetailedPlotDialog.png`. |
| F9. Taste, not AI slop | 10 | The interface is specific to GC-MS review; the repeated qualifier identifier is gone and no unjustified decoration or duplication was confirmed. `linux-light-2560x1410/24_unlabelled_grid.png`; `r15_normal/dark-cell-tip.png`; `identity_chart.py:177`. |

Reviewed commit `4f1b39997ffffa3044003c66302758c6ac2510d5`. Supplied screenshot paths are relative to `/home/willyg/code/pMANIC-notes/reviews/round-16/shots/`. Probe paths are relative to [this review's scratch folder](/home/willyg/code/uiux-scratch/review-r16-sol). Bare source filenames refer to `/home/willyg/code/pMANIC/.claude/worktrees/review-r16/src/manic/ui/`.

I viewed all **558 supplied PNGs**, using 54 contact sheets and enlarged originals for detailed inspection. I examined the 2560×1410 workspace first, then every Windows/macOS light/dark folder, the laptop captures and 150% scaling. The CI revision `94b43970` has no UI-source difference from the reviewed commit. Scores reflect the weakest observed result; no platform or appearance triggers the rubric's five-point cap. Issue 1 is the only confirmed gap to 10 in F4, F5 and F7. I found no additional defensible deduction for the other factors.

There is **one confirmed issue to rank**. I have not padded the requested top twelve with speculative concerns.

1. **The enlarged Identity popup loses its cell tooltip when the pointer rests.** Open Alanine's Identity popup and hover Qualifier 1 for `Sample_04_ratio_fail`. The tooltip initially gives `expected 0.450  ±25%  observed 0.815`. After the pointer rests, Qt's automatic tooltip request hides it. Moving one pixel within the cell does not restore it; leaving and re-entering the cell does. This reproduced in light and dark mode with real `QTest` QWindow mouse events inside the dialog's running event loop. The final reproduction injects no tooltip/help events.

   Evidence is `popup_verified/dark-initial-tip.png`, `popup_verified/dark-rest.png`, and `popup_verified/dark-reentered-tip.png`, with matching light captures. [results.json](/home/willyg/code/uiux-scratch/review-r16-sol/popup_verified/results.json) records nonempty initial detail, empty `natural_rest`, empty `after_one_pixel`, and restored detail after re-entry. [popup_verified.py](/home/willyg/code/uiux-scratch/review-r16-sol/popup_verified.py) reproduces the sequence.

   The popup shows detail on cell entry at [chart_popup_dialog.py:617](/home/willyg/code/pMANIC/.claude/worktrees/review-r16/src/manic/ui/chart_popup_dialog.py:617), but its viewport event filter at [chart_popup_dialog.py:763](/home/willyg/code/pMANIC/.claude/worktrees/review-r16/src/manic/ui/chart_popup_dialog.py:763) does not handle `QEvent.ToolTip`. The corresponding Summary protection is at [chart_style.py:234](/home/willyg/code/pMANIC/.claude/worktrees/review-r16/src/manic/ui/chart_style.py:234).

   Preserve the active Identity cell's tooltip when the popup receives that request, using the same ownership rule as Summary. Retain hiding on leave and close. Verify a real cell hover followed by a pause without further movement. Expected gain: F4, F5 and F7 each +0.2. This is a newly identified existing defect, not a confirmed round-16 regression: `chart_popup_dialog.py` is byte-identical to round 15.

The round-15 findings now have these outcomes:

| Round-15 issue | Status | Round-16 evidence |
|---|---|---|
| Cell-to-name Identity hover loses its tooltip | Fixed | One move shows the correct sample and both qualifier states, on the same row and another row; it survives resting and hides on leave. Ordinary and long names pass in both appearances. `r15_normal/results.json`; `transitions/results.json`; `targeted_qc_widget.py:244`; `chart_style.py:221`. |
| Identity cell copy repeats the qualifier identifier | Fixed | Summary and popup name Qualifier 1 once while retaining status, expectation, tolerance and observed ratio. `r15_normal/dark-cell-tip.png`; `popup_verified/dark-initial-tip.png`; `identity_chart.py:177`. |

The detailed-view close fix also holds: the queued-draw regression test passed, and closing detailed views during the probes produced no reproduced draw-cleanup error. The guard is at `matplotlib_plot_widget.py:792`. The amended grid tick test passed. No broad visual regression was observed. The unchanged one-decimal overall score reflects the newly exposed popup issue; the previous copy deduction is removed.

I also rechecked the twelve older findings listed as closed in the round-15 report:

| Earlier finding | Status | Current evidence |
|---|---|---|
| Long standard name hides Choose in Settings | Still fixed | Choose stays visible beside the shortened name. `secondary/long-settings-standard-chosen.png`; `settings_window.py:449`. |
| Long sample names push fit editors outside the table | Still fixed | Both columns and all editors fit; full names remain available. `isolated/long-settings-table.png`; `settings_window.py:616`. |
| Recent filenames hide their distinguishing folders | Still fixed | Folder endings and full-path hover distinguish the rows. `hover/main-long-recent.png`; `start_panel.py:217`. |
| Checklist cannot reveal shortened names or filenames | Still fixed | Tooltips recover the compound and both matched filenames. `isolated/long-mm-checklist.png`; `r14_checks/long-compound-checklist.png`; `post_load_checklist_dialog.py:356`. |
| Horizontal scrollbar cuts into the last fit row | Still fixed | Four complete fit rows fit without a horizontal scrollbar. `isolated/long-settings-table.png`; `settings_window.py:619`. |
| Deconvolution heading loses its identifying suffix | Still fixed | Middle elision preserves the ending. `secondary/long-settings-Deconvolution.png`; `chart_header.py:36`. |
| Zero-area Summary row loses full-name hover | Still fixed | The zero row answers with its full name and `Peak area  0`. `hover/area-zero-rows.png`; `hover/hover-results.json`; `chart_style.py:221`. |
| Validated Identity marks are faint | Still fixed | Marks remain legible in both appearances and native-platform captures. `ci-windows-latest-dark/33_identity_popup__ChartPopupDialog.png`; `challenge/challenge-results.json`. |
| Summary single-click selection is inconsistent | Still fixed | Peak area and Identity name clicks select the expected sample. `isolated/peak-area-click.png`; `r15_normal/results.json`. |
| Peak-window units require hover | Still fixed | The expanded section says `minutes`. `linux-light-2560x1410/05_labelled_grid.png`; `left_toolbar.py:301`. |
| Popup Return hint omits choosing a row | Still fixed | The hint describes choosing and selecting; first Return chooses, second selects. `popup-first-return.png`; `popup-return-results.json`; `chart_popup_dialog.py:695`. |
| Enlargement tooltip promises names already visible | Still fixed | It says `Enlarge (or double-click the chart)`. `hover/summary-expand-tip.png`; `chart_header.py:73`. |

No useful feature, control or path was confirmed lost. I compared `origin/main...4f1b3999` under `src/manic/ui`, inspected action/shortcut definitions and their handlers, and exercised the principal retained paths. The comparison includes menus, context commands, Settings, filtering, sample visibility and multi-selection, verdicts, fit choices, scale controls, integration controls, dialogs and popups. The former scale checkboxes remain accessible through the header and View menu; Settings and documentation retain menu/shortcut access. The old bulk fit capability remains in the per-sample table's selection menu. Evidence is [ui-retention.diff](/home/willyg/code/uiux-scratch/review-r16-sol/ui-retention.diff) and [retention-inventory.json](/home/willyg/code/uiux-scratch/review-r16-sol/retention-inventory.json). This supports no confirmed loss, not exhaustive execution of every command combination.

Fresh labelled loading showed **95 compounds and 30 samples**, with 2850 imported EICs. The supplied labelled folder contains thirty CDFs; the brief's 31-sample description is outdated. Unlabelled loading showed **eight compounds and eleven samples**, with 88 EICs. I read the sidebar indicators/counts, compound/tR grid heading and status area after each fresh load. The import toast is transient; the normal status message and default deconvolution indicator are empty afterward.

Both modes passed selection and multi-selection, keyboard acceptance of eligible below-threshold peaks, bad marks with stored-verdict checks, peak-window application with stored-offset checks, extraction-window application, a saved Settings change, Gaussian sample overrides, scale changes, filters, focus/restore, chart popups and detailed views. Additional probes covered recovery refresh, baseline/integration controls, documentation Find, detailed-view sample stepping, Pan/Zoom/Reset and Full scan. An unlabelled session round-trip retained its window offset and fit overrides.

Both exported workbooks opened with openpyxl. Labelled contains Raw Values, Corrected Values, Isotope Ratio, % Label Incorporation and Abundances. Unlabelled contains Raw Values, Abundances and Qualifier QC. Both session JSON files parsed. These checks establish UI operation, persistence and artifact readability. Scientific calculations and exported numerical correctness were excluded.

All 49 broad workflow checks passed. The dark tour completed all 36 steps with 62 captures, zero skips and zero errors. The selected test run reported 70 passed and one font-sensitive header test failed. That test expects folding at 520 px while its application has the smaller unstyled font. The actual app folds correctly at 520 px; the isolated comparison is in `header-results.json`. The same test passed when rerun with normal application styling. This test-setup discrepancy does not establish a user-facing defect. Original-summary, long-name, cross-row and leave checks passed; the separate popup reproduction establishes issue 1. Results are indexed in [verification-summary.json](/home/willyg/code/uiux-scratch/review-r16-sol/verification-summary.json).

For F9, the repetitions I found have clear purposes. The selected compound appears in navigation and the grid heading to maintain orientation. Each independently readable chart needs sample names and its own legend. Selection counts beside integration and fit controls state the scope of the action. Tile QC and Identity cells support individual inspection and cohort comparison; the nearby key explains colour and the footer counts qualifier cells. Menu/context/shortcut equivalents and drop/picker alternatives provide different access paths. The repeated qualifier identifier from round 15 is gone. I found no unjustified template stepper, ornamental card grid, decorative status chip, gradient or glow. Settled decisions were excluded from findings and scores.

All tours and probes ran offscreen after sourcing the required Qt dependencies. Windows/macOS visual judgments use the supplied CI captures; native interaction was not run on those hosts. Prove It Works shaped the real mouse-event, stored-state and workbook checks. Investigation/How and Unslop ran in-thread as the assigned independent review sub-agent, with no further delegation. Throughput checkpoint: n/a, read-only investigation. The requested `codex-harness.md` is absent; the installed Codex/T3 mappings were used. No repository or notes file was edited. This report is saved as [report.md](/home/willyg/code/uiux-scratch/review-r16-sol/report.md).

Not checked live: native file pickers, screen-reader output, installer/update delivery, external rebuild execution, every export option or every cancellation/error path.
Known remaining risk: enlarged Identity cell details disappear after a resting hover until the pointer leaves and re-enters; no core workflow failure was reproduced.

```json
{"F1":10,"F2":10,"F3":10,"F4":9.8,"F5":9.8,"F6":10,"F7":9.8,"F8":10,"F9":10,"overall":9.9}
```
