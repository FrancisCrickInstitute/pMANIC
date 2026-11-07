# MANIC UI/UX review, round 18 (re-rating at 7434f240), reviewer: opus

## Evidence

**Screenshots.** I viewed all 558 PNGs in the nine round-18 folders as 4×4 contact sheets (`sheets/`, 640 px tiles), and pixel-diffed every shot against round 17 (`imgdiff.py`):
- The four Linux folders at 2560, 1500 and 1024 are pixel-identical to round 17. The 150% folder differs in one shot, `24_unlabelled_grid`, and only in a 205×31 strip at the toast.
- The CI folders differ in 8 or 9 unlabelled shots each, inside the grid area. As in round 17, CI regenerates the synthetic data, so peak heights change. The chrome, layout and copy are the same.

Short names below: `2560L/`, `2560D/` (Linux 2560×1410, light and dark, the primary target); `WL/`, `WD/` (Windows CI); `ML/`, `MD/` (macOS CI); `1500L/`; `1024D/`; `150D/` (150%, 1280×800 window, dark).

**Code.** `git diff e33c52c9..7434f240 -- src` touches six UI files:
- `SummaryRows` becomes `BarRows` (`chart_style.py:207-266`). It owns the tip for the three Summary charts and for the popups. It reads the place under the pointer on every move, on a rest request, and on leave or hide.
- Identity cells are now found from the pointer's value-space position (`identity_chart.py:192-197`), not from `QBarSet.hovered`.
- Tips are held while the pointer rests (`_TIP_HOLD_MS = 86_400_000`, `chart_style.py:204, 249`).

The tests that changed this round pass: 192 passed and 4 skipped across `test_identity_chart`, `test_chart_popups`, `test_main_window_shell`, `test_ui_formatting`, `test_plot_grid_ui` and `test_compound_list_context_menu`. A first run, made while two offscreen probes shared the CPU, failed once on `test_compound_with_no_expected_ratios_says_so_instead_of_a_grey_grid[no-tolerances]`. That test passed alone, passed with its file, and passed in a clean rerun of the whole set, so I count it as flaky under load, not as a defect. `git status` is clean in both review worktrees.

**My own drive.** I ran `drive18.py` → `body18.py` offscreen with `screen2560.json` (log in `extra/log.txt`). It reached DONE with no traceback. With timings stripped, its 159-line log is **identical line for line to round 17's**. That covers:
- Labelled: the fresh load and its status; the A, N and B refusals ("No flagged plots in Pyruvate"); a Peak window draft and apply; the tR window apply ("Regenerated 30 EICs", 2.0 s); a Peak validation save; all seven Settings pages; the deconvolution indicator; both popups; the detailed view.
- Exports: labelled and unlabelled, each ending with the toast "Exported export.xlsx".
- Resizing 2560 → 1024 → 2560; the Scale menu; every menu bar menu read live.
- Unlabelled: all 8 compounds, the Glycine Summary, narrow names, the Identity popup, the detailed view, a fit override, and the round-14 probes including Open Recent.

**Round-18 probes** (`probe18c.py`, `probe18d.py`, `probe18e_*.py`, `hover_long.py`; logs in their folders). All of them move a real pointer with `QTest.mouseMove` on the window, so Qt itself sends the rest event.
- **Summary Identity, at 2560 and 1500.** On Sample_04_ratio_fail, Sample_05_rt_shift and MM_01, I tried every transition: q1 → rest → q2 → rest → name → rest → q1 → another row's q2 → rest. Each shows the right tip at once and keeps it at rest. Leaving into the grid hides the tip within Qt's 300 ms delay. A 12 s rest keeps the tip. Clicking a cell selects that sample's plot.
- **Summary Peak area and Ratio charts.** Bar, rest and name are right on the top, middle and bottom rows.
- **Identity popup.** Cell and rest are right. Name to cell is right. Leave and Esc hide the tip. Clicking a cell selects its plot and closes the popup.
- **Peak area popup and Ratio popup.** No stray tip. A click selects the plot and closes the popup.
- **A shortened popup name.** The repo test lost its hover assertion this round, so I checked it live: hovering the 92-character name in a popup still shows the full name, and it stays at rest.
- **Stale-tip probe.** Details in issue 1.

**Not run:**
- Real OS hover timing.
- The native macOS menu bar.
- Windows at 125% and 150%.
- A real OS scheme switch.
- Delete and Recover, session import, and the quit prompt. Their code has not changed since round 13.

## Verdict

The round's goal is met. One owner now serves every Summary chart and popup tip, and each hover transition I walked shows the right text at once, keeps it at rest and clears it on leave. That holds at 2560 and 1500, in both modes. The screens are pixel-identical to round 17, the end-to-end drive is identical, and nothing on `main` is missing.

The new hold time has one side effect, and it is a stale-state defect. In labelled mode, rest the pointer on a Summary Peak area bar, then press ↓ in the compound list. The tip keeps the previous compound's value, with no time limit, until the pointer moves. In one case it read "Peak area 6.23e+03" while the bar now stood for 136. Round 17 showed the same stale text, but Qt's default timeout removed it after about 10 s. I missed it last round. Now nothing removes it. Under the functional-first rule, that costs F5 a point.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 10 | Pixel-identical to round 17 at 2560: one type scale, quiet hairlines, and colour only for traces and verdicts (`2560L/24_unlabelled_grid.png`, `2560D/05_labelled_grid.png`). The Windows and macOS CI shots render the same tokens in both schemes (`WD/33`, `MD/27`). |
| F2 | Layout and hierarchy | 10 | At 2560: 30 labelled tiles and 11 unlabelled tiles, with no scroll (`2560L/05`, `2560L/24`). Resizing to 1024 and back lays out like a fresh launch, and the Summary yields at 1100 (drive log, `lab_resize`). |
| F3 | Onboarding and workflow clarity | 10 | One action per empty state (`*/02`, `*/03`, `*/36`). The checklist has a pattern how-to (`*/04_*_steps`). Quick Start has a key table (`*/17_…DocumentationViewer.png`). Refusals explain themselves ("No flagged plots in Pyruvate", log line 10). |
| F4 | Consistency and polish | 10 | The Summary and the popup now behave the same on every hover transition, because one class serves both (`chart_style.py:207-266`; probe18c, 2560 and 1500). |
| F5 | Feedback and state | 9 | Live feedback is all verified: "Regenerated 30 EICs", "Saved", "Exported export.xlsx", the refusals, and the draft caption. But in labelled mode a Summary tip keeps the previous compound's value, with no time limit, after a keyboard compound change (`chart_style.py:204, 249`; probe18d and probe18e). |
| F6 | Efficiency and flexibility | 10 | Every shortcut and menu is intact (menus read live). In the popups, ↑↓, Return and click choose a row (`chart_popup_dialog.py:741-770`). A tip no longer expires while you read it. |
| F7 | Data visualisation | 10 | Cell tips give the qualifier, the state, then "expected … ±25% observed …". Name tips summarise each qualifier's state (probe18c). The qualifier key lists only the states present (`*/24`), and the detailed view tags qualifier states in its legend (`*/34`). |
| F8 | Modern feel | 10 | It feels like current, considered software on the 27" screen and on both CI platforms. Panels yield and return, the theme switches live (`*/08_*`), and hover answers at once on every surface. |
| F9 | Taste (not AI slop) | 10 | The copy is unchanged and short: "Re-extracts all 11 shown samples", "Qualifier cells ✓ 16 ✕ 2 ? 4", "Hover a cell for details · ↑↓ to choose · Return or click to select its plot" (`*/33`). I found no template layouts, decorative chips or ornamental icons. |

Overall: (10×8 + 9)/9 = **9.9** (round 17: 10.0).

### F9 tells and duplications, named

These are unchanged from round 17. Judged strictly, I found none that lacks a reason.

| Tell | Where | Justified? |
|---|---|---|
| Sidebar and Summary toggles in the header, the View menu, and Ctrl+Alt+S/R | `*/05` | Yes: a menu command, a shortcut, and a button beside its panel. |
| Shared Y / Scale to peak in the header (or the folded Scale button) and the View menu | `*/05` | Yes: a menu command plus a control at the grid. |
| The qualifier QC key in the grid header, with a tally in the Identity footer | `2560L/24`, `*/33` | Yes: the key names the colours, and the footer only counts marks. |
| The Identity popup key, with swatches and labels | `*/33_identity_popup` | Yes: the popup is a separate window, away from the grid header's key. |
| The popup footer hint, "Hover a cell for details · ↑↓ to choose · Return or click…" | `*/33`, `*/13`, `*/14` | Yes: it is the only place these popup keys are taught. |
| The internal standard in the sidebar, the checklist and Settings | `*/04_*`, `*/16_settings_page4` | Yes: each is a place to act on it. |
| The deconvolution indicator in the status bar and in Settings | drive log, `lab_settings` | Yes: it appears only when the settings differ from the defaults. |
| The qualifier gap note in the grid header or in the Identity panel | `*/26` | Yes: it has one home at a time. |

## Top issues, ranked by user impact

**1. A Summary tip keeps a previous compound's value until the pointer moves (stale state; F5 −1).**

*What is wrong.* Take a labelled session. Rest the pointer on a Summary Peak area bar, focus the compound list, and press ↓. The chart redraws for the new compound, but the tip keeps the old text. Measured on Bio_001 (`probe18d/log.txt`, `probe18e/log.txt`):

| Compound change | Tip after the key press | Row's text now |
|---|---|---|
| Lactate → Alanine | Peak area 1.19e+04 | Peak area 8.66e+03 |
| Valine 218 → Urea | Peak area 6.23e+03 | Peak area 136 |

The Valine 218 → Urea tip is still up after 14.6 s, and a 1 px move corrects it.

*Cause.* Round 17 does the same at 1.6 s (`probe18d_on17`), but its tip was gone by 14.6 s (`probe18e_on17`), because Qt's default timeout removed it. Round 18 holds every tip for 24 h (`chart_style.py:204, 249`). The tip is recomputed only on pointer events (`chart_style.py:252-265`), and nothing recomputes it when the chart's data changes. On Windows and Linux, Qt does not hide a tip on a key press; only macOS does that in `QTipLabel`, from my reading of the Qt source, not verified on macOS here.

I verified only the compound-list key. Any other change of data under a resting pointer should behave the same way: Peak window Apply from the keyboard, or a regeneration finishing. Two cases did hide: unlabelled, and a programmatic compound change.

*Fix.* Keep each `BarRows` instance. Three widgets currently discard it: `targeted_qc_widget.py:82`, `total_abundance_widget.py:86` and `isotopologue_ratio_widget.py:85`. Call `self._rows.refresh()` at the end of `update_abundance_from_data` (`total_abundance_widget.py:126`), `update_ratios` (`isotopologue_ratio_widget.py:141`), and `update_results` and `clear` (`targeted_qc_widget.py:138, 183`). With no argument, `refresh()` recomputes the tip at the resting pointer: it shows the new value, or hides the tip when the row is gone. Add one row to the transition matrix: rest, update the data, then assert that the tip equals the new `hover_text`.

*Expected gain.* F5 +1.

Below the cut, none affecting a score:

2. **Moving from a popup cell onto a row name keeps the cell's tip for up to 300 ms.** It is shown at 150 ms and gone at 400 ms (probe18c). This is Qt's hide delay, and the end state is right. No fix needed.
3. **The sidebar standard keeps only "Lactate_…026_long" of a 56-character name.** Unchanged; the full name is on hover.
4. **The internal-standard row's tooltip is long.** Unchanged. It explains a consequence and its fix, which is what a tooltip is for.

## Re-rating comparison

**My round-17 issues, status:** round 17 listed no issue above the cut. Its three items below the cut:
1. The 300 ms hide delay from a popup cell onto a name: unchanged, by design (item 2).
2. Sidebar standard truncation: unchanged.
3. Long internal-standard tooltip: unchanged.

**The round's target (one tooltip owner for the Summary and popup charts): fixed.**
- Every transition I walked on the Summary Identity chart, the popup and the bar charts shows the right tip at once, keeps it at rest, and clears it on leave, Esc or close.
- The cell is found from the pointer, so a cell answers the same whether the pointer arrives from a name, another cell or another row.
- The repo transition matrix passes.

**Improved:**
- The Summary tip no longer expires after about 10 s while you read it.
- Two parallel hover paths (`QBarSet.hovered` plus a row filter) are now one, 42 lines fewer across the UI source (107 insertions, 149 deletions).

**Regressed:**
- The stale Summary tip in issue 1 used to last up to about 10 s; now it lasts until the pointer moves. It is not new state, but the bound on it was lost.
- Nothing else. The screens are pixel-identical, the drive log is identical, and the full name still shows on hover over a shortened popup row.

**Lost functionality: none against `origin/main`.** The UI diff against main is 8946 insertions and 3974 deletions. It adds no action and removes none. The menus read live match round 17:
- File: 12 actions.
- View: 8 actions.
- Review: 11 actions, including Curve Fit with five choices.
- Help: 4 actions.

Both exports completed. Popup click and Return still select a plot (probe18c).

**What stands between each factor and a 10:**
- F5: issue 1.
- The other eight factors: nothing I could find.

**Per-platform limits:**
- **2560:** offscreen renders plus my drive and probes at that geometry. Not checked: the native title bar and the macOS menu bar.
- **Windows:** the CI shots are clean in both schemes. Issue 1 applies to Windows, because Qt keeps a tip through key presses there. Not verified: 125% and 150% scaling.
- **macOS:** the CI shots are clean in both schemes, with the native button order (`ML/18`, `MD/16_*`). Not checked: the native menu bar, an OS scheme switch, and whether a key press there clears the stale tip in issue 1.
- **150%:** dark only (`150D/*`), and clean.

```json
{"F1": 10, "F2": 10, "F3": 10, "F4": 10, "F5": 9, "F6": 10, "F7": 10, "F8": 10, "F9": 10, "overall": 9.9}
```
