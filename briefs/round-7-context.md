Round 7 (re-rating). Commit `b804ecf` on `feat/ui-ux-overhaul`.

- Host: a Mac (macOS, real display, Retina). Ignore the reviewer brief's Linux
  `env.sh` line: run `uv run` directly. The tour opens real windows for about a
  minute; `--scheme light|dark` forces the appearance. Other agents may run
  tours on this machine at the same time; if a capture misses because another
  window took focus, rerun that step rather than reporting it as an app bug.
- Repository checkout to inspect and run: `/Users/couttsj/Documents/_code/pMANIC-review-r7`
  (detached at b804ecf; `testdata/` is ready). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/Users/couttsj/Documents/_code/pMANIC-notes` (read-only for you).
- Screenshots for this round, all in `<NOTES>/reviews/round-7/shots/`:
  - Real Windows and macOS from the CI runners (small laptop-sized screens:
    Windows 1024x720, macOS 1024x681): `ci-windows-latest-light/`,
    `ci-windows-latest-dark/`, `ci-macos-15-light/`, `ci-macos-15-dark/`.
  - Local macOS on a 14" MacBook (1512x949 available; the 1600x1000 request is
    clamped): `mac-light/`, `mac-dark/`.
  - Local macOS at `QT_SCALE_FACTOR=1.5` (screen 1008x633 logical, harsher than a
    real 1280x800 laptop at 150%): `mac-light-150pct-1280x800/`, `mac-dark-150pct-1280x800/`.
  View every PNG in every folder.
- Round 6 screenshots (commit 1581a94): `<NOTES>/reviews/round-6/shots/`.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 6 (1581a94) the team worked through both round 6 reports:
  - Restored the abundance popup's precise readout (three significant figures
    on the row under the pointer or keyboard focus), lost since main.
  - Identity columns come from the compound's own qualifiers; a compound with
    no assessable qualifier also gets the grid-header note and guide link.
  - Detailed legend wraps (all channels shown); labelled spectrum opens on the
    isotopologue cluster (Reset all shows the full scan); larger popup text;
    neutral abundance bars with the accent for selected samples; "Qualifier QC:".
  - Unapplied peak-window edits are kept per compound and target and marked
    "not applied" until Apply or Reset.
  - Clear Session defaults to Cancel; session import asks once with Cancel and
    Import Overrides; routine successes (regeneration, import) are toasts;
    toasts stay inside the window; the start footer holds links only.
  - Short windows: offsets group whole, Samples keeps three rows, Baseline and
    tR window fold behind a labelled row showing their values.
  - Settings: the one-row pages merged into one General page; Settings sizes to
    its content. Checklist keeps its pattern help in view at 150%.
  - Documentation navigation groups pages under headings with short labels.
    An attempt to delay the reveal until first paint crashed QtWebEngine and was
    reverted, so the first page may still flash blank briefly on CI macOS.
  - Quick Start's keyboard table lists the new keys.
  - Declined: replacing the isotopologue colours (user's choice); writing the
    session JSON outside the `manic_session_export/` folder main has always used
    (the toast names the real folder).
  Judge the result, not the intent. Re-check each of your round 6 issues and say
  which are fixed, partly fixed or still open.
- Platforms: score every factor at the weakest of Windows/macOS x light/dark, per
  the rubric. Use the CI folders for Windows.
- Lost functionality: compare against `origin/main` (`git diff origin/main...b804ecf -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
- The rubric has nine factors including F9 "Taste (not AI slop)" with the
  redundancy tell; the JSON `overall` is the F1..F9 mean. The user's target is
  now 10, so be exact about what still stands between each factor and a 10.
