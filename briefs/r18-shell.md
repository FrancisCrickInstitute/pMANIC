# Iteration 16, group shell

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r18-linux.md` first and follow it.
Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r18-shell`
(branch `uiux/r18-shell`, base `72561139`; `testdata` linked). Scratch: `/home/willyg/code/uiux-scratch/r18-shell/`.

Files you own: `src/manic/ui/main_window.py`, `settings_window.py`, `start_panel.py`,
`post_load_checklist_dialog.py`, `integration_window_widget.py`, `toast_notification.py`,
`left_toolbar.py`, `sidebar_widgets.py`, `docs/**`, and their feature-named tests
(`tests/test_main_window_shell.py`, `tests/test_settings_window.py`, `tests/test_start_panel.py`,
`tests/test_post_load_checklist.py`, `tests/test_integration_window.py`, `tests/test_sidebar.py`,
`tests/test_peak_review_menu.py`). Others own the chart and Summary files.

Findings (round 13; reproduce each first; the reviewers' probe images and JSON are under
`/home/willyg/code/uiux-scratch/review-r13-sol/` and `review-r13-opus/`):
1. Sol #1: a long internal-standard name on Settings › Internal standard pushes the Choose button
   out of the 720 px dialog (page 801 px in a 472 px viewport, no horizontal scroll) and loses its
   end without hover. Bound the name, elide in the middle, full name on hover; Choose stays visible.
2. Sol #2 and #5: the per-sample fit table on Settings › Deconvolution lets a long Sample column
   (599 px in a 460 px viewport) push the Fit type editors out of view, with no full-name tooltip;
   and a horizontal scroll bar cuts into the last promised row. Reserve Fit type's width, let
   Sample take the rest with middle elision and full-name hover, and keep the promised whole rows
   visible (no horizontal scroll bar, or count it in the height).
3. Sol #6: the Deconvolution page's compound heading clips a long name without an ellipsis or
   tooltip. Reuse the bounded header-name behaviour the grid and popups use
   (`HeaderName` in `chart_header.py`; import it, do not edit that file).
4. Sol #3: on the start screen, two long Recent compound-list names in different folders look
   identical: the filename takes the whole 360 px column, the folder gets no room, no tooltip.
   Bound and middle-elide the filename, keep some folder width, full path on hover.
5. Sol #4: the post-load checklist shortens compound names and one-to-three matched MM filenames
   without a tooltip (recovery exists only above three matches). Expose the full text whenever the
   displayed text is shortened.
6. Sol #10: the Peak window's Left offset, tR and Right offset show no unit (tooltips do; Add
   compound says minutes). Name minutes once, beside the group, not on each row.
7. Opus #3: a toast that refused an action ("Bio_001 is not Below threshold") stays on screen after
   the next action succeeds. A successful action replaces or clears a stale refusal.

Prove each at 2560 light and dark, then the laptop sizes (and 150% for the Settings items). Make
long-name test data under your scratch folder (long compound names, realistic acquisition
filenames that differ only near the end).
