Round 5 (re-rating). Commit `6ec219c` on `feat/ui-ux-overhaul`.

- Host: a Mac (macOS, real display, Retina). Ignore the reviewer brief's Linux
  `env.sh` line: run `uv run` directly. The tour opens real windows for about a
  minute; `--scheme light|dark` forces the appearance. Other agents may run
  tours on this machine at the same time; if a capture misses because another
  window took focus, rerun that step rather than reporting it as an app bug.
- Repository checkout to inspect and run: `/Users/couttsj/Documents/_code/pMANIC-review-r5`
  (detached at 6ec219c; `testdata/` is ready). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/Users/couttsj/Documents/_code/pMANIC-notes` (read-only for you).
- Screenshots for this round, all in `<NOTES>/reviews/round-5/shots/`:
  - Real Windows and macOS from the CI runners (small laptop-sized screens:
    Windows 1024x720, macOS 1024x681): `ci-windows-latest-light/`,
    `ci-windows-latest-dark/`, `ci-macos-15-light/`, `ci-macos-15-dark/`.
  - Local macOS on a 14" MacBook (1512x949 available; the 1600x1000 request is
    clamped): `mac-light/`, `mac-dark/`.
  - Local macOS at `QT_SCALE_FACTOR=1.5` (screen 1008x633 logical, harsher than a
    real 1280x800 laptop at 150%): `mac-light-150pct-1280x800/`, `mac-dark-150pct-1280x800/`.
  View every PNG in every folder.
- Round 4 screenshots (commit 5cf5d336): `<NOTES>/reviews/round-4/shots/`.
- Your previous report: {PREV}. The round 4 redundancy audit, which the team
  worked through, is `<NOTES>/reviews/round-4/redundancy-audit-sol.md`.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 4 (5cf5d336) the team worked through both round 4 reports and 51
  "remove" rows of the redundancy audit:
  - Start screen: the user chose a drop-zone design from three prototypes. The
    empty canvas shows one line, one button, recent files for the current step
    and one footer line; a dashed outline and tint appear only during a drag.
  - One place for each piece of state: the status bar no longer recaps the
    workspace; the sidebar header shows load status only; each count appears once;
    the Apply scope is stated once; a section's summary hides while it is open.
  - Peak window Reset/Apply row pinned on short windows.
  - Identity's missing-ratio guidance now points to the compound list (the
    round 4 regression); sidebar summaries keep their value axis, no heavy fade,
    "—" for missing ratios, selection scrolled into view.
  - Detailed view: larger text, taller chromatogram, theme colours, shorter footer.
  - Compact density is now visibly denser; Comfortable tiles are larger (the user
    approved this).
  - Documentation shows loading and failure states.
  - Dialogs: one sentence-case type scale (uppercase headings only in the
    sidebar); one per-sample fit editor in Settings (two could disagree); shorter
    Settings, checklist, recovery and Add Compound copy; Internal Standard page
    chooses the standard; Export Options asks before the save location.
  - Bugs fixed: sample-list right-click menu crashed; the status-bar
    deconvolution status was blank after loading until another compound was picked.
  Judge the result, not the intent. Re-check each of your round 4 issues and say
  which are fixed, partly fixed or still open.
- Platforms: score every factor at the weakest of Windows/macOS x light/dark, per
  the rubric. Use the CI folders for Windows.
- Lost functionality: compare against `origin/main` (`git diff origin/main...6ec219c -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
- The rubric has nine factors including F9 "Taste (not AI slop)" with the
  redundancy tell; the JSON `overall` is the F1..F9 mean. The user's target is
  now 10, so be exact about what still stands between each factor and a 10.
