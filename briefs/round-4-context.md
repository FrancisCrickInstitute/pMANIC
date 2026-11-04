Round 4 (re-rating). Commit `5cf5d336` on `feat/ui-ux-overhaul`.

- Host: this round runs on a Mac (macOS, real display, Retina). Ignore the
  reviewer brief's Linux `env.sh` line: run `uv run` directly. The tour opens
  real windows for about a minute; `--scheme light|dark` forces the appearance.
- Repository checkout to inspect and run: `/Users/couttsj/Documents/_code/pMANIC-review-r4`
  (detached at 5cf5d336; `testdata/` is ready). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/Users/couttsj/Documents/_code/pMANIC-notes` (read-only for you).
- Screenshots for this round, all in `<NOTES>/reviews/round-4/shots/`:
  - Real Windows and macOS from the CI runners (GitHub Actions, small laptop-sized
    screens: Windows 1024x720, macOS 1024x681): `ci-windows-latest-light/`,
    `ci-windows-latest-dark/`, `ci-macos-15-light/`, `ci-macos-15-dark/`.
    These are the first real Windows screenshots of the project. Judge Windows
    from them.
  - Local macOS on a 14" MacBook (Retina, 1512x949 available): `mac-light/`,
    `mac-dark/`. The tour asks for 1600x1000, so macOS clamps the window to
    the screen.
  - Local macOS at `QT_SCALE_FACTOR=1.5` (a 150% laptop stand-in):
    `mac-light-150pct-1280x800/`, `mac-dark-150pct-1280x800/`. At 1.5x the
    screen is 1008x633 logical, so the window is clamped to that: harsher than
    a real 1280x800 laptop at 150%.
  View every PNG in every folder. Downscaled contact sheets are fine for the
  first pass; open full size wherever a detail matters.
- Round 3 screenshots (commit 795ecbe6, Linux): `<NOTES>/reviews/round-3/shots/`.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 3 (795ecbe6) the team worked through both round 3 reports:
  - Grid: selection and focus kept when a fit or scale change re-plots the same
    compound, and the inspector keeps "Applies to N selected". Group Accept and
    Mark as Bad act on the not-yet-done eligible peaks and say "Clear Acceptance
    (n Peaks)" only when all are done. The context menu is ordered and named like
    the Review menu. Comfortable density uses 11px chart text and 13px captions.
    A "Not detected" pill and a stronger tint.
  - Popups, detailed view and QC: keyboard navigation from the popup's real
    initial focus; value axis pinned while rows scroll; "—" for samples with no
    ratio; a "Double-click a chart to reset it" hint; plain status words in
    legends; a one-line message when a compound has no expected ratios; an
    M+0…M+n spectrum bracket; the sidebar Identity chart scrolls with readable
    rows and highlights the selection instead of filtering.
  - Sidebar and checklist: the checklist body scrolls with a fixed footer, and
    the change-a-pattern steps sit behind a disclosure; the Apply window caption
    reads "Re-extracts all N shown samples"; summary charts name every sample and
    scroll; on short windows a pinned "Peak window · Display · Summary" switcher;
    lists keep at least 4 compound and 3 sample rows.
  - CI now screenshots the tour on real Windows and macOS runners.
  Judge the result, not the intent. Re-check each of your round 3 issues and say
  which are fixed, partly fixed or still open.
- Platforms: score every factor at the weakest of Windows/macOS x light/dark, per
  the rubric. Use the CI folders for Windows. Say per factor what you could not
  verify (for example, 150% scaling on real Windows).
- Lost functionality: compare against `origin/main` (`git diff origin/main...5cf5d336 -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
