# MANIC UI/UX hillclimb: resume note

Paused 2026-11-04 ~22:30 GMT on the Linux machine (second pause; the first was
~17:55 on the Mac). This branch (`uiux-hillclimb-notes`, orphan, never merged)
holds everything outside the repo: rubric, design spec, reviewer brief, decision
log, briefs, the round 0 to 3 reviews and screenshots, and check scripts. In
these files `<NOTES>` means wherever you check this branch out.

## Goal (from the user)

Full UI/UX overhaul of MANIC: beautiful, easy to use, flexible, not clunky
science software. No science changes, no lost functionality, works and looks
equally good on macOS and Windows, in light and dark mode (following the OS,
switching live). All work lands in ONE PR from `feat/ui-ux-overhaul` to `main`.

Two independent reviewers rate every round on the frozen rubric (`rubric.md`,
8 factors, 1 to 10, each factor scored at the weakest of mac/Windows x
light/dark): Codex GPT-6.1 Sol (`codex/gpt-6.1-sol`, reasoningEffort xhigh) and
Claude Opus 5.5 (`claudeAgent/claude-opus-5-5`, effort high). Metric = mean of
the two overall scores.

**Stop predicate:** average >= 8.0, neither reviewer < 7.5, at least 3
re-rating rounds, all tests green, tour `errors: 0` in light and dark,
reviewers report no lost functionality. Status after round 3: rounds and floor
MET, average NOT met (7.75).

## Scores so far

| Round | Commit | Sol | Opus | Avg |
|-------|--------|-----|------|-----|
| 0 baseline | `f55caa6` | 3.5 | 3.8 | 3.65 |
| 1 | `9a09a4c` (macOS light only) | 6.5 | 6.8 | 6.65 |
| 2 | `6fc71eb5` (Linux light/dark/150%) | 7.1 | 7.5 | 7.3 |
| 3 | `795ecbe6` (Linux light/dark, 150% both) | 7.6 | 7.9 | 7.75 |
| 4 | `5cf5d336` (to rate next) | | | |

Reports: `reviews/round-N/{sol-review,opus-report}.md`. Decision log:
`decision.tsv` (one row per iteration/round; rows `start` mark machine changes).

## State of the branches (all pushed)

- `feat/ui-ux-overhaul` @ `5cf5d336`: the PR branch. Iterations 3 to 5 merged
  (round 1, 2 and 3 findings), plus `.github/workflows/ui-tour.yml`.
  684 tests pass; tour `errors: 0 skipped: 0` light, dark, and both at
  `QT_SCALE_FACTOR=1.5 --size 1280x800`; science fence diff vs main empty.
  Iteration 5 (round 3 findings) is merged but NOT yet rated: that is round 4.
- `uiux-hillclimb-notes`: this branch.
- Local-only implementer branches `uiux/r3-*`, `uiux/r4-integrate`,
  `uiux/r5-*`, `uiux/r6-*` and `wip/ui-dark-mode` live on the Linux machine;
  everything in them is merged into feat. Nothing needs them.

## CI (Windows/macOS evidence)

`ui-tour.yml` runs the tour on `windows-latest` and `macos-15` x light/dark and
uploads `ui-tour-<os>-<scheme>` artifacts. It has a TEMPORARY `push` trigger on
`feat/ui-ux-overhaul` (remove it before opening the PR; workflow_dispatch only
works once the file is on main). The push of `5cf5d336` started a run: find it
with `gh run list --branch feat/ui-ux-overhaul`, then
`gh run download <id> -D <dir>`. First run (on `3935b277`): 4/4 green.
Runner screens are small (Windows 1024x720, macOS 1024x681; the Windows
resolution step does not take), so CI shots are the laptop worst case.

GitHub auth: the org enforces SAML SSO. The gh token on a machine needs the
`workflow` scope AND SSO authorisation for FrancisCrickInstitute, or every push
and API call returns 403. Fix: `gh auth login -h github.com -s workflow --web`
and click Grant next to FrancisCrickInstitute on the consent page. Check with
`gh api /repos/FrancisCrickInstitute/pMANIC --jq .full_name`.

## Resume steps, in order

1. Setup: `git fetch origin`; check out `feat/ui-ux-overhaul` (pull to
   `5cf5d336`) in a worktree and this branch as `<NOTES>`. `uv sync`.
   Regenerate the gitignored data: `uv run python scripts/generate_bench_data.py --mode labelled`
   and `uv run python scripts/generate_unlabelled_synthetic_data.py`.
   Tests: `uv run python -m pytest -q` (684, ~2 min). Tour:
   `uv run python scripts/ui_tour.py <dir> --scheme light|dark` (44 shots).
   On a Mac this just works with a display. (On headless Linux see
   "Linux headless" below.) Check gh auth (above).
2. Round 4 review of `5cf5d336`:
   - Tour into `<NOTES>/reviews/round-4/shots/` for light, dark, and
     `QT_SCALE_FACTOR=1.5 --size 1280x800` light and dark (name folders by
     platform, e.g. `mac-light`, ...). Download the CI run's 4 artifacts into
     `reviews/round-4/shots/ci-<os>-<scheme>/`.
   - Copy `briefs/round-3-context.md` to `briefs/round-4-context.md` and update:
     commit, the review checkout path (a detached worktree at `5cf5d336` with
     `testdata/`), shot folders (now including real Windows/macOS CI shots),
     "since round 3" summary (below), previous reports = round 3.
     All paths in the briefs are absolute Linux paths (`/home/willyg/...`):
     rewrite them for the new machine. Scratch folders go outside /tmp if
     /tmp is small.
   - Dispatch both reviewers with T3 `delegate_task`, role review, async, same
     brief shape as round 3 (see transcript of round 3 dispatch: "Read-only,
     no edits ... Read reviewer_brief.md and follow it ... ROUND_CONTEXT:
     read briefs/round-4-context.md with {PREV} and {SCRATCH} substituted").
     Targets: `codex/gpt-6.1-sol` reasoningEffort xhigh; `claudeAgent/claude-opus-5-5` effort high.
   - Copy their `report.md` into `reviews/round-4/`, log a `R4` row, push.
3. If avg >= 8.0 and both >= 7.5: go to step 5. Otherwise loop: group the
   findings into 3 file-disjoint Opus implementers (worktrees from feat head;
   brief = `briefs/impl-common.md` with base/test-count overrides, as in
   iteration 5), review each diff (owned files only, fence diff empty), merge,
   wire cross-branch hooks yourself, run tests + tours + the two check
   scripts, push (CI runs), re-rate.
4. After merging parallel work, compare overlapping screens side by side and
   keep the best version (the user flagged this).
5. Finish: remove the temporary `push` trigger from `ui-tour.yml`; batch the
   accepted nits (below); open the single PR to `main` (technical-writing +
   unslop, no Claude attribution anywhere), mention issue #269 (fixed here)
   and the behaviour notes below; run interrogate (Sol + Opus) on the diff and
   settle blocking findings (max 3 fix rounds); verify; `link_pull_request`.

## Since round 3 (for the round 4 context)

Iteration 5 merged in `5cf5d336`:
- Grid: selection and focus kept when a fit/scale change re-plots the same
  compound (and the inspector keeps "Applies to N selected"); group Accept /
  Mark as Bad act on the not-yet-done eligible peaks and say "Clear
  Acceptance (n Peaks)" only when all are done (checkmark dropped); context
  menu ordered and named like the Review menu; Comfortable density uses
  11px chart text / 13px captions; "Not detected" pill + stronger tint.
- Popups/detail/QC: keyboard navigation from the popup's real initial focus;
  value axis pinned while rows scroll; "—" for samples with no ratio; "Double-
  click a chart to reset it" hint; human status words in legends; one-line
  message when a compound has no expected ratios; M+0…M+n spectrum bracket;
  sidebar Identity chart scrolls with readable rows, highlights the selection
  instead of filtering, no dead band.
- Sidebar/checklist: checklist body scrolls with a fixed footer, change-a-
  pattern steps behind a disclosure, overlap check in the tour; Apply window
  caption "Re-extracts all N shown samples"; summary charts name every sample
  and scroll; on short windows a pinned "Peak window · Display · Summary"
  switcher; lists keep >= 4 compound + 3 sample rows.

## Known open items / nits to batch before the PR

- At 1280x720 with Samples open, the Peak window scrolls by 48px (lists win).
- `tests/test_r5_shell_contrast.py::test_rendered_filled_buttons...` takes
  ~50s: `apply_color_scheme` restyles every leftover widget from earlier tests.
  Make it cheaper (render with the stylesheet without a full-app restyle, or
  run it in a fresh widget set).
- Round 1 finding 18 (MM pattern editor) became copy + Open File in the
  checklist; no editor (decided).
- Behaviour notes for the PR: un-accepting a mixed selection only clears the
  eligible peaks (before, it also cleared "Marked bad" on other plots); typed 0
  in Add Compound now stays and gets the ">0" error; Settings moved to File on
  Windows/Linux (macOS app menu unchanged), Baseline Correction to Review.
- Issue #269 (Total Abundance sidebar chart mislabels samples on main) is
  fixed on feat; check script `reviews/drivers/abundance_pairs_check.py`
  (expect ~10 misses = same sample, display vs export integration).

## Check scripts (run from the feat worktree root)

- `reviews/drivers/abundance_pairs_check.py`: every abundance bar beside its
  own sample (sidebar + popup). Expect `MISMATCHES 10`.
- `reviews/drivers/hooks_check.py`: popup rows select plots; checklist names
  the compound list. Expect `HOOKS OK`.
- `scripts/ui_tour.py` has `layout_problems()` (overlap / cut-off text) used
  by the checklist step; reuse it for any dialog.

## Linux headless (only if resuming on the Linux box again)

`source ~/.local/qtdeps/env.sh` before any `uv run` (GL/fontconfig/X libs and
Inter/DejaVu fonts unpacked without root, offscreen Qt with a 1920x1200 screen,
TMPDIR off the small /tmp). Worktrees are under `/home/willyg/code/pMANIC/.claude/worktrees/`
(`feat` is the PR branch), notes at `/home/willyg/code/pMANIC-notes`, scratch
and CI artifacts at `/home/willyg/code/uiux-scratch/`. Push with
`git -c credential.helper= -c credential.helper='!gh auth git-credential' push`.

## Gotchas

- `bench/HILLCLIMB.md` and `src/manic/ui/sample_list_widget.py` changes in the
  Linux main checkout belong to an unrelated session. Never commit them.
- Never commit a `testdata` symlink in a worktree (add `/testdata` to
  `.git/info/exclude`).
- The tour's documentation screenshot can be blank where QWebEngine cannot be
  grabbed; reviewers know.
- Settings save stays per page ("Save this page") on purpose.
- Implementers: Opus in separate worktrees with disjoint file ownership,
  reading `design_spec.md` (binding fences). Review fences with
  `git diff <base> -- src/manic/{processors,models,validation,sheet_generators,io}`
  (must be empty).
