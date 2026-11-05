# MANIC UI/UX review, round 10 (re-rating at 4119119), reviewer: opus

## Evidence

**Screenshots.** I viewed all 560 PNGs in the ten round-10 folders. The eight laptop and CI folders went through 3×3 contact sheets, and the two 2560 folders through 2×2 sheets (`sheets/`). I opened shots full size wherever a detail mattered: `05_labelled_grid` and `30_sidebar_filter_and_samples` at 2560, and the dark verdict tiles (`crops/27_dark.png`). I also built a side-by-side of the first docs page from every folder (`crops/docs_first_all.png`). Short names used below:
- `2560L/`, `2560D/`: offscreen 2560×1410, light and dark. This is the primary target.
- `WL/`, `WD/`: Windows CI at 1024×720.
- `ML/`, `MD/`: macOS CI at 1024×681.
- `mL/`, `mD/`: the local 14" Mac (1512×949).
- `150L/`, `150D/`: the 150% folders (1008×633 logical).

**My own drives.** I ran `pMANIC-review-r10` at 4119119 on Qt's offscreen platform with the 2560×1410 screen config. Scripts are in this folder, output is in `run.out`, and the shots are in `extra/`.
- **`drive10.py`, labelled data:**
  - fresh window: read the sidebar and the panel state;
  - loaded the data, then in the checklist opened the standard picker, typed "scyl", pressed Return, then Apply;
  - read the status bar, header, sidebar and badges;
  - Shared Y header button, View › Scale to Selected Peak, the peak button again;
  - Summary button, Ctrl+Alt+R and Ctrl+Alt+S, and the remembered settings;
  - from the compound list: N ×3, A, N, B, the N/A loop, then N with nothing left to review;
  - Peak window: drafted a Left offset and a tR window, read the captions and primaries, then Return to apply;
  - Settings: Theme set to Dark and back, Minimum area ratio edited, then Save;
  - read every menu, opened the detailed view and both summary popups;
  - a full export, answering the no-standard prompt;
  - resized to 1280×800 and 1024×768 with the Summary open, then measured clipped labels and fields.
- **`drive10.py`, unlabelled data:**
  - the header and View menu;
  - all 8 compounds and their badges;
  - Samples expanded at 2560, with and without a compound filter, with widget geometry measured;
  - 1280 and 1024 with the Summary open.
- **`probeN.py`:** unlabelled N from the compound list, which went 04 → 05 → 07 → 04 (wrap).
- **Label diff:** quoted UI strings at c574eca against 4119119 (`labels_*.txt`).

**Harness noise, not app bugs:**
- In `drive10.py` the unlabelled N presses went nowhere, because the new window was not active offscreen. `probeN.py` activated the window first, and N worked there.
- The "QMenu already deleted" tracebacks in `run.out` are my menu dump calling `QAction.menu()`, the same artefact as rounds 8 and 9.
- Every docs page is blank in both 2560 folders. That is the offscreen platform not painting QtWebEngine, because the same pages render on Windows CI and on the local Mac.

**Not run:**
- real hover and tooltips;
- the native macOS menu bar;
- Windows at 125% and 150%;
- a real OS scheme switch;
- a live window on the physical 2560 monitor (offscreen stands in);
- Delete Sample and Recover;
- session import;
- an EIC regeneration through Apply window.

## Verdict

The core workflow works end to end, and 10 of my 12 round-9 issues are fixed. I verified each of these live:
- **Checklist picker:** it now opens the searchable chooser. "scyl" filters to scyllo-Ins, Return picks it, and the button turns into **Apply** with "Continue without changes" beside it.
- **N toast:** it now reads "No flagged plots in Pyruvate".
- **Draft primaries:** only the last-edited draft button is primary.
- **tR caption:** it fits ("All 30 shown · not applied").
- **Chooser height:** it shrinks to its matches.
- **Export copy:** the no-standard prompt now says "Abundances will be peak areas, summed over the corrected isotopologues."
- **Docs key table:** it shows one key form, with a macOS note.

The Summary panel and the sidebar toggles work from the header, the View menu and Ctrl+Alt+R/S, and both are remembered. Shared Y and Scale to peak stay in sync with the View menu and with each other. Theme applies the moment you choose it. Verdict pastels now match the workbook (`2560L/27`). The export ran in 28 s, wrote five sheets and showed a toast. Nothing that exists on `main` is missing.

On the primary 2560 screen, though, the round's new sidebar sizing has a visible layout bug:
- **The Samples section gaps.** With Samples open and short lists, which is the normal unlabelled case, the Samples filter floats about 150 px below its heading. The checklist starts another ~130 px lower (`2560L/30`, `extra/11_samples_gap__samples_open.png`).
- **Clipping at 1024 with the Summary open.** Shrink the window to 1024 with the Summary still open, which is what happens when the remembered state meets a laptop. The sidebar drops to 256 px, "Compound list" clips to "Compound li", and the tR window field shows ".2" for 0.2 (`2560L/34`, `extra/09_narrow__1024.png`).
- **Older open items.** Out-of-window labelled peaks are still unflagged (declined), and the first docs page is blank on CI macOS in both schemes.

F2 drops to 8 for the two layout bugs. Everything else holds at 9.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 9 | One token system holds across all ten folders. At 2560 the six-column grid, the narrow sidebar and the Summary column read calm and balanced (`2560L/05`, `2560D/05`). The verdict pastels are soft and readable (`2560L/27`, `WL/27`). Held back by the floating Samples filter at 2560 (`2560L/30`), "Compound li" clipped at 1024 (`2560L/34`), and muddy dark washes: Below threshold (brown-grey) and Marked bad (olive) sit close in `2560D/27` (`crops/27_dark.png`). |
| F2 | Layout and hierarchy | 8 | The 2560 layout uses the space well: 30 tiles at about 305×260, and both Summary charts in full (`2560L/05`). Two defects. First, the Samples section's slack spreads inside the section (`left_toolbar.py:405-409` gives the section stretch 1 while its list is capped), so the filter and checklist float in blank space (`2560L/30`, `extra/11_*`). Second, below about 1100 px with the Summary open, the sidebar is squeezed under its content: it is held at 256 px minimum (`left_toolbar.py:243`), and the Summary keeps its width on resize (`main_window.py:798-826`). The header also wraps to two rows at 1024 and 1280. |
| F3 | Onboarding and workflow clarity | 9 | Quick Start step 4 now matches the checklist ("Click Continue, or Apply if you chose a different internal standard"; verified: the button becomes Apply). The keyboard line no longer contradicts itself (`mL/17`). The start screen adds a quiet "Rebuild an export without CDF files…" link (`*/02`). Gap: labelled peaks outside the window still look clean, so a new user trusts "No flagged plots" when four Pyruvate tiles need a look (`2560L/05`, Bio_014/018/019/020). |
| F4 | Consistency and polish | 9 | One chooser everywhere: checklist, sidebar, Settings and Process External Data (`post_load_checklist_dialog.py:109-112`, `update_old_data_dialog.py:89`). Buttons sit 4 to 8 px apart, and Settings orders its buttons per platform (`WL/16` Save/Revert, `mD/28` Revert/Save). Left: the two draft captions phrase scope differently ("Applies to all 30 shown samples · not applied" against "All 30 shown · not applied", `integration_window_widget.py:773`, `:802`). The popup titles mix case: "Label Incorporation" against "Peak area" (`isotopologue_ratio_widget.py:439`, `total_abundance_widget.py:258`; window titles likewise). |
| F5 | Feedback and state | 9 | Verified live: the N toast, menus naming the target tile ("Accept Bio_004 (Below Threshold)"), verdict pills plus washes, the draft captions, the Apply/Continue switch in the checklist, the export toast, and the Summary highlighting the selected sample. Gaps: out-of-window labelled peaks are unflagged (declined pending a definition). The first docs page is blank on CI macOS in **both** schemes this round (`ML/17`, `MD/17`; known limit). |
| F6 | Efficiency and flexibility | 9 | Panel toggles have shortcuts and are remembered (`run.out`: `settings stored True True`). The y-scale toggles are one click and mirror the View menu. Theme takes effect at once. The detailed view steps samples with ‹ ›. The checklist chooser filters by keyboard, and N/A/B work from the list. Gap: resizing to a laptop width keeps the remembered Summary open and clips the sidebar, instead of yielding the Summary (`extra/09_narrow__1024.png`). |
| F7 | Data visualisation | 9 | The verdict colours now carry the workbook's meaning as washes plus pills, and QC badges never tint the tile (`2560L/27`, `WL/27`). The Summary keeps both charts visible beside the grid at 2560, with names readable. The identity heatmap is clear (`*/32`). Remaining: out-of-window peaks look like clean tiles. The dark washes for Below threshold and Marked bad are close in hue (`crops/27_dark.png`); the pills carry the difference. |
| F8 | Modern feel | 9 | Toggleable side panels remembered between sessions, a live theme switch, a searchable chooser, one-key review, docs Find, and previous/next in the detailed view. It feels like considered software. The blank first docs paint on CI macOS and the floating Samples filter at 2560 are what still read as unfinished. |
| F9 | Taste (not AI slop) | 9 | The round-9 tells are gone: the doubled key table, the wordy popup footer, the quoted column name. Copy is short and specific ("No amount: exports peak areas", "↑↓ to read · Return or click to open a plot"). Left, all small: the abundance popup says "Peak area" twice ("Peak area · 30 samples" over an axis titled "Peak area, sum of isotopologues (×10⁴)", `2560L/13`). The Qualifier QC key appears in the grid header and again as the Identity legend, at the same time (`2560L/24`). The header's Docs and Settings icons repeat Help › Documentation (F1) and File › Settings, next to two segmented controls (`graphs.py:263-268`). |

Overall: (9+8+9+9+9+9+9+9+9)/9 = **8.9** (round 9: 9.0).

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| The Qualifier QC key ("● Validated ● Failed ● Not assessed") in the grid header, and the Identity legend ("■ ✓ Validated 16 ■ × Failed 2 ■ ? Not assessed 4") | `2560L/24`, `graphs.py:271-283` | Partly. The header key explains the tile line colours and the legend adds counts, but both are on screen at once. Folding the counts into the header key, or dropping the header key while the Summary is open, removes one. |
| "Peak area" in the popup subtitle and its axis title | `2560L/13`, `total_abundance_widget.py:39`, `:258` | No. Make the subtitle "30 samples" and keep the precise axis title. |
| Docs and Settings icon buttons in the grid header | `*/05`, `graphs.py:263-268` | Weak. Both are one keystroke or menu away (F1, File › Settings), and the status-bar deconvolution text already opens Settings. Under the "uncluttered" directive the Docs icon is the one I would drop. |
| The Sidebar and Summary toggles in the header, the View menu and Ctrl+Alt+S/R | `*/05`, `main_window.py:489-499` | Yes. A menu command with its shortcut, plus a button next to the panel it opens. |
| Shared Y and Scale to peak in the header and the View menu | `*/05`, `main_window.py:509-520` | Yes. The user asked for them visible, and the menu holds the shortcuts. |
| The internal standard in the sidebar row, the checklist and Settings | `*/04_*`, `*/16` | Yes as places, and now one widget everywhere. |
| "No amount: exports peak areas" as the chooser heading, the sidebar note and the export prompt | `*/31`, `extra/00___checklist_chooser*` | Yes. A label at the moment of choice, a persistent state, and a confirmation at the action. |

## Top 12 issues, ranked by user impact

1. **The Samples section scatters into blank space on tall windows.** This is the primary screen.
   - Where: `2560L/30`, `2560D/30`, `extra/11_samples_gap__samples_open.png`. In unlabelled data with Samples open, the section spans y 397–1097. The filter sits at y 550, the checklist at 709–973, and blank bands of 125–150 px fall between them. The cause is `left_toolbar.py:405-409`: an expanded section gets stretch 1, while `_set_list_heights` caps the list at its rows, so the layout hands the slack to the gaps inside the section.
   - With Samples closed, the same short lists leave about 700 px of empty sidebar between the compounds and the Peak window (`2560L/24`). That is cleaner, but the Peak window ends up far from what it edits.
   - Fix: keep the section at stretch 0 and let the existing trailing `addStretch` take the slack. The section then hugs its rows, and the blank stays in one band above the Peak window. Or add a stretch after `sample_list` inside `samples_body`.
   - Gain: F2 +0.5, F1 +0.2.

2. **At laptop widths with the Summary open, the sidebar is clipped.**
   - Where: `2560L/34`, `2560D/34`, `extra/09_narrow__1024.png`, `extra/12_narrow_unlab__u1024.png`. At 1024 the splitter reads `[256, 494, 266]`. "Compound list" needs 87 px and gets 74, so it shows "Compound li". The tR window field shows ".2" (labelled) or "22" (unlabelled) for 0.2 and 0.22. A clipped number in an input reads as the wrong value.
   - Trigger: a user who leaves the Summary open on the 27" monitor and then works on a laptop. Fresh laptop windows open with the Summary closed (`WL/05`).
   - Fix: on resize, hide the Summary, or let the grid take its width, once the grid would drop to two columns. Raise the sidebar minimum to its content width, about 280 px (`left_toolbar.py:243`). Elide the status labels rather than clipping them.
   - Gain: F2 +0.3, F6 +0.2, F1 +0.1.

3. **Labelled peaks wholly outside the integration window carry no flag.**
   - Where: Pyruvate Bio_014, 018, 019 and 020 (`2560L/05`, `extra/03_peak_window__both_drafts.png`). N then says "No flagged plots in Pyruvate". That is now accurate wording, but the review gap is still the largest one left.
   - Status: declined pending a science-side definition.
   - Fix: settle the definition in the PR follow-up.
   - Gain: F5 +0.2, F7 +0.15, F3 +0.1.

4. **The first Documentation page is blank on CI macOS, now in both schemes.**
   - Where: `ML/17`, `MD/17`, `crops/docs_first_all.png`. It renders on Windows CI and on the local Mac.
   - Fix: keep the "Loading…" page up until `loadFinished` and a `requestAnimationFrame` round trip through `runJavaScript` have both fired, then switch. As things stand, the switch happens before the first paint.
   - Gain: F5 +0.1, F8 +0.1.

5. **The dark verdict washes for Below threshold and Marked bad are hard to tell apart.**
   - Where: `2560D/27`, `crops/27_dark.png`, `WD/27`. Brown-grey against olive, at similar lightness. The pills ("Below threshold", "Marked bad") carry the meaning, but at a glance across 30 tiles the wash is what the eye reads.
   - Fix: in `_verdict_scheme` (`colors.py:103`), raise the dark fill's chroma for the red-hued verdict a step, or lift its lightness apart from the tan. Keep the workbook hues.
   - Gain: F7 +0.1, F1 +0.05.

6. **The grid header carries five controls plus three icons, and wraps at laptop widths.**
   - Where: `2560L/05`. At 1024 and 1280 the title and icons sit on one row and the two segmented controls on a second (`extra/09_narrow__1280.png`, `WL/05`).
   - Fix: drop the Docs icon (F1 and Help cover it). That alone may keep 1280 on one row.
   - Gain: F9 +0.1, F2 +0.05.

7. **The Qualifier QC key is shown twice at once.**
   - Where: the grid header key and the Identity legend (`2560L/24`, `WL/24`).
   - Fix: hide the header key while the Summary is open, or move the counts into it and drop the Identity legend row.
   - Gain: F9 +0.1.

8. **The two draft captions describe their scope differently.**
   - Where: "Applies to all 30 shown samples · not applied" (Peak window) against "All 30 shown · not applied" (tR window) (`extra/03_peak_window__both_drafts.png`; `integration_window_widget.py:773`, `:802`).
   - Fix: one pattern for both, for example "All 30 shown · not applied" and "Bio_001 · not applied".
   - Gain: F4 +0.05, F9 +0.05.

9. **The popup titles mix case.**
   - Where: "Label Incorporation · 30 samples" against "Peak area · 30 samples" (`2560L/13`, `2560L/14`). The window titles do the same ('Label Incorporation — MANIC', 'Peak area — MANIC').
   - Fix: sentence case, "Label incorporation" (`isotopologue_ratio_widget.py:439`).
   - Gain: F4 +0.05.

10. **The abundance popup repeats its quantity.**
    - Where: the subtitle "Peak area · 30 samples" sits above the axis "Peak area, sum of isotopologues (×10⁴)" (`*/13`).
    - Fix: make the subtitle "30 samples".
    - Gain: F9 +0.05.

11. **The unlabelled Summary panel is two-thirds empty at 2560.**
    - Where: Identity and Peak area end around y 520 of 1380 (`2560L/24`, `extra/11_*`).
    - Fix: let the Identity rows grow to a comfortable row height, up to about 28 px, when there is room. Fewer samples then read larger rather than leaving a void.
    - Gain: F2 +0.05, F7 +0.05.

12. **The checklist scrolls its own title away at 150%.**
    - Where: `150L/04_*_steps`, `150D/23_*_steps`. With the pattern steps open, "Check your data setup" scrolls off the top.
    - Fix: keep the title and the button row outside the scroll area.
    - Gain: F4 +0.05.

## Re-rating comparison

**My round-9 issues, status:**
1. **Checklist uses a plain 96-item combo: fixed.**
   - `StandardPicker` opens the `StandardChooser` (`post_load_checklist_dialog.py:109-112`). Live: "scyl" filtered to scyllo-Ins, Return picked it, Apply appeared, and the standard was set.
   - Process External Data uses the same picker (`update_old_data_dialog.py:89`).
2. **Out-of-window labelled peaks unflagged: still open.** Declined (issue 3).
3. **N toast overstates the check: fixed.** It reads "No flagged plots in Pyruvate" (`run.out`).
4. **Blank first docs page on CI macOS: still open, and worse.** It is blank in both schemes this round (issue 4).
5. **Quick Start keyboard line contradicts itself: fixed** (`mL/17`).
6. **Docs key table doubles every key: fixed.** One form, plus "On macOS, press ⌘ where these tables say Ctrl" (`mL/17`).
7. **tR caption wraps: fixed.** "All 30 shown · not applied" fits on one line.
8. **Two primary buttons at once: fixed.** The last-edited draft is primary (`run.out`: `apply None applywin primary`).
9. **Chooser stays 10 rows tall after filtering: fixed.** It shrinks to 102 px for two rows (`extra/00___checklist_chooser_filtered.png`).
10. **Wordy popup footer: fixed.** "↑↓ to read · Return or click to open a plot".
11. **No-IS export copy quotes a column: fixed.** "Abundances will be peak areas, summed over the corrected isotopologues."
12. **Detailed view scrolls at small sizes: not reproduced.** The CI shots at 870×612 fit (`WL/11`, `WD/33`). I did not rerun the 921×581 local case.

**Improved beyond the list:**
- the Summary as a resizable right-hand panel with both charts always visible, which uses the 2560 width well;
- remembered panel toggles with shortcuts;
- visible Shared Y and Scale to peak toggles, synced both ways;
- the Appearance setting, applied at once;
- verdict colours that match the workbook;
- buttons that never touch;
- previous and next in the detailed view;
- the start-screen rebuild link;
- empty sidebar sections hidden before loading (`*/02`).

**Regressed:**
- The Samples section layout at 2560 (issue 1). It comes from this round's sidebar sizing, which replaced the round-9 lists/inspector splitter (`c585859`).
- The CI macOS docs blank now shows in both schemes.

**Lost functionality: none against `main`.**
- The menus are complete:
  - File: Load, Add Compound, Load Raw Data, Open Recent, Export and Import Session, New Analysis Session, Clear Session, Export Data, Process External Data, Settings, Quit;
  - View: Show Sidebar, Show Summary, Compact, Comfortable, Shared Y-Scale, Scale to Selected Peak (labelled only, as before), Find Compound, Previous and Next Compound, Sample List;
  - Review: Inspect, Select All, Deselect All, Show Only Selected, Show All, Next and Previous Flagged, Accept, Mark Bad, Curve Fit, Baseline Correction;
  - Help: Documentation, Check Data Setup, Check for Updates, About.
- The context menu matches (`*/09_*__menu`). Every verdict, fit control and scale option worked live.
- Removed strings: the old export and toast copy, the old popup footer, and "Total abundance", which is now "Peak area". The draggable split between the sidebar lists and the Peak window (round 9, "Drag to share space between lists and inspector") is gone, replaced by auto-fit. It never existed on `main`, so this is not a loss against `main`. It was the one manual way to fix the issue-1 gap, though.

**What still stands between each factor and a 10:**
- **F1:** issue 1, the clipping in issue 2, and the dark washes (issue 5).
- **F2:** issues 1 and 2, the header wrap, and the empty unlabelled Summary.
- **F3:** the out-of-window flag.
- **F4:** the caption and title-case mismatches, and the checklist scroll at 150%.
- **F5:** the out-of-window flag and the CI macOS docs blank.
- **F6:** the Summary should yield on resize.
- **F7:** the out-of-window flag and the dark washes.
- **F8:** the docs blank and issue 1.
- **F9:** the three duplications (QC key, "Peak area", the Docs icon).

**Per-platform limits:**
- **2560:** offscreen render only, with no native title bar or menu bar; QtWebEngine does not paint there.
- **Windows:** CI at 100% only. Clean in both schemes. Not checked: 125% and 150%, and hover.
- **macOS:**
  - not checked: the native menu bar and an OS scheme switch;
  - CI docs are blank;
  - the local Mac renders the docs.
- **150%:** only the harsh 1008×633 stand-in.

```json
{"F1": 9, "F2": 8, "F3": 9, "F4": 9, "F5": 9, "F6": 9, "F7": 9, "F8": 9, "F9": 9, "overall": 8.9}
```
