# MANIC redesign: shared spec for implementers

Goal: move MANIC from about 3.6/10 to 8/10 on the frozen rubric
(`rubric.md` next to this file) as rated by two independent reviewers.
Beautiful, easy, flexible, not clunky science software.

## Hard fences

- **No science changes.** Do not touch `src/manic/processors/`,
  `src/manic/sheet_generators/`, `src/manic/validation/`, `src/manic/models/`,
  `src/manic/io/`, or any calculation, default value, integration rule,
  correction, or exported value. UI code may only call the same functions
  with the same arguments it already does. Validation colour constants
  (`PEAK_VERDICT_FILL`, `QUALIFIER_OUTCOME_FILL`) also feed exports: do not
  edit them; map to UI colours in UI code if needed.
- **No lost functionality.** Every menu action, shortcut, context-menu
  command, setting, dialog, popup, recent-files path, session import/export,
  deletion and recovery, internal standard choice, sample filter/focus,
  multi-select, peak review verdict, fit control, scale option, integration
  control (offsets, tR, tR window, apply, reset, update window), and
  documentation link must still exist and work. Moving a control is fine;
  removing one is not. Keep the native macOS menu bar.
- **Tests:** `uv run python -m pytest -q` must pass (533 at baseline). You may
  update a UI test that asserts a purely cosmetic detail you deliberately
  changed (a colour, a label string, a widget type), keeping what it
  protects. Never weaken a science or behaviour test.
- **Tour:** `uv run python scripts/ui_tour.py <dir>` must keep running with
  `errors: 0`. If you rename an attribute the tour uses, update the tour.
  Run it and look at your screens before you finish.
- Only edit the files your brief assigns. If you truly need a one-line hook
  in a file you don't own, say so in your report instead of editing it.

## Design system

Tokens live in `src/manic/ui/theme.py` (`COLORS`, radii, font sizes).
`style.qss` uses them as `@name` (e.g. `@accent`, `@text_secondary`);
`apply_app_stylesheet` substitutes them. Python-painted widgets and charts
import `theme.color("name")`. Do not introduce new hex literals in UI code
when a token fits; add a token to `theme.py` only if nothing fits (shell
owner only).

- **Typography:** system UI font everywhere (no hard-coded Arial). Base 13px.
  Secondary/meta text 11-12px in `@text_secondary`. Section headings in the
  sidebar only: 11px semibold, uppercase, letter-spacing 0.5px, `@text_tertiary`.
  Dialogs and Settings use sentence-case 13px semibold group titles in `@text`
  (amended after round 4: uppercase on every surface read as generic). Dialog/page
  titles 16px semibold. No all-bold blocks.
- **Spacing:** 4/8/12/16/24 grid. Panels 16px padding, 12px between groups.
- **Surfaces:** window `@bg`; panels and cards `@surface` with one 1px
  `@border` and radius 8, never nested borders. Rows inside a panel get no
  border of their own.
- **Buttons:** height 28px, radius 6, 0 12px padding, 13px medium.
  - Default `QPushButton` is **neutral**: `@surface`, 1px `@border_strong`,
    `@text`; hover `@surface_hover`.
  - **Primary**: `QPushButton:default` or `[variant="primary"]`: `@accent`
    fill, white text; hover `@accent_hover`.
  - **Danger**: `[variant="danger"]`: only for destructive actions (clear
    session, delete, remove all overrides). `@danger` fill, white text.
  - **Ghost/tool**: `[variant="ghost"]`: transparent, `@text_secondary`,
    hover `@surface_hover`.
  - Never style by button text. Cancel/Close/Skip/Reset are neutral.
  - Set a variant with `button.setProperty("variant", "primary")` before
    the widget is shown (or re-polish after).
- **Inputs:** height 28px, radius 6, 1px `@border_strong`, focus border
  `@accent`. Placeholder `@text_tertiary`.
- **Selection:** `@accent` is the selection colour everywhere (list rows use
  `@accent_soft` background with `@text`; selected chart tiles get a 2px
  `@accent` outline). Selection must never look like a QC verdict.
- **Semantic colour:** red (`@danger`) only for failures and destructive
  actions; green (`@success`) only for pass; amber (`@warning`) for review /
  attention. Optional things that are unset are neutral grey, never red.
  Never colour alone: pair with text or an icon.
- **Charts:** isotopologue series keep `colors.label_colors` (meaning is
  learned). Axis text 10px `@text_secondary`, axis lines `@border_strong`,
  gridlines `@grid_line`, no chart frames, white plot area. Fewer ticks;
  no tick text overlapping. Sample captions 11-12px semibold `@text`.
- **Window titles:** "<Thing> — MANIC" for dialogs; main window
  "MANIC — Labelled analysis" style.
- **Empty states:** every empty panel says what goes there and how to fill
  it, with the action as a button.

## Platforms and appearance (added after round 0; binding)

- **macOS and Windows equally.** Every change must look and work as well on
  Windows 10/11 as on macOS. Windows has no native menu bar (the menu sits
  inside the window and must look designed), uses Segoe UI, Ctrl not Cmd,
  and often runs at 125-150% display scaling. Never hard-code a font family;
  use the system font. Show shortcuts with `QKeySequence.toString(NativeText)`
  so labels read ⌘O on Mac and Ctrl+O on Windows. Size in logical px and
  let Qt scale. Check paths with `pathlib`, not string joins.
- **Light and dark mode.** The app follows the OS appearance and switches
  live when it changes. `theme.py` carries a light and a dark token set;
  the stylesheet and every Python-painted widget and chart take colours only
  from the active tokens and re-read them when the scheme changes. No
  hard-coded `white`, `black`, `#fff`, or `Qt.white` in UI code. Charts in
  dark mode get a dark plot area with legible axes; series colours may be
  lightened for contrast but keep their hue and meaning.
- The tour takes `--scheme light|dark`. CI runs it on `windows-latest` and
  `macos-15` in both schemes and uploads the screenshots.

## Taste, not AI slop (added after round 3; binding, scored as F9)

The user wants the app to show real taste and not look AI-generated. Before
you add anything, ask whether a careful human designer working only on MANIC
would put it there.

- One place for each piece of information. Redundancy is generally bad: if
  the sidebar shows what is loaded, the canvas and status bar do not repeat
  it; helper text does not restate its heading; a dialog does not show the
  same value twice. Duplicate only with a clear reason (a menu command that is
  also in a context menu or has a shortcut; a value shown again where the user
  acts on it, far from where it first appears) and be ready to name it.
- Copy is short and specific to GC-MS work. Cut sentences that explain what
  the UI already shows. No "You can also", "Simply", "Let's", or marketing tone.
  Instructions longer than a line belong in the quick start guide.
- No template layouts: no hero-plus-stepper-plus-links empty states, no
  numbered badges for a two-step flow, no card grids of icon, title and blurb.
- No decoration without meaning: no gradients, glows, emoji, ornamental icons
  or badges that carry no information. Accent colour marks the primary action,
  selection and focus, nothing else.
- Prefer restraint and the user's real data (recent files, sample names,
  compound names) over generic explanation.

## User directives after round 4 (binding)

- Climb toward 10, not just 8: beautiful, professional, unique, and above all
  functional. A broken or misleading path outranks any visual polish.
- The user is very happy with how the graphs look. Changes that make them
  better (such as larger Comfortable tiles) are welcome; do not regress their
  look or swap their established colours and meaning.
- No redundant code or tests. Every line and every test must earn its place.
  Prefer deleting dead code, one-caller wrappers and duplicated helpers. A new
  test must protect a behaviour a user would notice; do not add tests that
  restate the implementation, pin copy, or duplicate an existing test.

## User directives, round 10 (binding)

- Clean, not cluttered. Every new label, badge, hint, button or line must earn
  its place; prefer removing to adding. Never remove something genuinely useful.
- Spacing between buttons matters everywhere: adjacent buttons, including the
  segments of a segmented control, never touch; keep a consistent gap (at least
  4 px inside a segmented control, 8 px between separate buttons).
- Peak verdict colours keep main's and the workbook's meanings (Below threshold
  light red, Accepted light purple, Marked bad tan), drawn as soft translucent
  pastel washes and pastel pills, never solid or bold fills.
