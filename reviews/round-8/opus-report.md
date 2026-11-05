# MANIC UI/UX review, round 8 (re-rating at a696f0b), reviewer: opus

## Evidence

**Screenshots.** I viewed all 440 PNGs in the eight round-8 folders as 3×3 contact sheets (`sheets/`). I opened full size or cropped wherever a detail mattered, such as the local Mac Pyruvate grid and the 150% sidebar. Short names used below:
- `WL/`, `WD/`: Windows light and dark (CI, 1024×720).
- `ML/`, `MD/`: CI macOS light and dark (1024×681).
- `mL/`, `mD/`: the local Mac (1512×949).
- `150L/`, `150D/`: the 150% folders (1008×633 logical).

**My own drives.** These ran on this Mac against `pMANIC-review-r8` at a696f0b, with real windows. The scripts are in this folder; stdout is in `run.out`, `run2.out` and the transcript below.
- `drive.py` (writes `extra/`). Labelled data:
  - fresh load: read the sidebar, header and status bar;
  - pressed N with nothing flagged;
  - chose Palatinose (no amount), then scyllo-Ins (has amounts);
  - pressed N and Shift+N, then N then A;
  - selected Bio_001–003, pressed N, then B;
  - made a tR window draft, switched compound and back, edited Left offset, and clicked Reset;
  - opened Settings › Choose…;
  - read every menu bar menu;
  - opened the detailed view;
  - exported with Palatinose (prompt only, cancelled), then with scyllo-Ins (full export);
  - opened the Clear Session prompt.

  Unlabelled data: went through all 8 compounds and read each tile's badges and tooltips, then cycled N.
- `check2.py` (writes `extra2/`): the detailed view at the CI macOS size of 921×581, Full scan on and off, Reset all, and the main window at 1008×633.
- `check4.py` (writes `extra4/`): clicked a compound in the sidebar list, then pressed N, N and A, in both modes.
- **Label diff.** UI labels at b804ecf against a696f0b (`labels_*.txt`). Nothing was removed. Four were added: "Choose…", "Full scan", "Next Flagged Sample" and "Previous Flagged Sample".

**Two tracebacks I ruled out as harness artefacts:**
- A "QMenu already deleted" error in `_sync_review_menu`. My script calls `QAction.menu()`, and that PySide wrapper call deletes the Curve Fit submenu. The app never calls `.menu()`.
- A `self.ax is None` error in `_place_full_scan_button`. It happened only when my hook closed the detailed dialog before its first paint. It didn't happen when I opened and closed the dialog normally (`check2.py`).

**Not run:**
- real hover and tooltips;
- the native macOS menu bar;
- Windows at 125% and 150%;
- a real OS scheme switch;
- Delete Sample and Recover;
- the session import itself;
- an EIC regeneration;
- the new "tR off" badge. Neither dataset triggers it: the shifted unlabelled sample reads "Not detected", and labelled mode never builds identity QC. I read the code only (`plot_tile.py:86-88`).

## Verdict

Every round-7 item I could check is fixed except the blank first docs page on CI macOS:
- Short spectra keep both ion labels ("174.00 / 247.98" in `MD/32`; both labels in `WL/32` at 870×612).
- A standard without an amount says "No amount: exports peak areas" on its sidebar row (`extra/02`).
- The Identity popup lost its phantom chip (`WL/31`).
- The docs read as prose.
- The prompts name their verbs, with Cancel as the default.
- Apply turns primary only when there is a draft.
- The N key exists.

The core paths work:
- fresh load, with the "Imported 2850 EICs" toast;
- verdicts;
- drafts that survive a compound switch ("not applied" is kept);
- Settings, and its Choose… menu;
- Reset (Cancel is the default);
- export: 5 sheets in 18.2 s, then a "Show in Folder" toast;
- Clear Session.

Nothing was lost.

This round's hands-on test of the review keys found three functional traps, and they matter more than any pixel:
1. **Review keys go to the compound list.** Clicking a compound leaves focus in the sidebar list, which has type-ahead. N then jumps to "nor-Leucine" and A jumps to "Alanine" or "Aspartate" (`check4.py`). This was already true of A and B in round 7. I missed it because I forced focus onto the grid.
2. **B can mark the wrong samples.** With samples selected, N moves the focus ring to the flagged tile, but B then marks the selection (`extra/04_n_cycle__N_with_selection_then_B.png`).
3. **N can do nothing at all.** In labelled mode with no internal standard, N does nothing and gives no feedback. Peaks that elute entirely outside the integration window (Pyruvate Bio_014, Bio_019) carry no badge, so N skips them.

The visual layer is at a 9 across all eight folders. The keyboard review loop is not yet trustworthy, so F6 drops to 8.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 9 | One token system holds in all eight folders (`WD/24`, `MD/26`, `150D/29`), and the docs now read as prose (`WL/17_…page1`, `…page2`). Held back by: the 95-item, three-column internal-standard menu, a wall of text (`extra/06_settings_choose__choose_menu.png`, `left_toolbar.py:733`); and labelled Full scan, where the isotopologue cluster becomes one black bar with no labels (`extra2/00___det921_full.png`). |
| F2 | Layout and hierarchy | 9 | Short windows open Baseline and tR window as a popover row, "Baseline, tR window · On · 0.22 min" (`ML/29`, `150L/29`). The detailed view fits at 921×581 (`extra2/00___det921.png`). At 150%, with Samples open, the compound list shrinks to one visible row (`150L/29`: only "Alanine" of 3 matches; `150L/33`: only "Glycine"; `left_toolbar.py:193`). Add Compound still cuts "Standards" in half at the scroll edge (`150L/18`, `150D/18`). |
| F3 | Onboarding and workflow clarity | 9 | Quick Start lists N and Shift+N. The checklist and the sidebar say when a standard has no amount. The grid note explains Glycine's unassessed qualifier (`WL/26`). Gaps: nothing tells a new user that the review keys act only after the grid has focus (issue 1). In labelled mode, "flagged" means only Below threshold and Marked bad, so N has nothing to visit until a standard is chosen (`extra/01`). |
| F4 | Consistency and polish | 9 | Verb buttons with Cancel as the default on Reset ("Reset Peak Window"), Export ("Export Peak Areas") and Clear Session (`extra/05_*`, `09_*`, `10_*`). Settings orders its buttons per platform. Gaps: Apply turns primary for a draft, but Apply window stays secondary for its own draft (`extra/05_drafts__trwin_edited.png`; `integration_window_widget.py:770`). "Not applied" appears as a standalone line in one place and as a "· not applied" suffix in another (`integration_window_widget.py:42`, `:767`). |
| F5 | Feedback and state | 9 | Verified live: the no-amount note, Below threshold, Accepted and Marked bad pills, QC fail and Not detected with reason tooltips, drafts, the export toast with Show in Folder. Gaps: N fails silently when nothing is flagged. Labelled peaks outside the integration window get no badge (`mL/05`: Bio_014, Bio_019). The first docs page is blank again on CI macOS dark (`MD/17_documentation__DocumentationViewer.png`). |
| F6 | Efficiency and flexibility | 8 | New: N and Shift+N, View › Compact/Comfortable, Choose… in Settings, Full scan. But the review keys are scoped to the grid (`main_window.py:536-541`). After the natural "click a compound" step, N, A and B type-ahead in the compound list and switch compound silently (`check4.py`: Lactate → nor-Leucine → Aspartate). N with a selection leaves B acting on the selection (`graphs.py:964-971`). The 95-name standard menu has no type-to-filter. |
| F7 | Data visualisation | 9 | Short spectra keep their own-ion labels (`MD/32`, `ML/32`, `WL/32`). The labelled spectrum opens on the "M+0…M+3" cluster. The detailed key names Raw signal and Baseline. The tR-off badge exists in code. Remaining: labelled Full scan collapses the cluster to one unlabelled stroke (`extra2/00___det921_full.png`); and a tile whose peak sits wholly outside the dashed window looks the same as a clean tile (`mL/05` Bio_014). |
| F8 | Modern feel | 9 | Toasts with actions, drafts kept per compound, verb prompts, a live scheme switch, folded editors, one-key review. Real documentation prose. What still feels old is keyboard focus that silently goes elsewhere, and the blank first docs paint on macOS. |
| F9 | Taste (not AI slop) | 9 | The round-7 tells are gone: the phantom chip, Yes/No, "synchronized" (now "Deleted compounds and samples will match the file.", `main_window.py:2134`) and the `<br>` prose. Left: the export prompt shows a database field name, "Missing or zero 'int_std_amount'", under "is missing required metadata" (`main_window.py:2860-2866`, `data_exporter.py:95`; `extra/09_export__QMessageBox.png`); and the standard picker is a 95-entry menu where a searchable list would fit. |

Overall: (9+9+9+9+9+8+9+9+9)/9 = **8.9** (round 7: 9.0). The drop is a pre-existing keyboard trap that the new N key brought to the surface. Nothing regressed.

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| Code identifier in user copy: "Missing or zero 'int_std_amount'" plus "missing required metadata" | `extra/09_export__QMessageBox.png`; `main_window.py:2860-2866`, `data_exporter.py:95` | No. The sidebar note already says it plainly: "No amount: exports peak areas". |
| Two spellings of one state: "Not applied" (a line of its own) and "· not applied" (a suffix) | `extra/05_drafts__trwin_back.png`; `integration_window_widget.py:42`, `:767` | No. One state should have one form. |
| A 95-item, three-column flat menu for the internal standard | `extra/06_settings_choose__choose_menu.png`; `left_toolbar.py:733` | No. It reads as a dump, not a chooser. |
| Internal standard picker in the sidebar row, the checklist, and Settings › Choose… | `WL/05`, `WL/04_*`, `WL/16_*` | Yes. Status, a setup step, and the context for Reference peak. |
| No-amount state shown in the sidebar note and in the export prompt | `extra/02`, `extra/09_*` | Yes. Persistent status, plus a confirmation at the moment of the action. |
| Next/Previous Flagged in the Review menu and on N / Shift+N | `WL/10_review_menu__menu` | Yes. A menu command with its shortcut. |
| Deconvolution in the status bar and in Settings | `WL/05`, `WL/16_…page1` | Yes. Status that opens the editor. |
| "Qualifier QC:" key on the unlabelled header and the Summary legend | `WL/24` | Yes. One keys the tiles, the other keys the cells. |

## Top 12 issues, ranked by user impact

1. **Review keys type into the compound list and silently switch compound.**
   - Where: `main_window.py:536-541` gives N, Shift+N, A and B `Qt.WidgetWithChildrenShortcut` on the graph view. Clicking a compound puts focus in `CompoundListWidget`, whose type-ahead takes the letter.
   - Reproduced (`check4.py`, labelled data): click Lactate, press N, and the compound becomes "nor-Leucine"; press A, and it becomes "Aspartate". In unlabelled data, A goes to "Alanine". No verdict is set and nothing is said.
   - Fix (any one of these):
     - give these actions `Qt.WindowShortcut`, and have them ignore the event when the focus widget is a `QLineEdit` or `QAbstractSpinBox`;
     - turn off keyboard search on the compound and sample lists (`setKeyboardSearch` no-op, or override `keyboardSearch`);
     - move focus to the grid after a compound is picked with the mouse.
   - Gain: F6 +0.75, F5 +0.25, F8 +0.1.

2. **N then B (or A) can act on samples other than the one N jumped to.**
   - Where: with Bio_001–003 selected, N focuses the flagged Bio_004, but `review_lead` returns the first selected plot when the focused plot is not selected (`graphs.py:964-971`). B then marked Bio_001–003 as bad, and Bio_004 kept "Below threshold" (`extra/04_n_cycle__N_with_selection_then_B.png`, `run.out`).
   - Fix: when N moves to a tile, select only that tile (or clear the selection), so the next verdict key acts on what the user is looking at.
   - Gain: F6 +0.25, F5 +0.2.

3. **N does nothing, and says nothing, when nothing is flagged.**
   - Where: `focus_flagged` returns False (`graphs.py:836-851`), and the action ignores it (`main_window.py:569`). Next Flagged stays enabled whenever plots exist (`main_window.py:612-618`). In a fresh labelled session with no standard, N is a no-op (`extra/01_n_no_is__N_nothing_flagged.png`).
   - Fix: on False, show a status toast such as "No flagged plots in Pyruvate". Better, step on to the next compound that has a flag, the way Next Compound works.
   - Gain: F5 +0.15, F6 +0.15.

4. **In labelled mode, a peak outside the integration window carries no flag.**
   - Where: in Pyruvate, the M+0 apex of Bio_014 and Bio_019 sits about 0.08 min right of the dashed right offset, yet the tiles are clean, with no IS or with scyllo-Ins (`mL/05`, `extra/03_is_with_amount__scyllo.png`). "tR off" is built only from identity QC, which only unlabelled mode has (`plot_tile.py:86-88`). N therefore skips the samples that most need a look.
   - Fix (display only, no change to integration): give labelled tiles the same "tR off" badge when the M+0 or summed-EIC apex lies outside [tR − left offset, tR + right offset]. Its tooltip names the apex time.
   - Gain: F5 +0.25, F7 +0.1, F3 +0.1.

5. **The first Documentation page is blank on CI macOS dark again.**
   - Where: `MD/17_documentation__DocumentationViewer.png` shows the nav only, while `ML/17` rendered. Known and accepted by the team, but users see it.
   - Fix: keep a "Loading…" label over the view until a `runJavaScript("requestAnimationFrame(()=>requestAnimationFrame(()=>1))")` callback fires. That waits without nesting an event loop.
   - Gain: F5 +0.1, F8 +0.1.

6. **At 150%, the compound list shrinks to one row when Samples is open.**
   - Where: `150L/29` (filter "ine", "3 of 8", only Alanine visible), `150L/33` and `150D/33` (only Glycine). `left_toolbar.py:193` lets both lists fall to a 1 px floor.
   - Fix: give the compound list a 4-row floor, and when space runs out cap the sample list first (it already has its own filter).
   - Gain: F2 +0.2, F6 +0.1.

7. **The export prompt names a database field.**
   - Where: "Internal standard 'Palatinose' is missing required metadata… Problems found: • Missing or zero 'int_std_amount'" (`extra/09_export__QMessageBox.png`; `main_window.py:2860-2866`, `data_exporter.py:95-99`).
   - Fix: "Palatinose has no internal-standard amount in the compound list. Export peak areas instead?", with Cancel / Export Peak Areas. Drop the bullet list.
   - Gain: F9 +0.1, F3 +0.05.

8. **The 95-name standard menu has no search.**
   - Where: the Settings Choose… button and the sidebar row open the same three-column `QMenu` (`left_toolbar.py:733`, `extra/06_settings_choose__choose_menu.png`).
   - Fix: a popup with a filter field above a list, as the compound list already has. Put compounds with an amount first, or mark the ones without.
   - Gain: F6 +0.15, F1 +0.1, F9 +0.1.

9. **Apply window doesn't turn primary for its own draft.**
   - Where: with a tR window draft of 0.3, the caption reads "Re-extracts all 30 shown samples · not applied", but Apply window stays secondary. Apply turns primary for an offset draft (`extra/05_drafts__trwin_back.png`, `run.out` `('applywin', True, None)`; `integration_window_widget.py:770`).
   - Fix: apply the same `variant=primary` rule to `regenerate_button` while `tr_window` differs from the stored value.
   - Gain: F4 +0.1, F5 +0.05.

10. **The Add Compound form still cuts a heading at 150%.**
    - Where: "Standards" is cut through the middle above the new separator (`150L/18`, `150D/18`). On CI macOS, unlabelled, the qualifier help line is cut the same way (`ML/28`, `MD/28`).
    - Fix: snap the scroll area's height to the bottom of a whole row, or scroll so a heading never sits on the edge.
    - Gain: F2 +0.05, F1 +0.05.

11. **Labelled Full scan collapses the spectrum to one unlabelled bar.**
    - Where: on Full scan, the M+0…M+3 stems at ~174–177 become one black stroke on a 100–400 axis (`extra2/00___det921_full.png`).
    - Fix: keep the cluster bracket label on Full scan, and draw the background scan in the muted grey so the own cluster stays in colour.
    - Gain: F7 +0.1.

12. **"Not applied" has two spellings.**
    - Where: the peak window shows a standalone "Not applied" line, and the tR window caption gets "· not applied" in the warning colour (`integration_window_widget.py:42`, `:767`; `extra/05_drafts__trwin_back.png`).
    - Fix: one form, the suffix on the scope caption in both places.
    - Gain: F4 +0.05, F9 +0.05.

## Re-rating comparison

**My round-7 issues, status:**
1. **Spectrum hides the Q-ion label on short dialogs: fixed.** "174.00" and "247.98" at 921×581 (`MD/32`); 174.02 and 247.96 at 870×612 (`WL/32`); the cluster label is kept (`extra2/00___det921.png`).
2. **Internal standard with no amount surfaces only at export: fixed.** The sidebar reads "Palatinose · No amount: exports peak areas", and the note hides again for scyllo-Ins (`extra/02`, `extra/03`).
3. **Identity popup phantom qualifier chip: fixed** (`WL/31`, `MD/31`).
4. **Docs break prose mid-sentence: fixed** (`WL/17_…page1`, `…page2`, `…page5` show a real list).
5. **Blank first docs page on macOS: still open** (`MD/17`).
6. **Yes/No on export prompts: fixed** ("Cancel / Export Peak Areas", Cancel the default). The copy is still code-like (issue 7).
7. **Apply always primary: fixed.** Secondary at rest, primary after an edit (`run.out`). Apply window is not consistent with it (issue 9).
8. **No next-flagged key: fixed, but with traps** (issues 1–3).
9. **Add Compound slices a heading: partly fixed.** There is now a separator, but the heading is still cut at 150% (issue 10).
10. **Session import jargon: fixed.** "Deleted compounds and samples will match the file." (`main_window.py:2134`).
11. **Docs say "Valid (white)": fixed.** "…no peak gets a Below threshold badge." (`WL/17_…page14`).
12. **Abundance readout is not precise: fixed in code.** `.4g` on the current row (`chart_popup_dialog.py:127-134`). Not re-checked live.

**Improved beyond the list:**
- an unapplied tR window is kept per compound;
- Choose… in Settings;
- View › Compact/Comfortable;
- the Full scan toggle;
- Reset asks with Cancel as the default;
- the folded Baseline and tR window row on short windows (`ML/29`).

**Regressed:** nothing visual or functional that I can tie to this round. The compound-list type-ahead trap (issue 1) already existed for A and B at b804ecf (`main_window.py:530` there). N makes it far more likely to hit, because N is the first key a reviewer presses after picking a compound.

**Lost functionality: none.**
- No UI label disappeared between b804ecf and a696f0b; four were added (`labels_b804ecf.txt` against `labels_a696f0b.txt`).
- Round 7 traced every main-only label to a rename.
- Live checks:
  - Review and context menus: Inspect, Select All, Deselect, Show Only, Show All, Accept, Mark Bad, Curve Fit, Baseline;
  - View: Compact, Comfortable, Shared Y-Scale, Scale to Selected Peak, Find, Previous and Next Compound, Sample List;
  - File: Load, Add Compound, Open Recent, Export and Import Session, New Session, Clear, Export Data, Process External Data, Settings, Quit;
  - Help: Documentation, Check Data Setup, Updates, About;
  - every one is present and enabled where it applies (`run.out` MENUBAR lines).

**Per-platform limits:**
- **Windows:** judged from CI at 100% (1024×720), clean in both schemes. Not verified: 125% and 150%, the native dark title bar, hover.
- **macOS:**
  - the native menu bar wasn't verified;
  - the scheme was forced, not switched by the OS;
  - the keyboard checks set focus directly, because other tours share this machine.
- **150%:** the harsh 1008×633 stand-in.

```json
{"F1": 9, "F2": 9, "F3": 9, "F4": 9, "F5": 9, "F6": 8, "F7": 9, "F8": 9, "F9": 9, "overall": 8.9}
```
