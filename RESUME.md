# MANIC UI/UX hillclimb: resume note

Paused 2026-11-04 ~17:55 GMT on the first machine. This branch
(`uiux-hillclimb-notes`, orphan, never merged) holds everything that lived
outside the repo: rubric, design spec, reviewer brief, decision log, and the
round 0 and round 1 reviews and screenshots. In these files `<NOTES>` stands
for wherever you check this branch out.

## Goal (from the user)

Full UI/UX overhaul of MANIC: beautiful, easy to use, flexible, not clunky
science software. No science changes, no lost functionality, works and looks
equally good on macOS and Windows, in light and dark mode (following the OS,
switching live). All work lands in ONE PR from `feat/ui-ux-overhaul` to `main`.

Two independent reviewers rate the app every round on the frozen rubric
(`rubric.md`, 8 factors, 1 to 10): Codex GPT-6.1 Sol (`codex/gpt-6.1-sol`,
reasoningEffort xhigh) and Claude Opus 5.5 (`claudeAgent/claude-opus-5-5`,
effort high). Every time changes land they re-rate. Metric = mean of the two
overall scores.

**Stop predicate:** average >= 8.0, neither reviewer < 7.5, at least 3
re-rating rounds (round 1 was the first), 550+ tests green, tour `errors: 0`
in light and dark, reviewers report no lost functionality.

## Scores so far

| Round | Commit | Sol | Opus | Avg |
|-------|--------|-----|------|-----|
| 0 baseline | `f55caa6` (= main + tour + tokens) | 3.5 | 3.8 | 3.65 |
| 1 | `9a09a4c` (macOS light only) | 6.5 | 6.8 | 6.65 |

Per-factor tables are in `reviews/round-*/`. The rubric now says each factor
scores the weakest of mac/Windows x light/dark, and a broken dark or Windows
layout caps F1, F4, F8 at 5, so round 2 can drop if dark mode/Windows are weak.

## Branches (all pushed to origin)

- `feat/ui-ux-overhaul` @ `9a09a4c`: the PR branch. Round 1 state. Contains
  `scripts/ui_tour.py` (screenshot harness), `src/manic/ui/theme.py` (tokens,
  `@name` substitution in `style.qss`), the shell/sidebar, grid/charts and
  dialogs redesigns (merged from three implementers), and the sidebar
  summary fix.
- `wip/ui-dark-mode` @ `6ffe4d2` (parent `9a09a4c`): UNFINISHED dark mode +
  live scheme switching + `ui_tour.py --scheme light|dark` + Fusion style
  (`src/manic/utils/utils.py`). 550 tests pass; dark tour ran with 0 errors;
  the implementer was stopped before it looked at the dark screens. Not done:
  reviewing/fixing dark screens, the CI workflow, the 150% scaling check.
- `uiux-hillclimb-notes`: this branch.

## Resume steps, in order

1. Setup: `uv sync`. Regenerate the gitignored synthetic data the tour
   needs: `uv run python scripts/generate_bench_data.py --mode labelled`
   (writes `testdata/bench/labelled`, 30 samples, 95 compounds; check the
   folder name) and `uv run python scripts/generate_unlabelled_synthetic_data.py`
   (writes `testdata/unlabelled_synthetic`). Run tests with
   `uv run python -m pytest -q` (the venv `pytest` shim may have a stale
   shebang). Tour: `uv run python scripts/ui_tour.py <dir> [--scheme dark]`.
2. Finish the dark/Windows work from `wip/ui-dark-mode` (brief below), then
   merge into `feat/ui-ux-overhaul`.
3. Iteration 3: fix the round 1 findings (list below).
4. Round 2 review (both reviewers, all four platform/appearance combos).
5. Loop fix -> re-rate until the stop predicate holds.
6. Open the single PR to `main`, run interrogate (Sol + Opus) on the diff,
   settle blocking findings, verify, link it. No Claude attribution anywhere.

## Dark mode / Windows: what is left

- Look at every dark screen (tour `--scheme dark`): no white panels,
  readable text, charts legible (QtCharts tiles, popups, matplotlib detailed
  view), dialogs consistent, logo on dark, focus/selection accent, QC tints.
  Light must not regress. Known literal: export-options text fixed black at
  `src/manic/ui/main_window.py` ~2759; documentation viewer had ~22 literal
  colours; `graphs.py` hard-codes "⌘/Ctrl" text (use native shortcut text).
- Live switching: the tour should flip the scheme mid-run and screenshot.
- Add `.github/workflows/ui-tour.yml`: `pull_request` (paths
  `src/manic/ui/**`, `src/manic/resources/**`, `src/manic/utils/utils.py`,
  `scripts/ui_tour.py`, the workflow) + `workflow_dispatch`; matrix
  `[windows-latest, macos-15] x [light, dark]`; Python/uv set up like
  `build-windows.yml`; generate both datasets; run the tour; upload
  `ui-tour-<os>-<scheme>` artifacts even on failure; fail on non-zero
  `errors:`. This is the only Windows evidence (no Windows machine).
- Check layout at `QT_SCALE_FACTOR=1.5` with a 1280x800 window.

## Round 1 findings to fix (both reviewers unless noted)

1. BUG: collapsed Display summary says "No baseline" while baseline is on.
   `left_toolbar.py` sets checkboxes with signals blocked (~547, ~582) so
   `_refresh_display_summary` never runs; View menu actions go stale too
   (`main_window.py` ~518). Fix + test that switches compounds.
2. Compound list shrinks to ~5 rows (3 with Samples open) once data loads:
   `fit_inspector` (~355) gives the inspector priority. Give browsing
   >= max(10 rows, 45%) height, inspector scrolls, Peak window and Summary
   collapsible, remember the split.
3. No persistent compound name above the grid; filtering can hide the active
   compound. Add a 15-16px title in the grid header (`graphs.py` ~214) with
   "tR 7.09 · 30 samples"; "No matching compounds" + clear-filter.
4. Baseline correction changes integration but sits under Display: move it to
   the Peak window section; Display keeps the y-scale options.
5. (Sol) Context-menu commands like "Mark peak as bad" / "Curve fit" act on
   all selected plots while reading singular: show the target count. Do not
   change targeting.
6. (Sol) Add Compound clips with inline errors and is ~773px tall: scroll
   area with fixed footer, reserve hint/error space; (Opus) flag every missing
   required field at once; replace remaining 0/0.0000 prefills with
   placeholders only where validation treats them identically.
7. Legend chips lose m/z and the QC key at 1280/1024: wrap to a second row
   before truncating. QC badges truncate sample names: give badges their own
   row/area.
8. (Sol) QC counts mix units ("1 failed" samples vs "Failed 2" cells): label
   units; name the grey states (absent / not assessed / unavailable).
9. Sidebar summary charts are anonymous: isotopologue key chips on Label
   Incorporation, hover tooltips/named rows; keep the mini overview.
10. (Opus) Popup value labels mix formats ("1", "6.22e-05"): fixed precision
    in the axis unit, "<0.01", "—" for empty, drop "Hover a bar" when labels
    show.
11. (Opus) Sample list looks like selection (all rows blue) but means "shown";
    reselecting moves a sample to the end of the grid (order from
    `selectedItems()`, `left_toolbar.py` ~506). Checkbox per row, keep list
    order, "k shown · n match" summary respecting the filter.
12. (Opus) Detailed view not redesigned: one toolbar for three charts,
    `chart_style`/theme colours, spectrum labels only on top-N peaks, "·"
    footer, legible legend.
13. Settings footer misaligned (Discard y=676 vs Save y=668,
    `settings_window.py` ~843-860), numeric fields stretch to 466px (cap
    ~120px); copy says "toolbar" (~433) and promises red backgrounds while the
    badge is amber (~174).
14. Labels: "Update" (tR window) is vague; make the status-bar deconvolution
    item open Settings > Deconvolution (Opus says it is not clickable; check).
15. (Sol) Visible Review menu: Inspect, Show selected, Show all, peak review
    and curve-fit actions with target counts; keep the context menu.
16. Docs still use old labels: `docs/00_quick_start.md:8`,
    `docs/01_user_guide.md:89,111,226,435-438`,
    `docs/Workflow_Process_External_Data.md:41-44` ("Skip" is now "Continue
    without changes", the Int Std pill is now a sidebar status row, etc.).
17. Tour bug: `charts()` in `scripts/ui_tour.py` sorts tiles by position in
    their own card; sort by position in the grid view instead.
18. (Sol, deferred) Checklist has no edit path for an existing compound's MM
    pattern. It is a new feature; decide whether it earns its place.

## How the loop ran (reuse it)

- Each round: run the tour into `<NOTES>/reviews/round-N/shots`, then
  dispatch both reviewers (T3 `delegate_task`, role review, async) with a
  brief that says: read `reviewer_brief.md` and follow it, read-only, round
  context (commit, shots dir, their previous report, their scratch folder),
  drive the app themselves, check lost functionality. Put CI artifacts for
  Windows/dark in the round folder too.
- Implementation: Opus implementers in separate worktrees with disjoint file
  ownership, reading `design_spec.md` (binding fences). Review each diff for
  science fences (`git diff --stat -- src/manic/{processors,models,validation,sheet_generators,io}`
  must be empty), merge, run tests + tour, look at the screens, then re-rate.
- After merging parallel implementers, compare overlapping screens side by
  side: the user flagged that the non-owner's version was sometimes better
  (sidebar summaries); keep the best.
- Decision log: `decision.tsv` (one row per attempt/round). Keep updating it.

## Gotchas

- `bench/HILLCLIMB.md` in the main checkout is from an unrelated session.
  Never commit it.
- Never commit a `testdata` symlink in a worktree.
- The tour's documentation screenshot is blank (QWebEngine cannot be grabbed);
  reviewers know it is a false positive.
- `feat/ui-ux-overhaul` was created tracking `origin/main`; it is now pushed
  with its own upstream.
- Settings save stays per page ("Save this page") on purpose: saving all pages
  would chain several saves and replots.
