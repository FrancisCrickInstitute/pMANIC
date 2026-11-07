# Iteration 21: bug fix, popup crash and stale Summary tips (round 18)

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r18-linux.md` first and follow it (shared
rules, headless run, fences, report). Overrides: base commit `7434f240`, 807 passed + 4 skipped at
base, scratch `/home/willyg/code/uiux-scratch/r23-bugfix/`, round 18 reports:
`/home/willyg/code/pMANIC-notes/reviews/round-18/sol-review.md` and `opus-report.md`.
This is the Bug fix playbook: reproduce each defect first on the real app, find the root cause,
fix it there, prove the fix with a test that fails on base.

Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r23-bugfix`
(branch `uiux/r23-bugfix`, base `7434f240`; `testdata` linked).
Files you own: `src/manic/ui/chart_popup_dialog.py`, `chart_style.py`, `identity_chart.py`,
`targeted_qc_widget.py`, `total_abundance_widget.py`, `isotopologue_ratio_widget.py`, and their
feature-named tests (`tests/test_chart_popups.py`, `tests/test_identity_chart.py`,
`tests/test_chart_summaries.py`).

## 1. CRASH (top priority; a regression from 7434f240)
Sol: load `testdata/unlabelled_synthetic`, dismiss the checklist, open the Identity popup with its
enlarge button, close it, reopen it. An event-filter error
`'ChartPopupDialog' object has no attribute 'chart_view'` (`chart_popup_dialog.py` ~742) during a
later popup's construction, then `Fatal Python error: Segmentation fault`. Light and dark. Round 17
(e33c52c9) survives 60 opens; a scratch variant that disposes each closed popup also survives 60.
Probes and logs: `/home/willyg/code/uiux-scratch/review-r18-sol/main_popup_click.log`,
`main_popup_stress.log`, `main_popup_dark.log`, and the probe scripts beside them.
The new `BarRows` (`chart_style.py`) holds popup callbacks (`chart_popup_dialog.py` ~306) and
installs event filters; callers return from `exec()` without disposing the dialog
(`targeted_qc_widget.py` ~253, and every other `ChartPopupDialog` caller). Trace the exact ownership
and teardown sequence, then fix at the root: a popup has a defined end of life after `exec()`, and
a `BarRows` never runs callbacks for a widget that is being or has been destroyed (remove its
filters / disconnect on destruction). Check every `ChartPopupDialog` caller (Identity, Peak area,
Label incorporation). Test: open and close each popup type 30 times through real mouse events
(enlarge button, Esc / close), in both schemes, with a compound without assessable ratios
(Glycine) among them; no exception, no crash, no leftover popup children. It must fail (or crash)
on base: run it in a subprocess if a segfault would kill pytest, and assert a clean exit.

## 2. Stale Summary tip after a data change (both reviewers)
Rest the pointer on a Summary Peak area bar in labelled mode, focus the compound list, press Down:
the chart redraws for the new compound but the tip keeps the old value ("Peak area 6.23e+03" while
the row now reads 136) indefinitely (tips are held 24 h, `chart_style.py` ~204/249, and recomputed
only on pointer events). Probes: Opus `/home/willyg/code/uiux-scratch/review-r18-opus/probe18d*`,
`probe18e*`; Sol `/home/willyg/code/uiux-scratch/review-r18-sol/compound_tooltip.py`.
Keep each widget's `BarRows` (three widgets currently discard it) and call its `refresh()` whenever
the chart's data changes or clears (`update_abundance_from_data`, `update_ratios`,
`update_results`, `clear`, and a scheme change), so the tip shows the new row's text or hides.
Add one case to the transition matrix: rest, replace the data, assert the tip equals the new
row's text (and hides when the row is gone).

Run the full suite and the five tours (2560 light/dark, 1500x940, 1024x720, 150% 1280x800) before
you report, and re-run Sol's crash probes and both reviewers' stale-tip probes against your
worktree; include their results.
