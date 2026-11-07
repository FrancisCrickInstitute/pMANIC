Round 19 (re-rating). Commit `f2c42d2c` on `feat/ui-ux-overhaul`.

- Host: a headless Linux box (no display, no root). In EVERY shell, before any
  `uv run`: `source ~/.local/qtdeps/libs.sh` (unpacked GL/font libraries; Inter and
  DejaVu fonts stand in for the system font; TMPDIR off the small /tmp). Ignore the
  reviewer brief's older `env.sh` line: that file forces a 1920x1200 screen. The tour
  renders offscreen on a virtual 2560x1410 screen by default; never pass `--onscreen`.
  Probes of your own set
  `QT_QPA_PLATFORM="offscreen:configfile=<checkout>/scripts/screen2560.json"`.
- Repository checkout to inspect and run: `/home/willyg/code/pMANIC/.claude/worktrees/review-r19`
  (detached at f2c42d2c; `testdata/` is linked). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/home/willyg/code/pMANIC-notes` (read-only for you).
- Screenshots for this round, all in `<NOTES>/reviews/round-19/shots/`:
  - Real Windows and macOS from the CI runners (small laptop-sized screens):
    `ci-windows-latest-light/`, `ci-windows-latest-dark/`, `ci-macos-15-light/`,
    `ci-macos-15-dark/`.
  - THE PRIMARY TARGET: the user works on a 27" monitor at 2560x1440 (device pixel
    ratio 1.0, 2560x1410 available). Offscreen renders at that size:
    `linux-light-2560x1410/`, `linux-dark-2560x1410/`. Laptop sizes:
    `linux-light-1500x940/`, `linux-dark-1024x720/`; 150% scaling (1707x940 logical
    screen, 1280x800 window): `linux-dark-150pct-1280x800/`. Judge 2560 first.
  View every PNG in every folder. Round 18 screenshots (commit 7434f240): `<NOTES>/reviews/round-18/shots/`.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 18 (7434f240), the two round 18 regressions:
  - Popup crash on reopen: closed chart popups were never deleted; a reference cycle through
    the tooltip owner left their teardown to Python's cyclic GC, which ran while Qt still
    delivered events (AttributeError, then SIGSEGV). Popups now delete themselves when they
    close (all three: Identity, Peak area, Label incorporation); the tooltip owner is a
    child of the viewport it watches. A test opens and closes each popup 30 times per
    scheme in a child process.
  - Stale Summary tip: each Summary chart refreshes its tip whenever its data changes or
    clears, so a resting tip shows the new compound's value (or hides).
  - Binding user directives: clean not cluttered, beautiful, functional first, big
    screens first. Judge clutter strictly.
  Judge the result, not the intent. Re-check each of your round 18 issues and say
  which are fixed, partly fixed or still open.
- Platforms: score every factor at the weakest of Windows/macOS x light/dark, per
  the rubric. Use the CI folders for Windows and macOS.
- Lost functionality: compare against `origin/main` (`git diff origin/main...f2c42d2c -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
- The rubric has nine factors including F9 "Taste (not AI slop)" with the
  redundancy tell; the JSON `overall` is the F1..F9 mean. The user's target is
  10, so be exact about what still stands between each factor and a 10.
