# Handoff: UI/UX hill-climb, finished 2026-11-08

The hill-climb is done. The single PR is open:
https://github.com/FrancisCrickInstitute/pMANIC/pull/271 (`feat/ui-ux-overhaul` -> `main`).

## Where things are
- PR branch `feat/ui-ux-overhaul` at `ecdbc161` (pushed). 821 tests pass, 8 skipped. Offscreen tours
  `errors: 0` at 2560 light/dark, 1500x940, 1024x720 and 150%. No diff under
  `src/manic/{processors,models,validation,sheet_generators,io}`.
- Scores (avg of Sol + Opus, 9-factor rubric): r11 9.2, r12 9.4, r13 9.65, r14-17 9.95, r18 9.65
  (popup crash regression), r19 9.95, r20 10.0 (Sol 10.0, Opus 10.0). Stop predicate met in round 20.
- Pre-PR code review (interrogate, Sol + Opus): 3 rounds, every act-on finding fixed with a test that
  fails without it (`reviews/interrogate/`). Deferred to a follow-up PR: split `settings_window.py`
  pages into a module and move the panel layout out of `main_window.py`.
- Issue #269 (sidebar Total Abundance mislabelled samples on main) is fixed by the PR ("Fixes #269").

## Machine notes (Linux box)
- `source ~/.local/qtdeps/libs.sh` before any `uv run` (GL/font libs without root; TMPDIR off /tmp).
  Do not use `env.sh`: it forces a 1920x1200 screen over the tour's own 2560 screen.
- Test data: `~/code/uiux-testdata` (`generate_bench_data.py --mode both`,
  `generate_unlabelled_synthetic_data.py`), symlinked as `testdata` in each worktree.
- Offscreen, `QTest.mouseMove(window.windowHandle(), ...)` does not move `QCursor.pos()`; hover probes
  must move a widget or call `QCursor.setPos`.
- The UI tour workflow no longer runs on push; it runs on pull requests and `workflow_dispatch`.

## Binding user directives
See `design_spec.md` and `reviewer_brief.md` (Settled decisions). Unchanged.
