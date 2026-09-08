# Benchmarking

The `bench/` suite answers one question: did a code change make MANIC faster or slower on the paths a user waits on? It times the real application code, headless, on synthetic GC-MS data, and stores the numbers so two runs can be compared. Correctness is the job of `tests/`; the bench only asserts cheap invariants (row counts, tile counts, finite areas) so a broken optimisation cannot post a good time.

## Quick start

```bash
uv sync                                                # once per machine
uv run pytest bench --benchmark-autosave               # baseline; note its 4-digit id
# ...change code...
uv run pytest bench --benchmark-compare=0001 --benchmark-compare-fail=median:10%
```

Replace `0001` with the id printed by the baseline run. The candidate is not
autosaved, so repeated candidate runs keep comparing with that fixed baseline.
The first run generates `testdata/bench/` (two datasets, ~36 s) and builds one
populated database per dataset under `bench/cache/` (~20 s). Both are
gitignored and reused only while their complete inputs remain unchanged.
`--benchmark-compare-fail=median:10%` fails when any stage is more than 10 %
slower.

## Outputs

Every run produces a terminal table and plots. Saved runs produce a third
artifact:

1. **A table in the terminal**, one section per stage and dataset. Navigation has one row per target compound. With `--benchmark-compare` each row appears twice, the saved run tagged with its 4-digit id and the current run tagged `NOW`.
2. **A JSON file when `--benchmark-autosave` is passed** in `.benchmarks/<platform>/`, named `<id>_<git sha>_<timestamp>.json`, holding every timing plus machine, workload, and commit info. This is the run history. Always select its id explicitly when comparing.
3. **A plot per stage** in `.benchmarks/plots/run-<stage>.svg`. With `--benchmark-compare` the baseline sits beside the current run; `plot_next` labels every target separately. Open them in a browser or the editor. They are overwritten each run; copy them if you want to keep one.

## Saved runs

Saved runs stay local. `.benchmarks/` is gitignored because timings from different machines are not comparable, and a fresh baseline costs 90 s, so there is nothing worth sharing. Save a baseline before you start, compare against it while you work, and delete the directory whenever you like.

To see every saved run on this machine as a table, or as plots:

```bash
uv run pytest-benchmark compare                       # every saved run, one table per stage
uv run pytest-benchmark compare --histogram=.benchmarks/plots/history
```

Compare only runs with the same workload. Each benchmark id carries the workload
(default or full, seed, sample count, scan interval), and `plot_next` rows carry
the compound name. Each JSON also records the hostname and CPU.

The plot stages drive the real `MainWindow` on Qt's offscreen platform, so no window appears.

## What is measured

| Test | Stage | Default work | Assertion |
| --- | --- | --- | --- |
| `import` | Compound CSV plus CDF import into a fresh database | 30 files | row count |
| `corrections` | Natural abundance correction over every EIC (labelled only) | 2,850 cells | count |
| `deconvolve_hard_windows[*-4]` | Deconvolution plus integration at the shipped default (level 4, balanced gate) | 12 hard windows | one finite area per channel |
| `deconvolve_hard_windows[*-7]` | Same at level 7 with the noise gate off | `--bench-full` only, 60 windows | as above |
| `plot_first` | First plot after opening: a fresh window, cold caches, full tile grid | 30 tiles | grid and sidebar populated |
| `plot_next` | Next-compound navigation; one identified benchmark per target | 9 targets spread over the list | grid populated after each move |
| `export` | Full Excel export, non-legacy integration | 30 samples | expected sheets and sample rows |

Each test runs once per dataset. Labelled compounds carry M+0..M+n channels and go through correction; unlabelled compounds are single-channel. The two are separate rows in the table.

### The datasets

`scripts/generate_bench_data.py` writes `testdata/bench/labelled` and `testdata/bench/unlabelled` deterministically (seed 1). Each has 30 samples (28 biological, 2 mixed standards) and ~100 compounds. Every sample × compound cell is assigned scenarios that mimic difficult real data: overlapping neighbours, near co-elution, shoulders, broad tailing peaks, noise, drifting baselines, retention time shift, trace-level peaks, saturated detector, heavy labelling, unlabelled controls, low internal standard, missing peaks. `manifest.json` records the scenario and true areas of every cell. The harness validates the parameters, generator fingerprint, manifest checksum, and every artifact hash before reuse, and generation replaces a corpus only after all new artifacts are complete.

Import, export and the tile grid scale linearly with samples, so 30 is enough to measure per-item cost. The deconvolution corpus is drawn from cells the generator planted as hard (`HARD_SCENARIOS` in `bench/conftest.py`), interleaved so any prefix is a mix.

## Options

| Flag | Effect |
| --- | --- |
| `--bench-full` | 60 deconvolution windows at levels 4 and 7, and every compound navigated in separately identified `plot_next` rows. This is a distinct workload and requires a matching full baseline. |
| `--bench-repeat N` | N rounds per stage (default 1). Use 3 when a change looks like it moved something by less than 10 %. |
| `--bench-scan-dt-s 0.1` | Generate and use dense-axis data. The scan interval is part of the workload identity and corpus validation. |
| `-k import` | Only the stages whose test name matches. Names: `import`, `corrections`, `deconvolve`, `plot_first`, `plot_next`, `export`, `labelled`, `unlabelled`. |
| `--benchmark-compare=0003` | Compare against a specific saved run by its 4-digit prefix instead of the latest. |
| `--benchmark-autosave` | Save this run as a baseline. Leave it off for candidate runs so repeated compares keep pointing at the same baseline. |
| `--benchmark-histogram=PATH` | Change where the plots are written (default `.benchmarks/plots/run`). |
| `--benchmark-disable` | Run the assertions once with no timing or saving. |

All `--benchmark-*` flags are from [pytest-benchmark](https://pytest-benchmark.readthedocs.io/); `uv run pytest bench --help` lists them.

## Reading the table

`Median` is the number to compare. Each `plot_next` target has its own row and
records the compound name in the saved metadata, so one slow compound cannot be
hidden by the median of the rest. `Rounds` is 1 unless you passed
`--bench-repeat`.

Run-to-run noise on a quiet machine is 1 to 3 % for most stages and up to 7 % for labelled export. Treat anything inside 10 % as noise unless `--bench-repeat 3` agrees.

## Typical loop for an optimisation

```bash
git switch -c faster-import
uv run pytest bench -k import --benchmark-autosave     # note the printed baseline id
# edit src/manic/io/eic_importer.py
uv run pytest bench -k import --benchmark-compare=0003 --benchmark-compare-fail=median:10%
# For a full comparison, save a full baseline before editing and select its id:
uv run pytest bench --bench-full --benchmark-compare=0004
./scripts/tests.sh                                     # correctness
```

The bench asserts only cheap invariants, so a faster deconvolution that lands on different peak areas still passes. When touching the fitter, also diff the answers. `bench/areas.py snapshot` fits every compound × sample cell in both cached datasets at levels 4 and 7 (about 6 minutes) and `diff` reports how many cells moved and by how much:

```bash
uv run python bench/areas.py snapshot /tmp/before.npz     # on main
uv run python bench/areas.py snapshot /tmp/after.npz      # on the branch
uv run python bench/areas.py diff /tmp/before.npz /tmp/after.npz
```

A pure overhead change should report every cell identical. A change to the optimiser's path will move a handful of ill-determined cells; the diff prints the largest so they can be judged against `testdata/bench/*/manifest.json` truths.

## Maintenance

- Generator, helper, source-XLS, corpus-parameter, or artifact changes trigger
  automatic corpus/database rebuilds.
- Cached databases are keyed on every CDF, the compound list, manifest, schema,
  dependency lock, benchmark import configuration, and all application Python
  sources.

- Dense-axis data (closer to instrument scan rates) is available with
  `uv run pytest bench --bench-scan-dt-s 0.1`; import and export slow roughly
  fivefold.
