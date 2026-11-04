Round 3 (re-rating). Commit `795ecbe6` on `feat/ui-ux-overhaul`.

- Repository checkout to inspect and run: `/home/willyg/code/pMANIC/.claude/worktrees/review-r3`
  (detached at 795ecbe6; `testdata/` is ready). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/home/willyg/code/pMANIC-notes` (read-only for you).
- Screenshots for this round: `<NOTES>/reviews/round-3/shots/linux-light/`,
  `linux-dark/`, `linux-light-150pct-1280x800/` and `linux-dark-150pct-1280x800/` (Windows-laptop stand-ins).
  View every PNG in light and dark.
- Round 2 screenshots (commit 6fc71eb5): `<NOTES>/reviews/round-2/shots/`. Round 1 (macOS light): `reviews/round-1/shots/`.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 2 (6fc71eb5) the team worked through both round 2 reports: one review API
  and wording for the Review and plot menus; per-chart reset back in the detailed view;
  laptop sidebar layout; empty state for zero shown samples; batch Accept on the eligible
  set; readable sidebar summaries; one popup sample order and popup rows that jump to
  plots; QC state marks; contrast; checklist correction path; onboarding docs; new tour
  steps (31-34). Judge the result, not the intent. Re-check each of your round 2 issues
  and say which are fixed, partly fixed or still open.
- Platforms: there are no macOS or Windows screenshots this round (the CI job that
  makes them is waiting on a GitHub permission). Rate from the Linux renders, the
  150% run and the code (Fusion style, tokens, native shortcut text); state per
  factor what you could not verify on macOS/Windows. Do not cap a factor for
  missing evidence alone; cap it only for a broken layout you can see or read in code.
- Lost functionality: compare against `origin/main` (`git diff origin/main...795ecbe6 -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
