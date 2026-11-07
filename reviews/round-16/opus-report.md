# MANIC UI/UX review, round 16 (re-rating at 4f1b3999), reviewer: opus

## Evidence

**Screenshots.** I viewed all 558 PNGs in the nine round-16 folders as 3×3 contact sheets (`sheets/`, 1000 px tiles for the two 2560 folders, 800 px for the rest). I also checked full-resolution crops of the 2560 unlabelled screen in light (`crops/L24_left.png`, `crops/L24_right.png`) and the labelled grid in dark (`crops/D05_left.png`). Short names below:
- `2560L/`, `2560D/`: linux 2560×1410, light and dark (the primary target).
- `WL/`, `WD/`: Windows CI. `ML/`, `MD/`: macOS CI.
- `1500L/`: 1500×940 light. `1024D/`: 1024×720 dark. `150D/`: 150% scaling, 1280×800 window, dark.

**Code.** I read the diff `e640bf03..4f1b3999`. Four UI files changed (33 insertions, 26 deletions):
- `chart_style.py`: `SummaryRows` keeps the last pointer position and gains `refresh()`.
- `targeted_qc_widget.py`: `_on_grid_hovered` now calls `refresh()` instead of showing or hiding the tip itself.
- `identity_chart.py`: the cell tip drops the repeated qualifier prefix.
- `matplotlib_plot_widget.py`: `_on_draw` returns early once `ax` is `None`.

For lost functionality I compared against `origin/main...4f1b3999` and read the menus live.

**My own drive** (`drive16.py` → `body16.py`, offscreen with `screen2560.json`; log in `extra/log.txt`; it reached DONE, and `run.out` has no traceback).

Labelled, at 2560:
- Fresh load: 30 tiles of 303×251 with no scroll, and the toast "Imported 2850 EICs".
- A on an unflagged plot gave "Bio_001 is not Below threshold". A with all plots selected, and with none, explained itself. N gave "No flagged plots in Pyruvate". Then B.
- A Peak window draft ("Bio_002 · not applied") applied.
- tR window 0.3 → Apply window: "Regenerated 30 EICs" in 2.0 s.
- A Peak validation edit, saved: "Saved", cleared 3.5 s later. All seven Settings pages.
- Deconvolution level 4 → 3. The indicator then read "Deconvolution level 3 · automatic peak shape · balanced noise gate".
- Both Summary popups, the detailed view, and a full export: five sheets, toast "Exported export.xlsx".
  - The export took 78 s against 43 s in round 15. My hover probe ran at the same time on the same machine, so I do not read this as a regression.

Resize and menus:
- Resized 2560 → 1920 → 1700 → 1500 → 1280 → 1100 → 1024 → 2560.
  - 1500 gives 5 columns with no scroll.
  - At 1100 the Summary yields.
  - Back at 2560 the layout returns to 6 columns with no scroll.
- Read the Scale menu and every menu bar menu live.

Unlabelled, at 2560:
- 11 tiles of 458×424.
- All 8 compounds. Glycine with the Summary open, closed and reopened.
- 1500 and 1024. The Identity popup, the detailed view, export (5.6 s, three sheets) and a fit override.

**Round-16 probes:**
- `probe16.py` covers four Identity rows at 2560 and at 1500. For each row:
  - a cell tip;
  - one move from the cell onto its own name, then a rest;
  - one move from the cell onto another row's name, then a rest;
  - one move from a column-1 cell to a column-2 cell;
  - leaving the chart.
- `probe16b.py` checks leaving the chart again, waiting out Qt's 300 ms tooltip hide delay.
- `probe15d.py` checks hover and rest on Peak area and Label incorporation rows, including a "No ratio" row.

**Not run:**
- Real OS hover timing.
- The native macOS menu bar.
- Windows at 125% and 150%.
- A real OS scheme switch.
- Delete and Recover, session import, and the quit prompt. Their code has not changed since round 13.

## Verdict

Both round-15 issues are fixed, and I verified each in the running app.
- **One move from an Identity cell onto a name now shows that row's tip.** This holds at 2560 and at 1500, for the cell's own row and for another row. The tip stays after a rest, and leaving the chart hides it. In round 15 the same move showed the stale cell tip or nothing.
- **The cell tip names the qualifier once.** It reads "Sample_04_ratio_fail / Qualifier 1  Failed / expected 0.450  ±25%  observed 0.815", in the Summary and in the popup. The cell and name tips now share one owner, `SummaryRows.refresh()`. The Identity widget no longer calls `QToolTip` itself.
- **No traceback in the drive.** Round 15's run printed the `_on_draw` traceback once. This round's run printed none (`run.out`).

The core workflow works end to end on both datasets. Every screen in the nine folders matches round 15. The 2560 screens are calm and uncluttered in both schemes, and the Windows and macOS CI shots are clean in light and dark. Nothing on `main` is missing.

I found no new defect. Judged strictly for clutter, I found no duplication without a reason (see the F9 table).

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 10 | The tokens hold across all nine folders. At full resolution the 2560 screen has one type scale, quiet hairlines, and colour used only for traces and verdicts (`crops/L24_left.png`, `crops/D05_left.png`). Identity reads as a clean grid over a one-line tally (`crops/L24_right.png`). |
| F2 | Layout and hierarchy | 10 | At 2560: 30 tiles of 303×251 and 11 tiles of 458×424, with no scroll (log `fresh 2560`, `unl 2560`). Resizing lays out like a fresh launch: 1500 gives 5 columns, the Summary yields at 1100, and 2560 returns (log `lab_resize`, `1024D/`, `150D/`). |
| F3 | Onboarding and workflow clarity | 10 | One action per empty state (`*/02`, `*/03`, `*/36`). The checklist has a pattern how-to (`*/04_*_steps`), and Quick Start has a key table (`*/17_…DocumentationViewer.png`). A, N and B explain refusals ("No flagged plots in Pyruvate"). |
| F4 | Consistency and polish | 10 | All three Summary charts now share one hover owner (`chart_style.py:221-246`). Identity's cell tip feeds through the same `refresh()` (`targeted_qc_widget.py:244-253`). The last cell-to-name inconsistency is gone (probe16). |
| F5 | Feedback and state | 10 | Verified live: refusal toasts; "Regenerated 30 EICs"; "Saved", then cleared; "Exported export.xlsx" with a progress dialog; the draft caption "Bio_002 · not applied"; the deconvolution indicator. Hover tips follow the pointer in one move and hide on leave. |
| F6 | Efficiency and flexibility | 10 | Every shortcut is intact (menus read live: Ctrl+O/Shift+O/I/E, Ctrl+Alt+S/R, Ctrl+Shift+Y/P/L/B, Ctrl+F, Ctrl+[ ], Return, Ctrl+A, Esc, N/Shift+N, A, B, F1). Clicking a Summary row selects its plot, including Identity row 10 → MM_01 and the empty Label row 3 → Bio_027. |
| F7 | Data visualisation | 10 | Identity cell tips carry the qualifier, its state, then the numbers, without repeating the qualifier. Name tips list each qualifier's state. The QC key lists only the states present (log `r14_unl`). The detailed view tags qualifier states in its legend (`*/34`). |
| F8 | Modern feel | 10 | On the 27" screen and on both CI platforms, it feels like current, considered software. Panels yield and return, the theme switches live (`*/08_*`), review goes one key at a time, and tips track the pointer exactly. |
| F9 | Taste (not AI slop) | 10 | The tip copy is now as short as it can be: "Qualifier 1  Failed / expected 0.450  ±25%  observed 0.815". The rest stays short and specific: "minutes", "Re-extracts all 11 shown samples", "Qualifier cells ✓ 16 ✕ 2 ? 4". I found no template layouts, decorative chips or ornamental icons. |

Overall: (10×9)/9 = **10.0** (round 15: 10.0).

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| Sidebar and Summary toggles in the header, the View menu, and Ctrl+Alt+S/R | `*/05` | Yes: a menu command, a shortcut, and a button beside its panel. |
| Shared Y / Scale to peak in the header (or the folded Scale button) and the View menu | `*/05`, log `lab_scale_menu` | Yes: a menu command plus a control at the grid. |
| The qualifier QC key in the grid header, with a tally in the Identity footer | `crops/L24_left.png`, `crops/L24_right.png` | Yes: the key names the colours once, and the footer only counts marks. |
| "Qualifier 1" in the cell tip | probe16 | Fixed: it is named once, on the status line. |
| The qualifier gap note in the grid header or in the Identity panel | log `unl_glycine` | Yes: it has one home at a time. |
| The internal standard in the sidebar, the checklist and Settings | `*/04_*`, `*/16_settings_page4` | Yes: each is a place to act on it. |
| The deconvolution indicator in the status bar and in Settings | log `after decon change` | Yes: it appears only when the settings differ from the defaults. |
| The Identity popup key, with swatches and labels | `*/33_identity_popup` | Yes: the popup is a separate window, away from the grid header's key. |
| The Peak area name tip repeats its bar tip | probe15d | Yes: the name and its bar are the same row, and one tip answers both. |

## Top issues, ranked by user impact

No issue survived verification. Below the cut, none affecting a score:
1. **Leaving the chart does not hide the tip at once.** `SummaryRows` clears its pointer on Leave (`chart_style.py:240-241`) but leaves the hiding to Qt. Qt hides the tip after its usual 300 ms delay (probe16b), the same as every other Qt tooltip. No fix needed.
2. **The sidebar standard keeps only "Lactate_…026_long" of a 56-character name.** This is unchanged from round 15. It follows from the sidebar's width, and the full name is on hover.
3. **The internal-standard row's tooltip is long.** "No amount: exports peak areas. The compound list gives this standard no amount, …". This is unchanged. It explains a consequence and its fix, which a tooltip is for.

## Re-rating comparison

**My round-15 issues, status:**
1. **One move from an Identity cell onto a name showed the wrong tip, or none: fixed.**
   - In probe16, the same move on rows 5, 0, 7 and 10, at 2560 and 1500, shows the target row's tip. Examples: "Sample_05_rt_shift / Qualifier 1  Not assessed / Qualifier 2  Not assessed" and "MM_02 / Qualifier 1  Validated / Qualifier 2  Validated".
   - The tip stays after a rest.
   - One move from a cell to the cell beside it shows that cell's tip.
   - Leaving the chart hides the tip once Qt's 300 ms delay has passed.
2. **The detailed view's draw callback ran after cleanup: fixed.** The early return is at `matplotlib_plot_widget.py:792`, and the drive printed no traceback (round 15 printed one).

**Improved beyond the list:** the Identity cell tip no longer repeats "Qualifier N". The status line names it, and the detail line starts at "expected …" (`identity_chart.py:177-186`).

**Regressed:** nothing I could find. The Peak area and Label incorporation tips are unchanged under the shared `refresh()`: hover and rest work on bars, names and the "No ratio" rows (probe15d).

**Lost functionality: none against `origin/main`.**
- The menus read live match round 15:
  - File: 12 actions.
  - View: 8 actions.
  - Review: 11 actions, including Curve Fit with five choices.
  - Help: 4 actions.
- The round-16 diff adds no action and removes none.
- Both exports completed with the same sheets as in round 15 (five labelled, three unlabelled).

**What stands between each factor and a 10:** nothing I could find. All nine factors score 10, and both round-15 issues are closed.

**Per-platform limits:**
- **2560:** offscreen renders plus my drive and probes at that geometry. Not checked: the native title bar, the macOS menu bar, and real hover timing.
- **Windows:** the CI shots are clean in both schemes (`WL/*`, `WD/*`). Not verified on real Windows: 125% and 150% scaling.
- **macOS:** the CI shots are clean in both schemes, including the docs in dark (`MD/17*`). Not checked: the native menu bar and an OS scheme switch.
- **150%:** dark only (`150D/*`), and clean. The dialogs scale without clipping (`150D/18`, `150D/20`, `150D/30`).

```json
{"F1": 10, "F2": 10, "F3": 10, "F4": 10, "F5": 10, "F6": 10, "F7": 10, "F8": 10, "F9": 10, "overall": 10.0}
```
