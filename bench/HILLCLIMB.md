# Performance hillclimb

Make every slow action in MANIC faster without changing any scientific result. You work in a loop. Make one change, measure it, check the science, then keep the change or revert it. Read `bench/README.md` before you start. It explains the harness, the synthetic datasets, and `bench/areas.py`.

## Goal

The average improvement across all actions in the table below is at least 30% against the baseline. Each action's improvement is `1 - candidate median / baseline median`, so it is capped at 100%. Every action has equal weight.

No action may end up more than 10% slower than baseline. Not every action has to improve.

## Actions

| # | Action | Bench stage | Status |
| --- | --- | --- | --- |
| 1 | Load compound list plus CDF import | `import` | exists |
| 2 | Natural abundance correction | `corrections` | exists |
| 3 | Deconvolution and integration, level 4 | `deconvolve` | exists |
| 4 | First plot after loading | `plot_first` | exists |
| 5 | Next compound | `plot_next` | exists |
| 6 | Export data (Excel) | `export` | exists |
| 7 | App cold start until the main window is shown | `startup` | to add |
| 8 | Export session, then import it into a fresh window | `session_roundtrip` | to add |
| 9 | Regenerate EICs after an RT window change and after a mass tolerance change | `regenerate` | to add |
| 10 | Resize or maximise the window with a full tile grid | `resize` | to add |
| 11 | Select a subset of samples and focus them, then select all | `select_samples` | to add |
| 12 | Open the detailed plot dialog (EIC, TIC, MS) | `detailed_plot` | to add |
| 13 | Clear session, then start a new session | `clear_session` | to add |

`plot_next` produces one row per target compound. Count it as one action by taking the median across its rows.

## Science invariants (hard gate)

A change is kept only if all three checks pass. If any check fails, revert the whole change. A failing gate is not open to argument.

1. `./scripts/tests.sh` passes.
2. `uv run python bench/areas.py diff .benchmarks/areas-base.npz <candidate>.npz` reports every cell identical at levels 4 and 7.
3. `uv run python scripts/diff_export.py <baseline.xlsx> <candidate.xlsx>` reports every cell value identical across every sheet of the full export, for both bench datasets.

Never change fitting defaults, thresholds, model selection, correction maths, or what is exported. Speed comes from doing the same work with less overhead. That means fewer reads, batching, caching, vectorising, avoiding repeated redraws, lazy imports, and moving work off the UI thread. It never means doing less science.

## Phase 0: build the harness, then freeze it

Do this phase before any optimisation. Commit it on its own branch, separately from any speed change.

1. **Write `scripts/diff_export.py`.** It loads two `.xlsx` files with openpyxl and compares every sheet name and every cell value. On any difference it exits non-zero and prints the sheet, the cell, and both values. Add a small test with one identical pair and one changed pair.
2. **Add bench stages 7 to 13.** Follow the pattern in `bench/test_plot.py`: the real `MainWindow` on Qt's offscreen platform, `benchmark.pedantic`, and one run per dataset. Each stage times only the action itself, so setup goes in `setup=`. Each stage must assert a cheap invariant proving the work happened, such as the tile count or sample count after the action. Put cold start (7) in a subprocess so imports are not already warm.
3. **Prove each new stage is sensitive.** Add an artificial `time.sleep(0.2)` to the code path the stage covers and confirm the bench reports it. Then remove the sleep.
4. **Freeze the harness.** After this phase, do not edit `bench/`, `scripts/generate_bench_data.py`, `scripts/synthetic_gcms.py`, `scripts/diff_export.py`, or the tests. If the harness itself turns out to be wrong, stop and report it. Do not fix it mid-run.

## Baseline

Run on one quiet machine, plugged in, with nothing else heavy running. Timings from different machines cannot be compared, so the baseline and every candidate must come from the same machine.

```bash
uv sync
uv run pytest bench --bench-repeat 3 --benchmark-autosave          # note the 4-digit baseline id
uv run python bench/areas.py snapshot .benchmarks/areas-base.npz
# export both datasets to .benchmarks/export-base-{labelled,unlabelled}.xlsx
./scripts/tests.sh
```

Record the baseline id, the per-action medians, and the machine in the first rows of the log.

## The loop

1. Read `.benchmarks/hillclimb.tsv`. Pick the slowest action, or the one with the most room left, and profile it (`py-spy` or `cProfile`) to find where the time actually goes.
2. Write one hypothesis that names a mechanism, for example "plot_next re-reads every EIC from SQLite; cache per compound". "Try memoising something" is not a hypothesis.
3. Make that one change only. Never stack untested changes.
4. Run `uv run pytest bench --bench-repeat 3 --benchmark-compare=<baseline id>`.
5. Run all three science gates.
6. Keep the change only if the targeted action improves by more than 10% (or `--bench-repeat 5` confirms a smaller gain), no action regresses by more than 10%, and every gate passes. Otherwise revert all of it.
7. Kept changes get one commit each. Stage only the files you changed, never `git add -A`. The commit message names the action and the measured delta.
8. Log every attempt, kept or reverted, as one row in `.benchmarks/hillclimb.tsv` with these columns: `id, action, hypothesis, change, before_ms, after_ms, delta_pct, gates, verdict, note`.

Independent hypotheses for different actions can run in parallel, each in its own git worktree. Re-measure every kept change on the main branch after merging. Wins measured in isolation do not always add up.

After three rejected attempts in a row on one action, switch to another action or another kind of fix. If a simpler version of the code holds the same time, keep it.

## Stop

Stop when the average improvement is at least 30% and you have made at least 15 attempts. Do not lower the target to meet it. If you run out of worthwhile ideas first, stop and report the plateau instead of making marginal changes.

## Deliverable

A pull request with the Phase 0 commit first and the kept wins stacked after it. The description contains:

- A per-action table: baseline median, final median, percent change.
- The average improvement.
- Attempts made, and how many were kept and reverted.
- One line per kept change, with its measured delta.
- Output of all three gates on the final head.
- The path to `hillclimb.tsv`.
- The best untried idea.
