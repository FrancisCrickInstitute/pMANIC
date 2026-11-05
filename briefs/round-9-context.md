Round 9 (re-rating). Commit `1bb490b` on `feat/ui-ux-overhaul`.

- Host: a Mac (macOS, real display, Retina). Ignore the reviewer brief's Linux
  `env.sh` line: run `uv run` directly. The tour opens real windows for about a
  minute; `--scheme light|dark` forces the appearance. Other agents may run
  tours on this machine at the same time; if a capture misses because another
  window took focus, rerun that step rather than reporting it as an app bug.
- Repository checkout to inspect and run: `/Users/couttsj/Documents/_code/pMANIC-review-r9`
  (detached at 1bb490b; `testdata/` is ready). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/Users/couttsj/Documents/_code/pMANIC-notes` (read-only for you).
- Screenshots for this round, all in `<NOTES>/reviews/round-9/shots/`:
  - Real Windows and macOS from the CI runners (small laptop-sized screens:
    Windows 1024x720, macOS 1024x681): `ci-windows-latest-light/`,
    `ci-windows-latest-dark/`, `ci-macos-15-light/`, `ci-macos-15-dark/`.
  - Local macOS on a 14" MacBook (1512x949 available; the 1600x1000 request is
    clamped): `mac-light/`, `mac-dark/`.
  - Local macOS at `QT_SCALE_FACTOR=1.5` (screen 1008x633 logical, harsher than a
    real 1280x800 laptop at 150%): `mac-light-150pct-1280x800/`, `mac-dark-150pct-1280x800/`.
  View every PNG in every folder.
- Round 8 screenshots (commit a696f0b): `<NOTES>/reviews/round-8/shots/`.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 8 (a696f0b) the team worked through both round 8 reports:
  - The keyboard review loop: N, Shift+N, A and B work anywhere in the main
    window except text fields (no more type-ahead in the lists); N selects only
    the tile it lands on, so A and B act on it and the menus name it; A and B
    enable after N; "needs review" means a badge that is neither Accepted nor
    Marked bad; Next/Previous Flagged disable when nothing needs review and N
    then says so in a toast.
  - Export prompt for a standard without an amount uses plain words.
  - Compact tile time labels are spaced by the plot width (no run-together labels).
  - The abundance popup names its quantity (peak area); the label-incorporation
    popup's key reads the current row's percentages (keyboard and hover).
  - Labelled Full scan keeps the isotopologue cluster labelled and coloured.
  - Documentation has Find (Ctrl/Cmd+F).
  - A searchable internal standard chooser (filter field, keyboard) replaces
    the 95-item menu at the sidebar row and Settings › Choose…; compounds with
    an amount come first.
  - Short windows: the compound list keeps about three rows; Samples gives up rows first.
  - Apply window turns primary for its own draft; one "· not applied" form.
  - Section headings report open/closed to screen readers; Peak window fields
    have accessible names. Add Compound scrolls by whole rows.
  - Reference docs: one Algorithm section in Baseline Correction; repeated
    rules stated once with links.
  - Known limit: the first documentation page may flash blank on CI macOS.
  - Declined: replacing the isotopologue colours (user's choice); moving the
    session JSON out of `manic_session_export/`; flagging labelled peaks outside
    the integration window (needs a science-side definition; a PR follow-up).
  Judge the result, not the intent. Re-check each of your round 8 issues and say
  which are fixed, partly fixed or still open.
- Platforms: score every factor at the weakest of Windows/macOS x light/dark, per
  the rubric. Use the CI folders for Windows.
- Lost functionality: compare against `origin/main` (`git diff origin/main...1bb490b -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
- The rubric has nine factors including F9 "Taste (not AI slop)" with the
  redundancy tell; the JSON `overall` is the F1..F9 mean. The user's target is
  now 10, so be exact about what still stands between each factor and a 10.
