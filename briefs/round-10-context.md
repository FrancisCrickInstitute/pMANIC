Round 10 (re-rating). Commit `4119119` on `feat/ui-ux-overhaul`.

- Host: a Mac (macOS, real display, Retina). Ignore the reviewer brief's Linux
  `env.sh` line: run `uv run` directly. The tour opens real windows for about a
  minute; `--scheme light|dark` forces the appearance. Other agents may run
  tours on this machine at the same time; if a capture misses because another
  window took focus, rerun that step rather than reporting it as an app bug.
- Repository checkout to inspect and run: `/Users/couttsj/Documents/_code/pMANIC-review-r10`
  (detached at 4119119; `testdata/` is ready). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/Users/couttsj/Documents/_code/pMANIC-notes` (read-only for you).
- Screenshots for this round, all in `<NOTES>/reviews/round-10/shots/`:
  - Real Windows and macOS from the CI runners (small laptop-sized screens:
    Windows 1024x720, macOS 1024x681): `ci-windows-latest-light/`,
    `ci-windows-latest-dark/`, `ci-macos-15-light/`, `ci-macos-15-dark/`.
  - THE PRIMARY TARGET: the user works on a 27" monitor at 2560x1440 (device
    pixel ratio 1.0, 2560x1410 available). `offscreen-light-2560x1410/` and
    `offscreen-dark-2560x1410/` are rendered on a virtual 2560x1410 screen with Qt's
    offscreen platform (fonts and widgets real; no native menu bar). Optimise your
    judgement for this size first; laptop sizes must still work.
    To drive it live at 2560 yourself: `QT_QPA_PLATFORM="offscreen:configfile=<NOTES>/briefs/screen2560.json"`
    with `--size 2560x1410` (offscreen renders to images; it does not open a window).
  - Local macOS on a 14" MacBook (1512x949 available; the 1600x1000 request is
    clamped): `mac-light/`, `mac-dark/`.
  - Local macOS at `QT_SCALE_FACTOR=1.5` (screen 1008x633 logical, harsher than a
    real 1280x800 laptop at 150%): `mac-light-150pct-1280x800/`, `mac-dark-150pct-1280x800/`.
  View every PNG in every folder.
- Round 9 screenshots (commit c574eca): `<NOTES>/reviews/round-9/shots/`.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 9 (c574eca), driven by the user's direct requests:
  - Peak verdict colours restored to main's and the exported workbook's meanings
    (Below threshold light red, Accepted light purple, Marked bad tan) as soft
    translucent pastel washes and pastel pills; QC badges never tint the tile.
  - Summary moved out of the sidebar into a resizable right-hand panel beside the
    grid, both charts always visible; the sidebar never shows tabs. Both side
    panels toggle from header buttons and View › Show Sidebar / Show Summary
    (Ctrl+Alt+S / Ctrl+Alt+R), remembered between sessions.
  - Shared Y and Scale to peak are visible toggles in the grid header again (the
    user missed them in the View menu), synced with the View menu.
  - Buttons never touch: segmented controls are separate pills 4 px apart,
    button rows 8 px apart.
  - Settings › General › Appearance: System / Light / Dark, applied at once.
  - Start screen: a quiet link to rebuild an export without CDF files.
  - The searchable standard chooser is used everywhere (checklist, Process
    External Data); the checklist table takes keyboard focus; detailed view has
    previous/next sample; documentation has a Find button; icon buttons and
    status rows have accessible names; clutter removed (empty sidebar sections
    before loading, duplicate qualifier note).
  - The user's directives now binding: clean not cluttered, beautiful,
    functional first, big screens first. Judge clutter strictly.
  - Known limit: the first documentation page may flash blank on CI macOS.
  - Declined: replacing the isotopologue colours; moving the session JSON out of
    `manic_session_export/`; flagging labelled peaks outside the integration
    window (needs a science-side definition; a PR follow-up).
  Judge the result, not the intent. Re-check each of your round 9 issues and say
  which are fixed, partly fixed or still open.
- Platforms: score every factor at the weakest of Windows/macOS x light/dark, per
  the rubric. Use the CI folders for Windows.
- Lost functionality: compare against `origin/main` (`git diff origin/main...4119119 -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
- The rubric has nine factors including F9 "Taste (not AI slop)" with the
  redundancy tell; the JSON `overall` is the F1..F9 mean. The user's target is
  now 10, so be exact about what still stands between each factor and a 10.
