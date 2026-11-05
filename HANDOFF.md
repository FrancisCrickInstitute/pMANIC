# Handoff: UI/UX hill-climb, paused 2026-11-05

## Where things are
- PR branch `feat/ui-ux-overhaul` at `970b288` (pushed). 743 tests pass. Not yet a PR.
- Scores (avg of Sol + Opus, 9-factor rubric, target 10): r4 7.75, r5 8.25, r6 8.8,
  r7 9.05, r8 9.05, r9 9.25, r10 9.1, r11 9.2 (Sol 9.4, Opus 9.0).
- Iteration 14 was in flight when paused:
  - `uiux/r16-shell` at `c2bfbd8` (pushed): all 7 shell findings done and committed,
    tests passing per commit; its final offscreen screenshot check was cut short.
    Base `86a53c3`. Review it, run the suite and tours, merge into the PR branch.
  - `wip/r16-charts` at `177cda4` (pushed): an UNFINISHED snapshot of the charts
    implementer's uncommitted work (11 files, no commits, base `86a53c3`). Not
    verified. Either finish it from that snapshot with a fresh implementer, or
    redispatch the charts brief from scratch. The brief is in the decision log
    row "14" and in this conversation's last iteration; its items are:
    short-cohort Summary stays together, roomy Summary names, one qualifier
    message, plain legend entries (no button capsules), middle-elided names
    everywhere incl. headers, larger fit-on-screen minimum tile, one-row header at 1024.
- Notes branch `uiux-hillclimb-notes` (pushed): decision.tsv (every iteration),
  design_spec.md (binding rules incl. user directives), rubric.md,
  reviewer_brief.md (incl. Settled decisions), briefs/ (implementer common briefs,
  latest `impl-common-r16.md`; round contexts, latest `round-11-context.md`),
  reviews/round-N/ (reports; screenshots are local only, not committed).

## Setup on a new machine
1. `git clone https://github.com/FrancisCrickInstitute/pMANIC.git pythonMANIC`
   `cd pythonMANIC && git checkout feat/ui-ux-overhaul && uv sync`
2. Notes worktree: `git worktree add ../pMANIC-notes uiux-hillclimb-notes`
3. Test data (not in git; ~600 MB on the old machine):
   `uv run python scripts/generate_bench_data.py --mode both` (testdata/bench)
   `uv run python scripts/generate_unlabelled_synthetic_data.py` (testdata/unlabelled_synthetic)
   `testdata/real` and `testdata/manic-unlabelled-test-data` were extra local data;
   copy them over if available, they are not needed by the tour.
4. Check: `uv run python -m pytest -q -p no:cacheprovider` (743 pass) and
   `uv run python scripts/ui_tour.py /tmp/tour --scheme light` (errors: 0).
   The tour renders offscreen on a virtual 2560x1410 screen by default.
5. Paths in briefs and decision rows are absolute to the old machine
   (`/Users/couttsj/Documents/_code/...`); adjust them when re-dispatching.

## Binding user directives (also in design_spec.md)
- Target 10; beautiful, professional, unique, above all functional.
- Clean, not cluttered; never remove something genuinely useful.
- Big screens first: 27in 2560x1440 at DPR 1; laptops must still work.
- Graphs: user likes them; improvements welcome, keep isotopologue colours.
- Peak verdicts keep main/workbook meanings as soft pastel washes and pills.
- Buttons never touch (4 px inside segmented controls, 8 px between buttons).
- Both side panels toggle; Settings one page per topic (empty pages fine).
- No redundant code or tests; tests assert what a user sees.
- Settled, never raise: no out-of-window labelled peak flag; label colours stay;
  session export keeps manic_session_export/; Settings not merged back.
- Agents run every tour/probe offscreen (tour default); never --onscreen except CI.
- Science fence: no diff in src/manic/{processors,models,validation,sheet_generators,io}.
- Known limit: first docs page may flash blank on CI macOS (two first-paint fixes
  crashed QtWebEngine; any docs-viewer loading change needs 30 clean runs).

## Loop (per iteration)
1. Merge implementer branches (fence check, full suite, tours offscreen, look at
   2560 light/dark yourself), fix merge-level issues, push; CI (ui-tour.yml) gives
   Windows/macOS shots.
2. Round N review: write briefs/round-N-context.md from the previous one, shots in
   reviews/round-N/shots/ (tour output + CI artifacts via `gh run download`),
   review checkout `git worktree add --detach ../pMANIC-review-rN <sha>`, dispatch
   Sol (codex gpt-6.1-sol xhigh) and Opus (claude-opus-5-5 high) with reviewer_brief.md.
3. Log an R-row in decision.tsv; split findings into file-disjoint implementer
   groups (claude-opus-5-5 high, worktree isolation) with a new impl-common brief.
4. Stop when the average reaches 10 or plateaus (two rounds gaining < 0.1 with no
   cheap fix left); then cleanup pass and open the single PR.
