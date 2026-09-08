# Benchmarking

The `bench/` suite answers one question: did a code change make MANIC faster or slower on the paths a user waits on? It times the real application code, headless, on synthetic GC-MS data, and stores the numbers so two runs can be compared. Correctness is the job of `tests/`; the bench only asserts cheap invariants (row counts, tile counts, finite areas) so a broken optimisation cannot post a good time.

## Quick start

```bash
uv sync                                                # once per machine
uv run pytest bench                                    # baseline, ~90 s (~3 min the first time)
# ...change code...
uv run pytest bench --benchmark-compare --benchmark-compare-fail=median:10%
```

The first run generates `testdata/bench/` (two datasets, ~36 s) and builds one populated database per dataset under `bench/cache/` (~20 s). Both are gitignored and reused afterwards. `--benchmark-compare` adds the previous run alongside, and `--benchmark-compare-fail=median:10%` fails the run when any stage's median is more than 10 % slower.

## Outputs

Every run produces three things.

1. **A table in the terminal**, one section per stage, one row per dataset. With `--benchmark-compare` each row appears twice, the saved run tagged with its 4-digit id and the current run tagged `NOW`.
2. **A JSON file** in `.benchmarks/<platform>/`, named `<id>_<git sha>_<timestamp>.json`, holding every timing plus machine and commit info. This is the run history; `--benchmark-compare` reads the latest one by default.
3. **A box plot per stage** in `.benchmarks/plots/run-<stage>.svg`. With `--benchmark-compare` the previous run sits beside the current one, so a change is visible at a glance and the whisker shows the worst compound in `plot_next`. Open them in a browser or the editor. They are overwritten each run; copy them if you want to keep one.

`.benchmarks/` is gitignored. Delete it to start the history fresh.

The plot stages drive the real `MainWindow` on Qt's offscreen platform, so no window appears.

## What is measured

| Test | Stage | Default work | Assertion |
| --- | --- | --- | --- |
| `import` | Compound CSV plus CDF import into a fresh database | 30 files | row count |
| `corrections` | Natural abundance correction over every EIC (labelled only) | 2,850 cells | count |
| `deconvolve_hard_windows[*-4]` | Deconvolution plus integration at the shipped default (level 4, balanced gate) | 12 hard windows | one finite area per channel |
| `deconvolve_hard_windows[*-7]` | Same at level 7 with the noise gate off | `--bench-full` only, 60 windows | as above |
| `plot_first` | First plot after opening: a fresh window, cold caches, full tile grid | 30 tiles | grid and sidebar populated |
| `plot_next` | Next-compound navigation; one round per move | 9 moves spread over the list | grid populated after each move |
| `export` | Full Excel export, non-legacy integration | 30 samples | expected sheets and sample rows |

Each test runs once per dataset. Labelled compounds carry M+0..M+n channels and go through correction; unlabelled compounds are single-channel. The two are separate rows in the table.

### The datasets

`scripts/generate_bench_data.py` writes `testdata/bench/labelled` and `testdata/bench/unlabelled` deterministically (seed 1). Each has 30 samples (28 biological, 2 mixed standards) and ~100 compounds. Every sample × compound cell is assigned scenarios that mimic difficult real data: overlapping neighbours, near co-elution, shoulders, broad tailing peaks, noise, drifting baselines, retention time shift, trace-level peaks, saturated detector, heavy labelling, unlabelled controls, low internal standard, missing peaks. `manifest.json` records the scenario and true areas of every cell.

Import, export and the tile grid scale linearly with samples, so 30 is enough to measure per-item cost. The deconvolution corpus is drawn from cells the generator planted as hard (`HARD_SCENARIOS` in `bench/conftest.py`), interleaved so any prefix is a mix.

## Options

| Flag | Effect |
| --- | --- |
| `--bench-full` | 60 deconvolution windows at levels 4 and 7, and every compound navigated in `plot_next`. Adds about a minute. Use it to confirm a result before merging. |
| `--bench-repeat N` | N rounds per stage (default 1). Use 3 when a change looks like it moved something by less than 10 %. |
| `-k import` | Only the stages whose test name matches. Names: `import`, `corrections`, `deconvolve`, `plot_first`, `plot_next`, `export`, `labelled`, `unlabelled`. |
| `--benchmark-compare=0003` | Compare against a specific saved run by its 4-digit prefix instead of the latest. |
| `--benchmark-histogram=PATH` | Change where the plots are written (default `.benchmarks/plots/run`). |
| `--benchmark-disable` | Run the assertions once with no timing or saving. |

All `--benchmark-*` flags are from [pytest-benchmark](https://pytest-benchmark.readthedocs.io/); `uv run pytest bench --help` lists them.

## Reading the table

`Median` is the number to compare. `Max` matters for `plot_next`, where one slow compound is what a user feels even when the median is fine. `Rounds` is 1 unless you passed `--bench-repeat`, except `plot_next`, where each move is a round.

Run-to-run noise on a quiet machine is 1 to 3 % for most stages and up to 7 % for labelled export. Treat anything inside 10 % as noise unless `--bench-repeat 3` agrees.

## Typical loop for an optimisation

```bash
git switch -c faster-import
uv run pytest bench -k import                          # baseline for the stage you are changing
# edit src/manic/io/eic_importer.py
uv run pytest bench -k import --benchmark-compare --benchmark-compare-fail=median:10%
uv run pytest bench --bench-full --benchmark-compare   # everything, before opening the PR
./scripts/tests.sh                                     # correctness
```

## Maintenance

- Regenerate data after changing the generator: `rm -rf testdata/bench bench/cache && uv run pytest bench`.
- The cached databases are keyed on the manifest and `schema.sql`; a schema change rebuilds them automatically.

- Dense-axis data (closer to instrument scan rates) is available with `uv run python scripts/generate_bench_data.py --mode both --scan-dt-s 0.1`; import and export slow roughly fivefold.
