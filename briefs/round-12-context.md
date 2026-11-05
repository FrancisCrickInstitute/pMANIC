Round 12 (re-rating). Commit `fd447a30` on `feat/ui-ux-overhaul`.

- Host: a headless Linux box (no display, no root). In EVERY shell, before any
  `uv run`: `source ~/.local/qtdeps/libs.sh` (unpacked GL/font libraries; Inter and
  DejaVu fonts stand in for the system font; TMPDIR off the small /tmp). Ignore the
  reviewer brief's older `env.sh` line: that file forces a 1920x1200 screen. The tour
  renders offscreen on a virtual 2560x1410 screen by default; never pass `--onscreen`.
  Probes of your own set
  `QT_QPA_PLATFORM="offscreen:configfile=<checkout>/scripts/screen2560.json"`.
- Repository checkout to inspect and run: `/home/willyg/code/pMANIC/.claude/worktrees/review-r12`
  (detached at fd447a30; `testdata/` is linked). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/home/willyg/code/pMANIC-notes` (read-only for you).
- Screenshots for this round, all in `<NOTES>/reviews/round-12/shots/`:
  - Real Windows and macOS from the CI runners (small laptop-sized screens):
    `ci-windows-latest-light/`, `ci-windows-latest-dark/`, `ci-macos-15-light/`,
    `ci-macos-15-dark/`.
  - THE PRIMARY TARGET: the user works on a 27" monitor at 2560x1440 (device pixel
    ratio 1.0, 2560x1410 available). Offscreen renders at that size:
    `linux-light-2560x1410/`, `linux-dark-2560x1410/`. Laptop sizes:
    `linux-light-1500x940/`, `linux-dark-1024x720/`; 150% scaling (1707x940 logical
    screen, 1280x800 window): `linux-dark-150pct-1280x800/`. Judge 2560 first.
  View every PNG in every folder. Round 11 screenshots stayed on the old machine.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 11 (86a53c3), from both round 11 reports:
  - Lists: long compound and sample names cut in the middle with the full name on
    hover; no horizontal scroll bars.
  - The sidebar's right divider runs the full height; a folded Peak window edit shows
    its value; cut section summaries show in full on hover.
  - Peak validation help no longer names a colour; the status bar names deconvolution
    only when it departs from the default.
  - The Summary opens on its own only with room for three grid columns, and closes
    (without saving) when the window narrows past that.
  - Quick Start: short review steps; rare procedures moved to the User Guide.
  - Charts: a short cohort's Summary stays together at the top; Summary names grow with
    roomy rows; the qualifier gap message has one home (the Summary while it is open);
    the channel legend is plain swatches and names; long names cut in the middle in the
    grid and detailed-view headers; the smallest fit-on-screen tile is larger (165x120),
    else the grid scrolls large tiles; a narrow header folds the two scale toggles into
    a Scale menu so it stays one row.
  - Fixed a freeze: at some tile widths a plot's time-axis ticks flipped between two
    steps forever and hung the app.
  - Binding user directives: clean not cluttered, beautiful, functional first, big
    screens first. Judge clutter strictly.
  - Known limit: the first documentation page may flash blank on CI macOS.
  Judge the result, not the intent. Re-check each of your round 11 issues and say
  which are fixed, partly fixed or still open.
- Platforms: score every factor at the weakest of Windows/macOS x light/dark, per
  the rubric. Use the CI folders for Windows and macOS.
- Lost functionality: compare against `origin/main` (`git diff origin/main...fd447a30 -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
- The rubric has nine factors including F9 "Taste (not AI slop)" with the
  redundancy tell; the JSON `overall` is the F1..F9 mean. The user's target is
  10, so be exact about what still stands between each factor and a 10.
