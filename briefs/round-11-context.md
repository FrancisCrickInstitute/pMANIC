Round 11 (re-rating). Commit `86a53c3` on `feat/ui-ux-overhaul`.

- Host: a Mac (macOS, real display, Retina). Ignore the reviewer brief's Linux
  `env.sh` line: run `uv run` directly. The tour opens real windows for about a
  minute; `--scheme light|dark` forces the appearance. Other agents may run
  tours on this machine at the same time; if a capture misses because another
  window took focus, rerun that step rather than reporting it as an app bug.
- Repository checkout to inspect and run: `/Users/couttsj/Documents/_code/pMANIC-review-r11`
  (detached at 86a53c3; `testdata/` is ready). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/Users/couttsj/Documents/_code/pMANIC-notes` (read-only for you).
- Screenshots for this round, all in `<NOTES>/reviews/round-11/shots/`:
  - Real Windows and macOS from the CI runners (small laptop-sized screens:
    Windows 1024x720, macOS 1024x681): `ci-windows-latest-light/`,
    `ci-windows-latest-dark/`, `ci-macos-15-light/`, `ci-macos-15-dark/`.
  - THE PRIMARY TARGET: the user works on a 27" monitor at 2560x1440 (device
    pixel ratio 1.0, 2560x1410 available). This round the shots are REAL captures
    on that monitor: `real-light-2560x1410/`, `real-dark-2560x1410/`. Laptop-size
    windows on the same screen: `real-*-1500x940/`; 150% scaling (1707x940 logical
    screen, 1280x800 window): `real-*-150pct-1280x800/`. Judge 2560 first.
    To drive the app at 2560 yourself, run it normally (the monitor is attached),
    or offscreen with `QT_QPA_PLATFORM="offscreen:configfile=<NOTES>/briefs/screen2560.json"`.
  - Local macOS on a 14" MacBook (1512x949 available; the 1600x1000 request is
    clamped): `mac-light/`, `mac-dark/`.
  - Local macOS at `QT_SCALE_FACTOR=1.5` (screen 1008x633 logical, harsher than a
    real 1280x800 laptop at 150%): `mac-light-150pct-1280x800/`, `mac-dark-150pct-1280x800/`.
  View every PNG in every folder.
- Round 10 screenshots (commit 4119119): `<NOTES>/reviews/round-10/shots/`.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 10 (4119119), from both round 10 reports and the user's direct requests:
  - The rebuild-from-Raw-Values flow refuses unsupported (unlabelled) input up
    front; the start-screen link shows only in labelled mode.
  - Sidebar sections hug their content at 2560 (Peak window right under Samples);
    the sidebar is never squeezed below its content; the Summary closes itself only
    when the window genuinely cannot fit all three panels.
  - Dark verdict washes are distinct (rose, lavender, tan); Not detected tiles show
    their raw traces clearly; Identity passes are quiet; Summary rows grow.
  - Summary hover tooltips had no background (a chart view's stylesheet leaked into
    them); fixed.
  - Settings split into one page per topic, Appearance set apart; Appearance has no
    Save/Revert (it applies at once).
  - Compact/Comfortable removed (the user did not understand it): tiles shrink to
    fit every sample on one screen down to a readable minimum; a grid that must
    scroll uses large tiles.
  - Header: Documentation icon removed (F1, Help › Documentation, start-screen link remain).
  - Binding user directives: clean not cluttered, beautiful, functional first, big
    screens first. Judge clutter strictly.
  - Known limit: the first documentation page may flash blank on CI macOS.
  - Declined: replacing the isotopologue colours; moving the session JSON out of
    `manic_session_export/`; flagging labelled peaks outside the integration
    window (needs a science-side definition; a PR follow-up).
  Judge the result, not the intent. Re-check each of your round 10 issues and say
  which are fixed, partly fixed or still open.
- Platforms: score every factor at the weakest of Windows/macOS x light/dark, per
  the rubric. Use the CI folders for Windows.
- Lost functionality: compare against `origin/main` (`git diff origin/main...86a53c3 -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
- The rubric has nine factors including F9 "Taste (not AI slop)" with the
  redundancy tell; the JSON `overall` is the F1..F9 mean. The user's target is
  now 10, so be exact about what still stands between each factor and a 10.
