Round 13 (re-rating). Commit `72561139` on `feat/ui-ux-overhaul`.

- Host: a headless Linux box (no display, no root). In EVERY shell, before any
  `uv run`: `source ~/.local/qtdeps/libs.sh` (unpacked GL/font libraries; Inter and
  DejaVu fonts stand in for the system font; TMPDIR off the small /tmp). Ignore the
  reviewer brief's older `env.sh` line: that file forces a 1920x1200 screen. The tour
  renders offscreen on a virtual 2560x1410 screen by default; never pass `--onscreen`.
  Probes of your own set
  `QT_QPA_PLATFORM="offscreen:configfile=<checkout>/scripts/screen2560.json"`.
- Repository checkout to inspect and run: `/home/willyg/code/pMANIC/.claude/worktrees/review-r13`
  (detached at 72561139; `testdata/` is linked). Read-only: change no file in it.
- Notes folder (`<NOTES>`): `/home/willyg/code/pMANIC-notes` (read-only for you).
- Screenshots for this round, all in `<NOTES>/reviews/round-13/shots/`:
  - Real Windows and macOS from the CI runners (small laptop-sized screens):
    `ci-windows-latest-light/`, `ci-windows-latest-dark/`, `ci-macos-15-light/`,
    `ci-macos-15-dark/`.
  - THE PRIMARY TARGET: the user works on a 27" monitor at 2560x1440 (device pixel
    ratio 1.0, 2560x1410 available). Offscreen renders at that size:
    `linux-light-2560x1410/`, `linux-dark-2560x1410/`. Laptop sizes:
    `linux-light-1500x940/`, `linux-dark-1024x720/`; 150% scaling (1707x940 logical
    screen, 1280x800 window): `linux-dark-150pct-1280x800/`. Judge 2560 first.
  View every PNG in every folder. Round 12 screenshots (commit fd447a30): `<NOTES>/reviews/round-12/shots/`.
- Your previous report: {PREV}.
- Your scratch folder (write only here): {SCRATCH}. Save your final report there as
  `report.md` as well as returning it.
- Since round 12 (fd447a30), from both round 12 reports:
  - Quit prompt names the real command (File > Export Session...).
  - Panels: a resized window lays out like a fresh launch (the Summary narrows toward
    its minimum before it closes, so the grid keeps its columns).
  - A and B say why when they cannot act; Settings shows a transient "Saved"; short
    Settings pages are only as tall as they need.
  - Internal-standard chooser and recovery lists: middle-elided names with full-name
    hover, no horizontal scroll bars.
  - Docs: the validation guide no longer equates "no badge" with a healthy peak;
    article headings no longer repeat their category; Quick Start's export step is short.
  - Charts: 30-sample Summary names reach 12 px; Peak area rows too small to draw read
    "0", "<0.01" or "—" like the popup; the unlabelled QC line key stays beside the
    traces while the Summary is open (the Identity footer keeps marks and counts); the
    folded Scale button names the active scale; chart popup headings elide in the
    middle; the detailed view names a sample's fit override.
  - Documentation keeps "Loading…" until the page has drawn, retries once, then offers
    Try Again; the CI macOS dark Quick Start now renders.
  - Binding user directives: clean not cluttered, beautiful, functional first, big
    screens first. Judge clutter strictly.
  Judge the result, not the intent. Re-check each of your round 12 issues and say
  which are fixed, partly fixed or still open.
- Platforms: score every factor at the weakest of Windows/macOS x light/dark, per
  the rubric. Use the CI folders for Windows and macOS.
- Lost functionality: compare against `origin/main` (`git diff origin/main...72561139 -- src/manic/ui`)
  and the running app. Every menu action, shortcut, context-menu command, setting,
  dialog, popup, filter, multi-select, peak verdict, fit control, scale option and
  integration control on main must still exist and work.
- The rubric has nine factors including F9 "Taste (not AI slop)" with the
  redundancy tell; the JSON `overall` is the F1..F9 mean. The user's target is
  10, so be exact about what still stands between each factor and a 10.
