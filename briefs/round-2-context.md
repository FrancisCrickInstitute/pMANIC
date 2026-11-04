Round 2 (re-rating). Commit `6fc71eb5` on `feat/ui-ux-overhaul`.

- Repository checkout to inspect and run: `/home/willyg/code/pMANIC/.claude/worktrees/review-r2`
  (detached at 6fc71eb5; `testdata/` is ready). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/home/willyg/code/pMANIC-notes` (read-only for you).
- Screenshots for this round: `<NOTES>/reviews/round-2/shots/linux-light/`,
  `linux-dark/`, and `linux-dark-150pct-1280x800/` (Windows-laptop stand-in).
  View every PNG in light and dark.
- Round 1 screenshots (macOS light, commit 9a09a4c): `<NOTES>/reviews/round-1/shots/`.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 1 the team: added dark mode following the OS with live switching;
  made dialogs shrink on short or scaled screens; and worked through the round 1
  findings (sidebar state, browsing room, Review menu, sample list checkboxes,
  grid title, legend wrap, QC units, popup labels, detailed view, Add Compound,
  Settings, docs, tour). Judge the result, not the intent.
- Platforms: there are no macOS or Windows screenshots this round (the CI job that
  makes them is waiting on a GitHub permission). Rate from the Linux renders, the
  150% run and the code (Fusion style, tokens, native shortcut text); state per
  factor what you could not verify on macOS/Windows. Do not cap a factor for
  missing evidence alone; cap it only for a broken layout you can see or read in code.
- Lost functionality: compare against `origin/main` (`git diff origin/main...6fc71eb5 -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
