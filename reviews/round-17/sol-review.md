MANIC scores **9.9/10**. The primary 2560×1410 workspace remains attractive, uncluttered and effective for chromatogram review. Both datasets completed the core editing and export workflow. The reported round-16 popup defect is fixed. One distinct, previously unreported hover defect remains in the enlarged Identity popup when moving from a qualifier cell to a shortened sample name. I found no confirmed loss of useful functionality.

| Factor | Score | Justification |
|---|---:|---|
| F1. Visual design | 10 | Typography, spacing, alignment and restrained surfaces hold across the supplied platforms and appearances. `linux-light-2560x1410/05_labelled_grid.png`; `ci-windows-latest-dark/33_identity_popup__ChartPopupDialog.png`. |
| F2. Layout and hierarchy | 10 | The large workspace prioritises plots and places compact cohort comparisons beside them; smaller windows preserve the review area. `linux-dark-2560x1410/24_unlabelled_grid.png`; `ci-macos-15-light/05_labelled_grid.png`. |
| F3. Onboarding and workflow clarity | 10 | Empty states give one next action; setup checks and inline validation explain actionable gaps. `ci-windows-latest-light/02_empty_labelled.png`; `linux-light-2560x1410/04_labelled_loaded_checklist__PostLoadChecklistDialog.png`. |
| F4. Consistency and polish | 9.8 | Windows and dialogs are coherent, but the popup's cell-to-name hover still differs from the corrected Summary behaviour. `popup_transition_final/dark-same-row-name.png`; `chart_popup_dialog.py:611`; `targeted_qc_widget.py:253`. |
| F5. Feedback and state | 9.8 | Loading, selection, verdicts and saved changes are clear; the popup transition briefly retains cell detail before losing name feedback. `ci-macos-15-dark/27_peak_verdicts.png`; `popup_transition_final/results.json`; `chart_popup_dialog.py:774`. |
| F6. Efficiency and flexibility | 10 | Keyboard review, multi-selection, filters, fit overrides, scale choices and responsive layouts remain effective. `ci-windows-latest-dark/10_review_menu__menu.png`; `linux-dark-150pct-1280x800/24_unlabelled_grid.png`; `main_window.py:521`. |
| F7. Data visualisation | 9.8 | Charts, axes, legends and enlarged views remain legible; recovery of a shortened popup sample name has the hover exception in issue 1. `ci-macos-15-dark/11_detailed_view__DetailedPlotDialog.png`; `popup_transition_final/dark-initial-name-tip.png`; `chart_popup_dialog.py:733`. |
| F8. Modern feel | 10 | Main windows, Settings and detailed views feel like one considered desktop application in both appearances. `ci-macos-15-dark/29_unlabelled_settings_deconvolution__SettingsWindow.png`; `ci-windows-latest-light/11_detailed_view__DetailedPlotDialog.png`. |
| F9. Taste, not AI slop | 10 | The interface is specific to GC-MS review; copy is concise and no unjustified decoration or duplication was confirmed. `linux-light-2560x1410/24_unlabelled_grid.png`; `popup_verified/dark-initial-tip.png`; `identity_chart.py:177`. |

Reviewed commit `e33c52c9a4703864e81ffefd4beb6bfc65513cd7`. Supplied screenshot paths are relative to `/home/willyg/code/pMANIC-notes/reviews/round-17/shots/`. Probe paths are relative to [this review's scratch folder](/home/willyg/code/uiux-scratch/review-r17-sol). Bare source filenames refer to `/home/willyg/code/pMANIC/.claude/worktrees/review-r17/src/manic/ui/`.

I viewed all **558 supplied PNGs** through 54 contact sheets, then enlarged relevant originals. I examined the 2560×1410 workspace first, followed by every Windows/macOS light/dark folder, laptop sizes and 150% scaling. Scores reflect the weakest observed result. No platform or appearance triggers the rubric's five-point cap. Issue 1 is the only confirmed gap to 10 in F4, F5 and F7; I found no additional defensible deduction for the other factors.

There is **one confirmed issue to rank**. I have not padded the requested top twelve with speculative concerns.

1. **The enlarged Identity popup loses full-name hover after leaving a qualifier cell.** With a long sample name shortened on the axis, hover the name first. Its full-name tooltip appears and now survives resting. Move into that row's qualifier cell, then directly back to the name and stop. The old cell detail remains briefly, then the tooltip disappears. Moving one pixel along the same name does not restore it. Moving directly from the cell to another row's name shows that new name briefly, but it also disappears after resting. This makes it unreliable to recover the full identifier precisely when the displayed name is shortened.

   This reproduced in light and dark mode with real `QTest` QWindow mouse events in the popup's running event loop. The probe injects no tooltip/help events. Evidence includes `popup_transition_final/dark-initial-name-tip.png`, `dark-same-row-initial-tip.png`, `dark-same-row-name.png`, and `dark-other-row-initial-tip.png`, with matching light captures. [results.json](/home/willyg/code/uiux-scratch/review-r17-sol/popup_transition_final/results.json) records a persistent `initial_name_rest`, empty `cell_to_same_name_rest` and `cell_to_other_name_rest`, and empty feedback after one-pixel movement. [popup_transition_final.py](/home/willyg/code/uiux-scratch/review-r17-sol/popup_transition_final.py) reproduces the sequence.

   The source explains the conflicting ownership. Cell leave unconditionally hides the tooltip at [chart_popup_dialog.py:611](/home/willyg/code/pMANIC/.claude/worktrees/review-r17/src/manic/ui/chart_popup_dialog.py:611). Mouse movement only refreshes the row tooltip when the row changes at [chart_popup_dialog.py:774](/home/willyg/code/pMANIC/.claude/worktrees/review-r17/src/manic/ui/chart_popup_dialog.py:774). The new automatic-tooltip protection preserves an existing tooltip but does not repair this transition. Summary already refreshes its current row feedback after cell hover changes at [targeted_qc_widget.py:253](/home/willyg/code/pMANIC/.claude/worktrees/review-r17/src/manic/ui/targeted_qc_widget.py:253).

   Coordinate popup cell and row hover so cell leave recomputes feedback from the current pointer position. Over a shortened name, show that row's full name; outside the chart or after closing, hide it. Verify cell-to-name movement within the same row and across rows, followed by a pause without another move. Expected gain: F4, F5 and F7 each +0.2. The same transitions fail against round 16 in [popup_r16_baseline/results.json](/home/willyg/code/uiux-scratch/review-r17-sol/popup_r16_baseline/results.json), so this is a newly identified existing defect, not a round-17 regression.

The round-16 finding has this outcome:

| Previous finding | Status | Round-17 evidence |
|---|---|---|
| Enlarged Identity cell tooltip disappears while the pointer rests | Fixed | Expected and observed ratios remain visible after a 2.5-second pause, one-pixel movement and re-entry, in both appearances. `popup_verified/results.json`; `chart_popup_dialog.py:769`. |

Initial long-name hover also now survives resting. Leaving the chart and closing with Escape hide the tooltip in the lifecycle probe. The separate transition defect above does not invalidate the fix to the reported stationary-cell case. The unchanged one-decimal overall score reflects this newly confirmed gap; the original cell-rest deduction is removed. No new visual regression was observed.

The test changes also hold. The context-menu test releases its right button, the header-fold test uses the app's styling, and the selected 94-test run passed. The detailed-view queued-draw close check passed as part of that run.

I rechecked the closed findings carried in the round-16 report:

| Earlier finding | Status | Current evidence |
|---|---|---|
| Summary cell-to-name hover loses feedback | Still fixed | Ordinary and long names, same-row and cross-row transitions persist and hide on leave in both appearances. `r15_normal/results.json`; `transitions/results.json`. |
| Cell copy repeats the qualifier identifier | Still fixed | The identifier appears once while status and numeric detail remain. `popup_verified/dark-initial-tip.png`; `identity_chart.py:177`. |
| Long standard name hides Choose in Settings | Still fixed | Choose remains visible beside the shortened value. `secondary/long-settings-standard-chosen.png`. |
| Long sample names push fit editors out of view | Still fixed | Both columns and all editors fit, with full-name tooltips. `isolated/long-settings-table.png`; `isolated/isolated-results.json`. |
| Recent filenames hide their distinguishing folders | Still fixed | Folder endings distinguish rows and hover retains their paths. `hover/main-long-recent.png`; `hover/hover-results.json`. |
| Checklist cannot reveal shortened names or filenames | Still fixed | Tooltips retain the compound and both matched filenames. `isolated/isolated-results.json`; `r14_checks/challenge-results.json`. |
| Horizontal scrollbar cuts into the last fit row | Still fixed | Four complete rows occupy a 144-pixel viewport with no horizontal scrollbar. `isolated/long-settings-table.png`. |
| Deconvolution heading loses its identifying suffix | Still fixed | Middle elision preserves the suffix. `secondary/long-settings-Deconvolution.png`. |
| Zero-area Summary row loses full-name hover | Still fixed | The zero row returns its full identifier and `Peak area  0`. `hover/hover-results.json`. |
| Validated Identity marks are faint | Still fixed | Marks remain legible in both appearances and native-platform captures. `ci-windows-latest-dark/33_identity_popup__ChartPopupDialog.png`; `challenge/challenge-results.json`. |
| Summary single-click selection is inconsistent | Still fixed | Peak-area and Identity name clicks select the expected sample. `isolated/isolated-results.json`; `r15_normal/results.json`. |
| Peak-window units require hover | Still fixed | The expanded section visibly says `minutes`. `linux-light-2560x1410/05_labelled_grid.png`; `r14_checks/challenge-results.json`. |
| Popup Return hint omits choosing a row | Still fixed | The hint describes choosing and selecting; first Return chooses, second selects. `popup-first-return.png`; `popup-return-results.json`. |
| Enlargement tooltip promises already-visible names | Still fixed | It says `Enlarge (or double-click the chart)`. `hover/hover-results.json`. |

No useful feature, control or path was confirmed lost. I compared `origin/main...e33c52c9` under `src/manic/ui`, inspected controls and signal connections, and exercised the principal retained paths. This covered menus and shortcuts, plot/context commands, Settings, compound/sample filtering, sample visibility and multi-selection, verdicts, fit choices, scaling, integration controls, dialogs and chart popups. Scale checkboxes remain available as header/View controls. Settings and documentation retain menu/shortcut access. Bulk fit remains in the per-sample table's selection menu. Evidence is [ui-retention.diff](/home/willyg/code/uiux-scratch/review-r17-sol/ui-retention.diff), [retention-inventory.json](/home/willyg/code/uiux-scratch/review-r17-sol/retention-inventory.json), the runtime probes and the additional tests. This establishes no confirmed loss, not exhaustive execution of every command combination.

Fresh labelled loading showed **95 compounds and 30 samples**. The supplied labelled folder has thirty CDFs, rather than the brief's stated 31. Unlabelled loading showed **eight compounds and eleven samples**. I read the sidebar readiness indicators and counts, compound/tR grid heading and status area after each load. The import toast is transient; the normal status message and default deconvolution indicator are empty afterward. `core/probe-results.json` records the fresh states.

Both modes passed selection and multi-selection, keyboard acceptance of eligible below-threshold peaks, bad marks with stored-verdict checks, peak-window application with stored-offset checks, extraction-window application, a saved Settings change, Gaussian sample overrides, scale changes, filters, focus/restore, chart popups and detailed views. Further probes checked recovery refresh, baseline/integration controls, documentation Find, detailed-view stepping, Pan/Zoom/Reset and Full scan. The unlabelled session round-trip retained its window offset and fit overrides.

Both workbooks opened with openpyxl. Labelled contains Raw Values, Corrected Values, Isotope Ratio, % Label Incorporation and Abundances. Unlabelled contains Raw Values, Abundances and Qualifier QC. Both session JSON files parsed. These checks establish UI operation, persistence and artifact readability. Scientific calculations and exported numerical correctness were excluded.

All **49 broad runtime checks passed**. The dark tour completed 36 steps and 62 captures with zero skips and zero errors. The first selected test run reported **94 passed**. The additional retention run reported **64 passed and one failed**. That failure requires an ellipsis in a long export toast even when the entire text fits. It also failed when rerun with app styling. A standalone styled-app probe confirmed 840 pixels of text fitting within an 842-pixel label with both buttons inside the toast. A longer filename correctly elides and retains full-path hover. See `toast/results.json`, `toast/window-1000.png`, and `toast_long/results.json`. This is a font-dependent test expectation, not a reproduced clipping defect.

For F9, the visible repetitions have clear purposes. Navigation and the grid heading repeat the selected compound for orientation. Independently readable charts need their sample identifiers and legends. Selection counts beside editing controls state the action's scope. Tile QC and Identity cells support individual inspection and cohort comparison; the nearby key explains the states and the footer counts qualifier cells. Menu/context/shortcut equivalents and drop/picker alternatives provide different access paths. I found no unjustified template stepper, decorative card grid, ornamental status chip, gradient, glow or redundant qualifier identifier. Settled decisions were excluded from findings and scores.

All tours and probes ran offscreen after sourcing the required Qt dependencies. Windows/macOS judgments use the supplied native CI captures; native interaction was not run on those hosts. Investigation/How and Unslop ran in-thread as the assigned review sub-agent, with no further delegation. Prove It Works drove the real mouse-event, stored-state and workbook checks. Throughput checkpoint: n/a, read-only investigation. The requested `codex-harness.md` is absent; the installed Codex/T3 mappings were used. No repository or notes file was edited. This report is saved as [report.md](/home/willyg/code/uiux-scratch/review-r17-sol/report.md).

Not checked live: native file pickers, screen-reader output, installer/update delivery, external rebuild execution, every export option or every cancellation/error path.
Known remaining risk: enlarged Identity full-name feedback can disappear after leaving a qualifier cell; no core workflow failure was reproduced.

```json
{"F1":10,"F2":10,"F3":10,"F4":9.8,"F5":9.8,"F6":10,"F7":9.8,"F8":10,"F9":10,"overall":9.9}
```
