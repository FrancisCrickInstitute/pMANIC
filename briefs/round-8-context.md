Round 8 (re-rating). Commit `a696f0b` on `feat/ui-ux-overhaul`.

- Host: a Mac (macOS, real display, Retina). Ignore the reviewer brief's Linux
  `env.sh` line: run `uv run` directly. The tour opens real windows for about a
  minute; `--scheme light|dark` forces the appearance. Other agents may run
  tours on this machine at the same time; if a capture misses because another
  window took focus, rerun that step rather than reporting it as an app bug.
- Repository checkout to inspect and run: `/Users/couttsj/Documents/_code/pMANIC-review-r8`
  (detached at a696f0b; `testdata/` is ready). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/Users/couttsj/Documents/_code/pMANIC-notes` (read-only for you).
- Screenshots for this round, all in `<NOTES>/reviews/round-8/shots/`:
  - Real Windows and macOS from the CI runners (small laptop-sized screens:
    Windows 1024x720, macOS 1024x681): `ci-windows-latest-light/`,
    `ci-windows-latest-dark/`, `ci-macos-15-light/`, `ci-macos-15-dark/`.
  - Local macOS on a 14" MacBook (1512x949 available; the 1600x1000 request is
    clamped): `mac-light/`, `mac-dark/`.
  - Local macOS at `QT_SCALE_FACTOR=1.5` (screen 1008x633 logical, harsher than a
    real 1280x800 laptop at 150%): `mac-light-150pct-1280x800/`, `mac-dark-150pct-1280x800/`.
  View every PNG in every folder.
- Round 7 screenshots (commit b804ecf): `<NOTES>/reviews/round-7/shots/`.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 7 (b804ecf) the team worked through both round 7 reports:
  - Unapplied tR window edits are kept and marked "not applied", like the offsets.
  - Choosing an internal standard without an amount says so on its status row.
  - Every confirmation uses verb buttons with Cancel as the default (Reset,
    both export prompts, import, new session, quit, update).
  - Apply is primary only while there is an unapplied edit.
  - New: a red "tR off" tile badge when the Q-ion apex is outside the tR
    tolerance (before, such samples showed a clean tile though export flagged them).
  - N / Shift+N move to the next / previous plot that still needs review;
    View › Compact / Comfortable; the density control is keyboard-focusable.
  - Spectrum: own-ion labels always fit; a Full scan toggle; Reset all returns
    to the opening view. Abundance popup: zero vs missing, 4-figure current row,
    long names elided with the full name on hover and focus. No phantom
    qualifier chip. The detailed key names raw signal, other fitted peaks and baseline.
  - Short windows: Baseline and tR window open as a popover so the lists keep
    their rows; the compound list keeps the current compound in view.
  - Settings' Internal standard row has a Choose… button that opens the same
    menu as the sidebar.
  - Docs render source line wraps as prose (no mid-sentence breaks), and were
    checked against the app.
  - Known limit: the first documentation page may flash blank on CI macOS. Two
    fixes that waited for the first painted frame crashed QtWebEngine and were dropped.
  - Declined: replacing the isotopologue colours (user's choice); moving the
    session JSON out of `manic_session_export/`.
  Judge the result, not the intent. Re-check each of your round 7 issues and say
  which are fixed, partly fixed or still open.
- Platforms: score every factor at the weakest of Windows/macOS x light/dark, per
  the rubric. Use the CI folders for Windows.
- Lost functionality: compare against `origin/main` (`git diff origin/main...a696f0b -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
- The rubric has nine factors including F9 "Taste (not AI slop)" with the
  redundancy tell; the JSON `overall` is the F1..F9 mean. The user's target is
  now 10, so be exact about what still stands between each factor and a 10.
