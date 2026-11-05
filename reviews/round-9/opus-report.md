# MANIC UI/UX review, round 9 (re-rating at c574eca), reviewer: opus

## Evidence

**Screenshots.** I viewed all 440 PNGs in the eight round-9 folders, as 3×3 contact sheets (`sheets/`). I opened a shot full size wherever a detail mattered: the docs first page on each CI runner, and the Windows chooser. Short names used below:
- `WL/`, `WD/`: Windows light and dark (CI, 1024×720).
- `ML/`, `MD/`: CI macOS light and dark (1024×681).
- `mL/`, `mD/`: the local Mac (1512×949).
- `150L/`, `150D/`: the 150% folders (1008×633 logical).

**My own drives.** All ran on this Mac against `pMANIC-review-r9` at c574eca, with real windows. The scripts are in this folder; output is in `run.out`, `run2.out` and `run3.out`.
- `drive9.py` (writes `extra/`). Labelled data:
  - fresh load: read the sidebar, header, status bar and checklist;
  - clicked a compound in the list, then pressed N, A, B and P;
  - opened the sidebar chooser, typed "pal" and Return, then "scyl" and arrows;
  - drafted a tR window and a Left offset, switched compound and back, Reset (cancelled), and Return to apply;
  - opened Settings › Choose…;
  - read every menu-bar menu;
  - opened the detailed view;
  - exported: the Palatinose prompt (cancelled), then a full export with scyllo-Ins;
  - Documentation: Ctrl+F, "baseline", Return, Esc;
  - opened the Clear Session prompt.

  Unlabelled data: went through all 8 compounds and their badges, ran N from the list, then B, then N. Finally resized the window to 1008×633.
- `probe2.py` (writes `extra2/`): the same review keys, but each key press first confirms that MANIC is the active window. It chose scyllo-Ins through the chooser by keyboard. Then:
  - N, N, Shift+N, then A;
  - three tiles selected, then N and B;
  - N with everything reviewed;
  - Return, then the detailed view with Full scan at 921×581 and 1400×900;
  - the unlabelled N cycle with a wrap.
- `probe3.py`: the chooser with a filter that matches nothing.
- **Label diff.** Quoted UI strings at a696f0b against c574eca (`labels_*.txt`).
  - Removed: "Clear Acceptance (2 Peaks)" was a docstring example. "Hover a bar for its value" was replaced by the new hover copy. "Not applied" now has one form. Two dialog titles were reworded.
  - Added: Find (Done, Next/Previous match, No matches), "Peak area, sum of isotopologues" and "Q-ion peak area".

**Harness noise, not app bugs:**
- Other agents' tours shared this machine. In `drive9.py` the first N press reached MANIC while it was not the active window, and the compound moved (Lactate → Histidine). In `probe2.py` every press checked activation first, and N, A and B from the list never changed compound.
- The chooser is a `Qt::Popup`. It closed by itself in two `probe3.py` runs, when another window took activation. I confirmed in code that Return on a filter with no match does nothing (`standard_chooser.py:146-163`).
- The "QMenu already deleted" error in `_sync_review_menu` is the same artefact as round 8: my menu dump calls `QAction.menu()`. So is the `self.ax is None` error in `_place_full_scan_button`: my hook closed the detailed dialog before its first paint.

**Not run:**
- real hover and tooltips;
- the native macOS menu bar;
- Windows at 125% and 150%, and the native dark title bar;
- a real OS scheme switch;
- Delete Sample and Recover;
- the session import itself;
- an EIC regeneration.

## Verdict

The round-8 keyboard traps are fixed, and I verified each one live (`probe2.py`):
- N, A and B go to the review commands even when the compound list has focus. Other letters still type ahead in the list, as they should.
- N selects only the tile it lands on. The menus then name it ("Accept Bio_004 (Below Threshold)", "Mark Bio_004 as Bad"), and A acts on that tile alone.
- In unlabelled data, N runs 04 → 05 → 07 and then wraps.
- With nothing left to review, Next/Previous Flagged are disabled, and N shows a "No plots need review in Pyruvate" toast.

The new internal standard chooser works:
- It filters as you type and puts the compounds with an amount first, under a "No amount: exports peak areas" heading.
- It opens from both the sidebar and Settings, and on Windows CI it stays open (`WL/30`, `WD/30`).

Several other round-8 issues are fixed: the export prompt reads in plain words, Apply window turns primary for its own draft, "· not applied" has one form, and labelled Full scan keeps the coloured M+0…M+3 cluster. Compact tile labels are spaced (`*/22`), the compound list keeps 3–4 rows at 1008×633, and docs Find works ("1 of 1", Esc closes it).

The full export ran in 22 s, wrote 5 sheets and showed the "Exported export.xlsx" toast. Nothing was lost.

What stands between this and a 10:
- **The checklist's standard picker.** The first place a user picks a standard, the checklist, is still a 96-item plain combo. The new chooser exists only in the sidebar and Settings.
- **Unflagged peaks.** In labelled data, peaks that sit wholly outside the dashed window still carry no flag. N then reports "No plots need review" for a compound with four such tiles.
- **Blank docs page.** The first docs page is blank again on CI macOS, light this time.
- **Copy and layout polish.**

Every factor holds at 9 on the weakest platform. F6 is back to 9.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 9 | One token system holds in all eight folders (`WD/24`, `MD/26`, `150D/29`, `mD/32`). The chooser replaces the three-column wall with a calm 10-row list (`extra/02_chooser__chooser_open.png`). Held back by small things: the tR window caption wraps to two lines in the sidebar (`extra/04_drafts__both_drafts.png`); the chooser keeps 10 rows of empty space after filtering (`extra/02_chooser__chooser_pal.png`, `standard_chooser.py:94-97`); and the docs key column wraps "Ctrl+A (⌘A on / macOS)" (`ML/17`). |
| F2 | Layout and hierarchy | 9 | Short windows keep compounds first: "3 of 8" shows all three matches at 150% (`150L/29`), and 4 rows show at 1008×633 (`extra/12_short__short.png`; `left_toolbar.py:51-55`). Add Compound scrolls by whole rows (`ML/28`, `150L/28`). Gaps: two primary buttons sit at once when both drafts exist (`extra/04_drafts__both_drafts.png`). The detailed view scrolled at 921×581 in one local run when its legend wrapped (`extra2/00___det921.png`), though CI at the same size fits (`ML/11`). |
| F3 | Onboarding and workflow clarity | 9 | The empty states, the checklist and the Quick Start keyboard table are clear (`*/02`, `*/04_*`, `mL/17`). The export prompt is plain: "Palatinose has no internal-standard amount in the compound list. Export peak areas instead?" (`extra/08_export__QMessageBox.png`). Gap: Quick Start says "Click a plot first so the grid has keyboard focus. A, B and N work anywhere in the window except a text field" (`docs/00_quick_start.md:12`). The first sentence contradicts the second for the keys a new user needs most. |
| F4 | Consistency and polish | 9 | One "· not applied" form, and the primary rule now covers Apply window too (`integration_window_widget.py:766-799`, `run.out` `('applywin', True, 'primary')`). Prompts use verbs with Cancel as the default. Settings orders its buttons per platform (`WL/27` Save/Revert, `ML/27` Revert/Save). Gap: three places pick the internal standard, with two different components. The sidebar and Settings use the filterable chooser; the checklist (`post_load_checklist_dialog.py:126-130`) and Process External Data (`update_old_data_dialog.py:126-128`) use a plain combo in file order. |
| F5 | Feedback and state | 9 | Verified live: the N toast, Next Flagged disabled when nothing is flagged, menus naming the target tile, the no-amount note, the export toast, and the draft captions. Gaps: labelled tiles whose peak lies wholly outside the window carry no badge (`mL/05`, `extra2/00___N_focus.png`: Bio_014/018/019/020 in Pyruvate). The toast then says "No plots need review", which overstates the check (`main_window.py:634`). The first docs page is blank on CI macOS light (`ML/17_documentation__DocumentationViewer.png`). |
| F6 | Efficiency and flexibility | 9 | Fixed: the review keys are window-wide, a text field types them (`main_window.py:536-541`), N selects only its tile (`graphs.py:860-872`), the standard can be picked by filter and Return, docs have Find, and compact/comfortable density is kept. Gap: the checklist's 96-item combo has no filter, and it lists compounds in file order with the no-amount ones mixed in. N has no "next compound with a flag" step. |
| F7 | Data visualisation | 9 | Labelled Full scan keeps the M+0…M+3 label and colours (`extra2/00___det1400_full.png`). The abundance popup names its quantity: "Peak area, sum of isotopologues (×10⁶)" (`mL/13`). Compact time labels are spaced (`*/22`). Remaining: a peak outside the dashed window looks the same as a clean tile (`extra2/00___N_focus.png`). The team declined to flag it until there is a science definition. |
| F8 | Modern feel | 9 | One-key review that now behaves; a searchable popup chooser; Find in docs; toasts with actions; drafts kept per compound; a live scheme switch. The blank first docs paint on CI macOS is the one thing that still reads as unfinished. |
| F9 | Taste (not AI slop) | 9 | The round-8 tells are gone: the field name in the export prompt, two spellings of "not applied", the 95-item menu. Left, all small: the docs key table doubles every key for both platforms ("Ctrl+Shift+B (⌘⇧B on macOS)", `extra/09_docs_find__docs_find.png`); the popup footer gives two instructions with ↑↓ twice ("Hover or ↑↓ to read a sample's percentages · Click a sample, or ↑↓ and Return, to show its plot", `chart_popup_dialog.py:404`, `:693`); and the no-IS export copy quotes 'Peak Area' (`main_window.py:2852-2853`). |

Overall: (9+9+9+9+9+9+9+9+9)/9 = **9.0** (round 8: 8.9).

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| Each shortcut is written for both platforms in one cell, "Ctrl+[ and Ctrl+] (⌘[ and ⌘] on macOS)" | `extra/09_docs_find__docs_find.png`, `mL/17` | No. The viewer knows the platform, so show one form. |
| The popup footer repeats ↑↓ in two clauses | `14_label_popup`, `chart_popup_dialog.py:404`, `:693` | No. "↑↓ to read · Return to open" says the same. |
| The internal standard is picked in the sidebar, the checklist and Settings › Choose… | `WL/05`, `WL/04_*`, `WL/16` | Yes as places (status, setup step, the context for Reference peak). No as two different widgets. |
| "No amount: exports peak areas" appears in the sidebar note, as the chooser heading, and in the export prompt | `extra/02_chooser__palatinose.png`, `extra/02_chooser__chooser_pal.png`, `extra/08_*` | Yes. Persistent status, a label at the moment of choice, and a confirmation at the action. |
| "Not assessed" appears in the grid header note, the identity chip and the detailed legend | `WL/26`, `WL/31`, `WD/32` | Yes. Three separate surfaces, each opened on its own. |
| Next/Previous Flagged appear in the Review menu and on N / Shift+N | `WL/10_review_menu__menu` | Yes. A menu command with its shortcut. |
| Deconvolution appears in the status bar and in Settings | `WL/05`, `WL/27` | Yes. Status that opens the editor. |

## Top 12 issues, ranked by user impact

1. **The checklist still picks the standard from a plain 96-item combo.**
   - Where: `post_load_checklist_dialog.py:126-130` (`run.out`: `('No internal standard', 96, False)`), shown in `WL/04_*`, `mL/04_*` and `150L/04_*`. This is the first place a new user sets the standard, and the list has no filter. It mixes no-amount compounds in file order, so picking one leads straight into the "Export peak areas instead?" prompt.
   - Fix: replace the combo with a button showing the current choice that opens `StandardChooser`, as Settings › Choose… does. Do the same in Process External Data (`update_old_data_dialog.py:126`), or at least order its combo the same way.
   - Gain: F4 +0.2, F6 +0.2, F3 +0.1.

2. **Labelled peaks wholly outside the integration window carry no flag, so N skips them.**
   - Where: Pyruvate Bio_014, 018, 019 and 020 have their apex right of the right dashed line with no badge, with or without scyllo-Ins (`mL/05`, `extra2/00___N_focus.png`). Pantothenate shows the same (`extra/02_chooser__palatinose.png`).
   - Status: declined pending a science-side definition, but this is still the largest review gap a user meets.
   - Fix: settle the definition in the PR follow-up. Until then, see issue 3.
   - Gain: F5 +0.25, F7 +0.15.

3. **The N toast claims more than the check does.**
   - Where: "No plots need review in Pyruvate" (`main_window.py:634`) appears while the four tiles above visibly need a look.
   - Fix: "No flagged plots in Pyruvate". It is accurate, and just as short.
   - Gain: F5 +0.05, F9 +0.05.

4. **The first Documentation page is blank on CI macOS.**
   - Where: `ML/17_documentation__DocumentationViewer.png` shows the nav only. `MD/17` rendered this round; last round it was the other way round. The new "Loading…" status page (`documentation_viewer.py:224-240`) doesn't show in the blank shot either, so the view switches to the web view before it paints.
   - Fix: stay on the status page until `loadFinished` and a `runJavaScript("requestAnimationFrame(...)")` callback have both fired, then switch.
   - Gain: F5 +0.1, F8 +0.1.

5. **The Quick Start keyboard line contradicts itself.**
   - Where: `docs/00_quick_start.md:12`, "Click a plot first so the grid has keyboard focus. A, B and N work anywhere in the window except a text field."
   - Fix: "Arrow keys, Space and Return act on the grid: click a plot first. N, A and B work anywhere except in a text field."
   - Gain: F3 +0.1, F9 +0.05.

6. **The docs key table doubles every key and wraps.**
   - Where: "Ctrl+A (⌘A on / macOS)" breaks across lines in the narrow Key column (`ML/17`, `mL/17`, `extra/09_docs_find__docs_find.png`).
   - Fix: substitute the platform's keys when the page renders (the viewer already uses `QKeySequence.NativeText` for its own tooltips), and widen the Key column.
   - Gain: F9 +0.1, F1 +0.05.

7. **The tR window caption wraps in the sidebar.**
   - Where: "Re-extracts all 30 shown / samples · not applied" runs over two lines in amber, while the Peak window caption fits on one (`extra/04_drafts__both_drafts.png`; `integration_window_widget.py:790-794`).
   - Fix: shorten it to "All 30 samples · not applied", or elide the scope and keep "· not applied".
   - Gain: F1 +0.05, F2 +0.05.

8. **Two primary buttons appear at once.**
   - Where: with both drafts open, Apply and Apply window are both filled blue (`extra/04_drafts__both_drafts.png`), so nothing says which comes first.
   - Fix: keep both enabled, but make only the most recently edited one primary. Or let Return in either field apply both.
   - Gain: F2 +0.05, F4 +0.05.

9. **The chooser stays 10 rows tall after filtering.**
   - Where: "pal" leaves three rows above about 180 px of empty panel (`extra/02_chooser__chooser_pal.png`; fixed size at `standard_chooser.py:94-97`).
   - Fix: resize the list to the visible rows, up to `VISIBLE_ROWS`, on `filtered`.
   - Gain: F1 +0.05.

10. **The chart popup footer is wordy.**
    - Where: "Hover or ↑↓ to read a sample's percentages · Click a sample, or ↑↓ and Return, to show its plot" (`*/14`; `chart_popup_dialog.py:404`, `:693`).
    - Fix: "↑↓ to read · Return or click to open its plot".
    - Gain: F9 +0.05.

11. **The no-IS export copy quotes a column name.**
    - Where: "Abundance values will represent 'Peak Area' (sum of corrected isotopologues)." (`main_window.py:2852-2853`).
    - Fix: "Abundances will be peak areas (sum of corrected isotopologues)." That matches the plain wording the no-amount prompt now uses.
    - Gain: F9 +0.05.

12. **The detailed view can scroll at small sizes when its legend wraps.**
    - Where: in my local run at 921×581, "Baseline" wrapped to a second legend line, and the TIC and spectrum x axes went out of view (`extra2/00___det921.png`). CI macOS fits at the same size (`ML/11`), so the trigger is font metrics.
    - Fix: let the EIC legend use two columns, or shrink its font one step before the dialog gives up height.
    - Gain: F2 +0.05, F7 +0.05.

## Re-rating comparison

**My round-8 issues, status:**
1. **Review keys go to the compound list: fixed.**
   - N, A and B from the list leave the compound alone, with the window confirmed active (`probe2.py`).
   - P still types ahead, as it should.
   - A letter in the tR window field is not taken as a review key.
2. **N then B acts on the old selection: fixed.** N calls `select_only_plot` (`graphs.py:871`). The menus then read "Mark Bio_004 as Bad", and A accepted only Bio_004.
3. **N silent when nothing is flagged: fixed.** Next/Previous Flagged are disabled (`run.out` MENUBAR Review), and N shows a toast. The toast copy overstates the check (issue 3).
4. **Labelled peaks outside the window unflagged: still open.** Declined pending a definition (issue 2).
5. **Blank first docs page on macOS: still open** (`ML/17`).
6. **Compound list one row at 150%: fixed** (`150L/29`, `150L/33`, `extra/12_short__short.png`: 4 rows).
7. **Export prompt names a database field: fixed** (`extra/08_export__QMessageBox.png`).
8. **No search in the standard picker: fixed in the sidebar and Settings.** It is partly fixed overall, because the checklist still uses a combo (issue 1).
9. **Apply window not primary for its draft: fixed** (`run.out` `('applywin', True, 'primary')`).
10. **Add Compound cuts a heading at 150%: fixed.** It scrolls by whole rows (`150L/18`, `150L/28`, `ML/28`).
11. **Labelled Full scan collapses the cluster: fixed** (`extra2/00___det1400_full.png`, `extra2/00___det921_full.png`).
12. **Two spellings of "not applied": fixed.** Both captions use "· not applied" (`run.out` drafts lines).

**Improved beyond the list:**
- Find in Documentation, with a count, Return to step, and Esc to close;
- section headings that report open or closed to screen readers, and accessible names on the Peak window fields (`integration_window_widget.py:312`, `:348`);
- the label popup key reads the current row;
- the abundance popup axis names its quantity.

**Regressed:** nothing I can tie to this round.

**Lost functionality: none.**
- The label diff shows no command removed. The six removed strings are a docstring, a rewritten hint, the merged "Not applied" form, and reworded dialog titles.
- Live checks found every menu present and enabled where it applies:
  - File: Load, Add Compound, Load Raw Data, Open Recent, Export and Import Session, New Analysis Session, Clear Session, Export Data, Process External Data, Settings, Quit;
  - View: Compact, Comfortable, Shared Y-Scale, Scale to Selected Peak, Find Compound, Previous and Next Compound, Sample List;
  - Review: Inspect, Select All, Deselect All, Show Only Selected, Show All, Next and Previous Flagged, Accept, Mark Bad, Curve Fit, Baseline Correction;
  - Help: Documentation, Check Data Setup, Check for Updates, About.
- The context menu matches (`*/09_plot_context_menu__menu`). Round 8 traced main's labels to b804ecf and a696f0b.

**Per-platform limits:**
- **Windows:**
  - judged from CI at 100% (1024×720), clean in both schemes;
  - the chooser opens and stays open (`WL/30`, `WD/30`);
  - not verified: 125% and 150%, the native dark title bar, hover.
- **macOS:**
  - the native menu bar wasn't verified;
  - the scheme was forced, not switched by the OS;
  - the key drives confirmed window activation before each key, because other tours shared the machine.
- **150%:** the harsh 1008×633 stand-in only.

```json
{"F1": 9, "F2": 9, "F3": 9, "F4": 9, "F5": 9, "F6": 9, "F7": 9, "F8": 9, "F9": 9, "overall": 9.0}
```
