# MANIC UI/UX review, round 7 (re-rating at b804ecf), reviewer: opus

## Evidence

**Screenshots.** I viewed all 440 PNGs in the eight round-7 folders as 3×3 contact sheets (`sheets/`). I opened full size wherever a detail mattered: the CI macOS detailed spectrum, the identity popup, the 150% checklist and sidebar, and the docs pages. Short names used below:
- `WL/` and `WD/`: Windows light and dark (CI, 1024×720).
- `ML/` and `MD/`: CI macOS light and dark (1024×681).
- `mL/` and `mD/`: the local Mac (1512×949).
- `150L/` and `150D/`: the 150% folders (1008×633 logical).

**My own drives.** These ran on this Mac against `pMANIC-review-r7` at b804ecf, with real windows. The scripts are in this folder, and the full stdout is in `run.out`.

`drive.py` writes `extra/`. On labelled data it:
- did a fresh load and read the sidebar, header and status bar;
- set Palatinose as the internal standard, which gave Bio_004 "Below threshold";
- edited Left offset with nothing selected, then switched compound and back, selected and deselected a plot, and applied with Ctrl+Return;
- pressed A, B, B on Bio_004 with forced focus;
- changed Settings › General › Minimum area ratio and saved it;
- opened the abundance popup and moved its current row;
- opened the detailed view with Return;
- opened Summary at 1024×640;
- exported the session and opened Import Session, then cancelled;
- exported the data, answering Yes;
- opened the Clear Session prompt.

On unlabelled data it went through all 8 compounds in Summary, opened the Identity popup for Lactate, Glycine and Serine, and exported.

`check2.py` writes `extra2/`. It checked the abundance popup's current-row readout. It also opened the Glycine detailed view at the CI macOS dialog size (921×581) and again at 1200×900, and read which spectrum labels were visible.

I diffed the UI action labels between `origin/main`, 1581a94 and b804ecf (`labels_*.txt`).

My first run hung in the labelled export. That was my script's fault: it had no `__main__` guard, so the export's process pool re-ran it. With the guard added, the export finished in 16.5 s. It was not an app bug.

**Not run:**
- real hover and tooltips;
- the native macOS menu bar (I saw only the captured popups);
- Windows at 125% and 150%;
- a real OS-driven scheme switch;
- Delete Sample and Recover;
- the import itself (I opened the Import Session prompt and cancelled it);
- an EIC regeneration (my Apply didn't need one).

## Verdict

**Functionally, every path I drove works.**
- **Fresh load:** all sidebar rows tick, the header reads "Pyruvate tR 7.09", and the status bar shows the "Imported 2850 EICs" toast and the deconvolution state.
- **Verdict keys:** A accepts, B marks, and a second B returns to "Below threshold".
- **Peak window:** an edit made with nothing selected is kept per compound. It reads "Not applied" when I come back to Pyruvate. Selecting a plot shows that sample's own values, and deselecting brings the draft back. Ctrl+Return applies it, and the detailed view then reads "integration 6.990–7.125 min".
- **Settings:** two pages and a 720×585 window. The dirty title is "Settings[*]", and Save is primary until it is saved.
- **Exports:** labelled export wrote 5 sheets in 16.5 s; unlabelled wrote Raw Values, Abundances and Qualifier QC in 3 s. Both end in a toast with Show in Folder.
- **Session:** export ends in a toast that names the folder. Import asks once, with Cancel as the default and an "Import Overrides" button.
- **Clear Session:** Cancel is the default, and the red button says "Clear Session".

Eleven of my twelve round-6 issues are fixed or settled by the user's decision. The app is a quiet, consistent tool that holds up on Windows and macOS, in light and dark, and at 150%.

What still stands between it and a 10 is a short list:
- On short screens, the mass spectrum hides the compound's own quantifier-ion label, the one peak the user opened the view to read.
- An internal standard without an amount shows up only at export time.
- The Identity popup still names a qualifier the method doesn't have.
- The docs render wrapped prose as broken lines.
- The first docs page can still be blank on CI macOS.
- A few prompts keep generic Yes/No buttons.
- The Apply button is primary even when there is nothing to apply.
- The review loop still has no "next flagged sample" key.

## Scores

| # | Factor | Score | Justification |
|---|--------|-------|---------------|
| F1 | Visual design | 9 | One token system holds across all eight folders (`WD/24`, `MD/26`, `150D/29`). Abundance bars are now neutral ink, and a selected sample takes the accent (`extra/05_popup__abundance_row3.png`, `WD/13`). Settings fits its content (`WL/16_*`). Held back by: docs prose broken mid-sentence by forced line breaks (`WL/17_…page1`, `…page2`; `documentation_viewer.py:478`); a spectrum whose tallest stem runs into the top edge with no label (`ML/32`, `150L/32`). |
| F2 | Layout and hierarchy | 9 | On short windows the sidebar folds Baseline and tR window into one labelled row, "Baseline, tR window · On · 0.22 min" (`ML/29`, `150L/29`). The Summary panel folds its second chart (`extra/07_summary__w1024.png`). The checklist keeps its pattern help visible at 150% (`150L/04_…Dialog`). The detailed view at 921×581 is the weak spot: a 2-tick spectrum axis, with the main label dropped (`ML/32`, `extra2/00_gly__det921.png`). Add Compound slices the "Standards" heading at the scroll edge on CI macOS and at 150% (`ML/19_*`, `150L/18_*`). |
| F3 | Onboarding and workflow clarity | 9 | Glycine (no assessable qualifier) now gets the grid-header note with the guide link (`WL/26`). The Quick Start key table lists A, B, Ctrl/⌘+Return and Ctrl+Shift+B/Y/P (`docs/00_quick_start.md:14-36`). The start footer is links only (`WL/02`). Gaps: an internal standard with no `int_std_amount` gets a green tick in the sidebar and is first questioned at export (`main_window.py:2849`). One docs page is stale: '"Valid" (white)' (`docs/Reference_Peak_Validation.md:15`). |
| F4 | Consistency and polish | 9 | macOS now shows ⇧⌘B on Baseline Correction (`ML/10_review_menu__menu`). "Not assessed" is one term in the header, the legend, Summary and the detailed legend (`WD/32`). Settings orders its buttons per platform (Save/Revert on Windows, Revert/Save on macOS). Gaps: the export prompts use "&Yes/&No" while Clear Session and Import use verbs (`main_window.py:2829`, `:2849`). The Identity popup shows a "Qualifier ion 2 · not in the method" chip that the grid and Summary don't show (`WL/31`, `channel_chips.py:35-39`). |
| F5 | Feedback and state | 9 | Verified live: "Not applied" survives a compound switch; "Applies to Bio_003" when a selection narrows the scope; the Below threshold, Accepted and Marked bad pills; the Settings dirty title; the toasts for import, export and session export; Cancel as the default on destructive prompts. Gaps: the Q-ion label disappears on short spectra (`matplotlib_plot_widget.py:750-757`). The internal standard's missing amount surfaces late (`main_window.py:2849`). The first Documentation page was captured blank on CI macOS dark (`MD/17_documentation__DocumentationViewer.png`). Apply is primary even with no draft (`integration_window_widget.py:323`). |
| F6 | Efficiency and flexibility | 9 | A and B verdict keys, Ctrl/⌘+Return Apply, the scale toggles, Find, Previous and Next Compound, the Compact density, the folded editors on short windows, and per-compound drafts. To reach 10: a key to jump to the next flagged tile (Below threshold, QC fail, Not detected) and a key to focus the Peak window fields. |
| F7 | Data visualisation | 9 | The labelled spectrum now opens on the isotopologue cluster (155–195 m/z), and "Reset all" shows the full scan (`WL/11`, `mL/11`). The detailed legend wraps every channel. Identity Summary shows only the compound's own qualifiers: Lactate has 1 column, with counts 10 / 0 / 1 (`extra/11_unlab__sum1.png`). Abundance bars are neutral, with the accent marking the selection. Remaining: the hidden Q-ion label and the full-height mass0 guide that hides the stem height on short dialogs (`ML/32`, `MD/32`, `150L/32`; reproduced in `extra2`). The current-row "precise" readout looks the same as its neighbours for values ≥1 (2.89 vs 2.89). |
| F8 | Modern feel | 9 | Toasts with actions, drafts that survive navigation, a two-page Settings that fits its content, folded editors, one-key verdicts and a live scheme switch. It reads as modern desktop software. The docs viewer is what feels old: ragged `<br>` prose, and a numbered list on the Process External Data page rendered as broken lines (`WL/17_…page5`). |
| F9 | Taste (not AI slop) | 9 | The round-6 tells are gone: the over-sized Settings, the footer instruction, the code-like "Qualifier colour =" legend and the stock teal bars. What is left is small and named in the table below. The screens feel made for GC-MS review: tR in the header, M+n chips, an Identity grid, a peak window with scope captions. |

Overall: (9+9+9+9+9+9+9+9+9)/9 = **9.0** (round 6: 8.9).

### F9 tells and duplications, named

| Tell | Where | Justified? |
|---|---|---|
| Identity popup chip "Qualifier ion 2 · not in the method" for Glycine and Lactate | `WL/31`, `MD/31`; `channel_chips.py:35-39` | No. It names state that doesn't exist, and the grid and Summary already dropped it. |
| Apply drawn as the primary button when there is nothing to apply | `WL/05`, `ML/05`; `integration_window_widget.py:323` | No. The accent stops meaning "this needs doing". |
| Generic "&Yes / &No" on two export prompts | `main_window.py:2829`, `:2849` | No. Every other prompt names its verb. |
| Session import: "Compound and sample deletion states will be synchronized." | `main_window.py:2121` | No. It is jargon where a plain sentence would do. |
| Docs prose with forced line breaks | `WL/17_…page1`, `…page2`; `documentation_viewer.py:478` | No. It looks unedited. |
| "Qualifier QC:" key on the unlabelled header while Summary shows its counted legend | `WL/24`, `extra/11_unlab__sum1.png` | Yes. One keys the tile traces, the other keys the cells. |
| Internal standard in the sidebar, the checklist and Settings › General (read-only) | `WL/05`, `WL/04_*`, `WL/16_*` | Yes. Status, a setup step, and context for the reference peak. |
| Review menu and plot context menu | `WL/09`, `WL/10` | Yes. A menu plus a context menu. |
| Deconvolution in the status bar and in Settings | `WL/05`, `WL/16_…page1` | Yes. Persistent status that opens the editor. |
| Sidebar "Not loaded" rows and canvas "Drop a compound list here" | `WL/02` | Yes. Status versus the call to action. |

## Top 12 issues, ranked by user impact

1. **On short dialogs the mass spectrum hides the compound's own ion label.**
   - Where: the Glycine detailed view on CI macOS (921×581) and at 150%. The Q-ion stem at 174 runs to the top edge with no "173.99" label, while the smaller qualifier keeps its label. See `ML/32_*`, `MD/32_*`, `150L/32_*`, `150D/32_*`. I reproduced it: at 921×581 the labels are `[('174.02', False), ('248.02', True)]`, and at 1200×900 both are visible (`extra2/00_gly__det921.png`, `check2.py` output).
   - Cause: `_declutter_peak_labels` hides any label that would cross the plot top (`matplotlib_plot_widget.py:750-757`). The headroom is a fixed 1.18× of the data (`:122`, `:419`), and that is too little when the axes are short. The full-height mass0 guide drawn at the same m/z (`detailed_plot_dialog.py:806`) then hides how tall the stem is.
   - Fix: reserve the label height in pixels. After the first draw, raise `ylim` until the tallest own label fits. Never drop an own-ion label for want of headroom. Draw the mass0 guide behind the stems and lighter, or stop it short of the stem.
   - Gain: F7 +0.25, F5 +0.1, F2 +0.1.

2. **An internal standard without an amount is first questioned at export.**
   - Where: I chose Palatinose in the sidebar. It got a green tick, and Settings named it. Only File › Export said "Internal standard 'Palatinose' is missing required metadata. Proceed with export in Peak Area mode instead?" (`main_window.py:2849`, `extra/09_export__QMessageBox.png`).
   - Why it matters: the user reviews the whole session believing Abundances will be calibrated.
   - Fix: check `int_std_amount` when the standard is chosen, in the sidebar menu, the checklist and Process External Data. Show it on the status row, for example "Palatinose · no amount: Abundances export as peak areas", with the guide link.
   - Gain: F5 +0.25, F3 +0.1.

3. **The Identity popup names a qualifier the method doesn't have.**
   - Where: for Glycine and Lactate, the popup adds a dotted "Qualifier ion 2 · not in the method" chip (`WL/31`, `MD/31`, `150L/31`). `identity_key_chips` adds a chip for every empty qualifier slot (`channel_chips.py:35-39`). The grid header and Summary now show only real qualifiers (`extra/11_unlab__sum1.png`).
   - Fix: drop the placeholder chips.
   - Gain: F9 +0.1, F4 +0.1, F7 +0.05.

4. **The docs break prose mid-sentence.**
   - Where: the viewer turns on `markdown.extensions.nl2br` (`documentation_viewer.py:478`), so source wrapped at 80 columns renders as ragged lines. Examples:
     - "For a one-page path, see / Quick Start. For targeted / profiling…" (`docs/01_user_guide.md:5-7`, `WL/17_…page1`);
     - "…known compounds when you are / not performing…" and "…in each / sample:" (`docs/Unlabelled_Targeted_Analysis.md:15-16`, `WL/17_…page2`);
     - the Process External Data numbered conditions render as `<br>` lines, not a list (`WL/17_…page5`).
   - Fix: remove `nl2br`. Where a hard break is really wanted, use a blank line or a list.
   - Gain: F1 +0.1, F8 +0.1, F9 +0.1.

5. **The first Documentation page can still open blank on macOS.**
   - Where: `MD/17_documentation__DocumentationViewer.png` is empty, even though the tour waits on `viewer.is_rendered` before capturing (`ui_tour.py:483`). This time `ML/17` rendered. The paint-delay fix was reverted after it crashed QtWebEngine.
   - Fix: keep the "Loading…" page until the page itself reports a frame. Have `runJavaScript("requestAnimationFrame(()=>requestAnimationFrame(()=>1))", callback)` reveal the view from its callback. The callback runs on the GUI thread after `loadFinished`, with no nested event loop and no blocking. Make `is_rendered` follow the same flag, so the tour tests the real signal.
   - Gain: F5 +0.1, F8 +0.1.

6. **Two export prompts keep generic Yes/No buttons.**
   - Where:
     - "You have not selected an internal standard. Proceed with export?" (`main_window.py:2829`);
     - "Internal standard 'Palatinose' is missing required metadata…" (`:2849`).

     Both read "&Yes / &No", with Yes as the default (`extra/09_export__QMessageBox.png`). Clear Session and Import Session now use verb buttons.
   - Fix: use "Export Peak Areas" / "Cancel" and "Export" / "Cancel".
   - Gain: F4 +0.1, F9 +0.05.

7. **Apply is the primary button even when there is nothing to apply.**
   - Where: `apply_button` always has `variant=primary` (`integration_window_widget.py:323`). The filled blue Apply sits under untouched fields on every grid screenshot (`WL/05`, `ML/05`, `150L/05`). The new "Not applied" draft state is exactly when it should stand out.
   - Fix: secondary while the fields match the stored values, primary while `_has_draft()` is true. Keep it enabled, so re-applying to a mixed selection still works.
   - Gain: F5 +0.1, F9 +0.1.

8. **No key to jump to the next flagged sample.**
   - Where: the review loop for 30 samples is arrow keys, then A or B. Nothing jumps to the next tile with "Below threshold", "QC fail", "QC partial" or "Not detected" (`docs/00_quick_start.md:16-24`).
   - Fix: N and Shift+N (or ⌥↓ and ⌥↑) move focus to the next and previous flagged tile, listed in the Review menu and the key table.
   - Gain: F6 +0.25.

9. **The Add Compound form slices a section heading at its scroll edge on short screens.**
   - Where: "Standards" is cut in half above the buttons on CI macOS and at 150% (`ML/19_add_compound_empty_submit__*`, `150L/18_*`, `150L/19_*`).
   - Fix: add a top fade or separator on the button row when the form scrolls, or snap the scroll area's height to whole rows.
   - Gain: F2 +0.05, F1 +0.05.

10. **The session import prompt reads like code.**
    - Where: "Compound and sample deletion states will be synchronized." (`main_window.py:2121`, `extra/08_sessions__QMessageBox.png`).
    - Fix: "Deleted compounds and samples will match the file."
    - Gain: F9 +0.05, F3 +0.05.

11. **One docs page contradicts the app.**
    - Where: '…all peaks are treated as "Valid" (white) by default.' (`docs/Reference_Peak_Validation.md:15`). Tiles have no white "Valid" state; they show no badge.
    - Fix: "…no peak gets a Below threshold badge."
    - Gain: F3 +0.05, F4 +0.05.

12. **The abundance popup's precise readout rarely shows.**
    - Where: the current row uses `.3g` (`chart_popup_dialog.py:123-134`). The axis is scaled to ×10ⁿ, so most values are 1–9.99, and the "precise" text equals the compact text ("2.89" vs "2.89", `check2.py`). The row stands out only by a text-colour change.
    - Fix: give the current row four significant figures, or the unscaled value with its unit ("2,893 × 10³"), plus the row marker it already has.
    - Gain: F7 +0.05.

## Re-rating comparison

**My round 6 issues, status:**
1. **Identity summary counts absent qualifiers: fixed.** Lactate's Summary has one "Qualifier 1" column, and its counts are Validated 10, Failed 0, Not assessed 1 (`extra/11_unlab__sum1.png`). It is partly open in the popup chips (issue 3).
2. **No grid note when no qualifier can be assessed: fixed.** Glycine's header reads "Qualifier 1 is not assessed: the compound list gives it no expected ratio. See Fix a missing qualifier ratio" (`WL/26`, live log).
3. **Session file in `manic_session_export/`: declined by the user, not scored.** The toast names the real folder ("Exported mysession.json to manic_session_export").
4. **Docs keyboard table: fixed** (`docs/00_quick_start.md:14-36`).
5. **macOS hides ⌘⇧B: fixed** (`ML/10_review_menu__menu`, `MD/10_…`).
6. **Big, near-empty Settings: fixed.** General plus Deconvolution, at 720×585 (`WL/16_*`, live log).
7. **Labelled spectrum wastes its width: fixed.** It opens on the cluster, and Reset all shows the full scan (`WL/11`). The short-dialog label bug is new to my list (issue 1).
8. **Stock teal bars: fixed.** The bars are neutral ink, and the selected Bio_002 is in the accent (`extra/05_popup__abundance_row3.png`).
9. **Blank first docs page: still open** on CI macOS dark (issue 5).
10. **Footer instruction: fixed.** The footer is now two links (`WL/02`).
11. **QC legend reads like code: fixed.** It is now "Qualifier QC:". Showing it next to the Summary legend is justified (see the F9 table).
12. **150% burying: fixed.** The checklist keeps "How do I change a pattern?" in view (`150L/04_…Dialog`). The sidebar folds Baseline and tR window into a row showing their values, with no lone scrollbar (`150L/29`, `ML/29`).

**Improved beyond the list:**
- Unapplied peak-window edits survive compound switches and selection changes, and they are marked "Not applied" (live).
- The detailed legend wraps, and popup text is larger.
- Clear Session defaults to Cancel. Import asks once.
- Routine successes are toasts that stay inside the window.

**Regressed:** nothing functional. The spectrum label drop (issue 1) may predate this round, since round 6's unlabelled detailed captures were taller. It is visible in every short folder now.

**Lost functionality: none found.**
- The labels present only on `origin/main` are the same renames I traced in round 6, for example "View Detailed..." → "Inspect *sample*...", "Update tR Window" → "Apply window", and "Shared y-scale" → View › Shared Y-Scale (`labels_main.txt` against `labels_b804ecf.txt`).
- Between 1581a94 and b804ecf no label disappeared. "Show corrected data" was added.
- The Settings merge kept every control: Mass tolerance, Integration method, the internal standard's Reference peak, Minimum area ratio, Natural abundance, all of Deconvolution, and the unlabelled Qualifier Ratios page (`WL/16_*`, `WL/27_*`).
- Live checks:
  - the A and B keys;
  - Ctrl+Return;
  - Settings save;
  - both exports and the session export;
  - Import Session up to its confirm prompt;
  - Clear Session;
  - the detailed view by Return;
  - the abundance popup;
  - the Identity popups;
  - Summary on short windows.

**Per-platform limits.**
- **Windows** was judged from CI at 100% and 1024×720, and is clean in both schemes. Not verified: 125% and 150% scaling, the native dark title bar, hover and tooltips.
- **macOS:**
  - The native menu-bar rendering was not verified (only the captured popups).
  - The tour forces the scheme, so a real OS switch was not tested.
  - Keyboard verdicts were verified after forcing activation, because other tours share this machine.
- **150%** is the harsh 1008×633 stand-in, not a real laptop.

```json
{"F1": 9, "F2": 9, "F3": 9, "F4": 9, "F5": 9, "F6": 9, "F7": 9, "F8": 9, "F9": 9, "overall": 9.0}
```
