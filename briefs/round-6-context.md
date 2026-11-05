Round 6 (re-rating). Commit `1581a94` on `feat/ui-ux-overhaul`.

- Host: a Mac (macOS, real display, Retina). Ignore the reviewer brief's Linux
  `env.sh` line: run `uv run` directly. The tour opens real windows for about a
  minute; `--scheme light|dark` forces the appearance. Other agents may run
  tours on this machine at the same time; if a capture misses because another
  window took focus, rerun that step rather than reporting it as an app bug.
- Repository checkout to inspect and run: `/Users/couttsj/Documents/_code/pMANIC-review-r6`
  (detached at 1581a94; `testdata/` is ready). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/Users/couttsj/Documents/_code/pMANIC-notes` (read-only for you).
- Screenshots for this round, all in `<NOTES>/reviews/round-6/shots/`:
  - Real Windows and macOS from the CI runners (small laptop-sized screens:
    Windows 1024x720, macOS 1024x681): `ci-windows-latest-light/`,
    `ci-windows-latest-dark/`, `ci-macos-15-light/`, `ci-macos-15-dark/`.
  - Local macOS on a 14" MacBook (1512x949 available; the 1600x1000 request is
    clamped): `mac-light/`, `mac-dark/`.
  - Local macOS at `QT_SCALE_FACTOR=1.5` (screen 1008x633 logical, harsher than a
    real 1280x800 laptop at 150%): `mac-light-150pct-1280x800/`, `mac-dark-150pct-1280x800/`.
  View every PNG in every folder.
- Round 5 screenshots (commit 6ec219c): `<NOTES>/reviews/round-5/shots/`.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 5 (6ec219c) the team worked through both round 5 reports:
  - A code-quality cleanup removed dead code, duplicated helpers and redundant
    tests (pixel-identical screenshots before and after).
  - Session export now names the file it actually wrote (a bug also on main);
    data and session export confirm in a toast with Show in Folder; Clear Session
    states once what it removes.
  - Peak window: offsets and Reset/Apply are one group that never scrolls; the
    default-scope caption is gone; Ctrl/Cmd+Return applies.
  - Summary on short windows shows one chart at full height, the other folded
    to its title; unlabelled Summary no longer clips its qualifier columns.
  - Keyboard verdicts: A accepts or clears acceptance, B marks or clears bad,
    in the plot grid only, shown in both menus.
  - The Display tab moved into the View menu (Shared Y-Scale, Scale to Selected Peak).
  - A compound-level QC gap is one grid-header note with a link to a new User
    Guide section, not an amber badge on every tile; "Not assessed" everywhere.
  - Detailed view: TIC and spectrum side by side under the EIC, larger text,
    footer with tR and integration window only.
  - Documentation shows Loading on every page request.
  - Settings: short option names with "?" help, Save/Revert footer, the
    Internal Standard page names the standard instead of a fourth chooser; mode
    chooser with two equal options; Add Compound ion errors under their rows.
  - Declined: replacing the isotopologue colours (the user likes the graphs and
    users know what the colours mean). Do not score down for keeping them.
  Judge the result, not the intent. Re-check each of your round 5 issues and say
  which are fixed, partly fixed or still open.
- Platforms: score every factor at the weakest of Windows/macOS x light/dark, per
  the rubric. Use the CI folders for Windows.
- Lost functionality: compare against `origin/main` (`git diff origin/main...1581a94 -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
- The rubric has nine factors including F9 "Taste (not AI slop)" with the
  redundancy tell; the JSON `overall` is the F1..F9 mean. The user's target is
  now 10, so be exact about what still stands between each factor and a 10.
