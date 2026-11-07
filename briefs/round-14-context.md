Round 14 (re-rating). Commit `b99e2e22` on `feat/ui-ux-overhaul`.

- Host: a headless Linux box (no display, no root). In EVERY shell, before any
  `uv run`: `source ~/.local/qtdeps/libs.sh` (unpacked GL/font libraries; Inter and
  DejaVu fonts stand in for the system font; TMPDIR off the small /tmp). Ignore the
  reviewer brief's older `env.sh` line: that file forces a 1920x1200 screen. The tour
  renders offscreen on a virtual 2560x1410 screen by default; never pass `--onscreen`.
  Probes of your own set
  `QT_QPA_PLATFORM="offscreen:configfile=<checkout>/scripts/screen2560.json"`.
- Repository checkout to inspect and run: `/home/willyg/code/pMANIC/.claude/worktrees/review-r14`
  (detached at b99e2e22; `testdata/` is linked). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/home/willyg/code/pMANIC-notes` (read-only for you).
- Screenshots for this round, all in `<NOTES>/reviews/round-14/shots/`:
  - Real Windows and macOS from the CI runners (small laptop-sized screens):
    `ci-windows-latest-light/`, `ci-windows-latest-dark/`, `ci-macos-15-light/`,
    `ci-macos-15-dark/`.
  - THE PRIMARY TARGET: the user works on a 27" monitor at 2560x1440 (device pixel
    ratio 1.0, 2560x1410 available). Offscreen renders at that size:
    `linux-light-2560x1410/`, `linux-dark-2560x1410/`. Laptop sizes:
    `linux-light-1500x940/`, `linux-dark-1024x720/`; 150% scaling (1707x940 logical
    screen, 1280x800 window): `linux-dark-150pct-1280x800/`. Judge 2560 first.
  View every PNG in every folder. Round 13 screenshots (commit 72561139): `<NOTES>/reviews/round-13/shots/`.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 13 (72561139), from both round 13 reports:
  - Settings: a long internal-standard name elides in the middle and Choose stays in
    view; the per-sample fit table keeps Fit type whole, elides sample names and never
    scrolls sideways; the Deconvolution and Qualifier ratios headings elide long names.
  - Start screen: recent files with long names keep room for their folder; full path
    on hover. Checklist: shortened names and matched files give the full text on hover.
  - Peak window names its unit ("minutes") once; a refused A/B toast clears when the
    next review goes through.
  - Summary: one name size and elision rule whether or not a plot is selected (150%);
    every row answers hover (zero rows too) and a single click selects its sample;
    validated checkmarks reach 4.5:1 on their cells.
  - Qualifier QC key: lists only the states the compound shows (hidden when nothing is
    assessed); the Identity footer is a tally, so the key appears once.
  - Popup hint says what the keys do; the enlarge tooltip is shorter.
  - The documentation Loading fix holds on CI macOS dark (two runs).
  - Binding user directives: clean not cluttered, beautiful, functional first, big
    screens first. Judge clutter strictly.
  Judge the result, not the intent. Re-check each of your round 13 issues and say
  which are fixed, partly fixed or still open.
- Platforms: score every factor at the weakest of Windows/macOS x light/dark, per
  the rubric. Use the CI folders for Windows and macOS.
- Lost functionality: compare against `origin/main` (`git diff origin/main...b99e2e22 -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
- The rubric has nine factors including F9 "Taste (not AI slop)" with the
  redundancy tell; the JSON `overall` is the F1..F9 mean. The user's target is
  10, so be exact about what still stands between each factor and a 10.
