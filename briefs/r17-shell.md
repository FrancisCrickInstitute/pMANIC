# Iteration 15, group shell

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r17-linux.md` first and follow it.
Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r17-shell`
(branch `uiux/r17-shell`, base `fd447a30`; `testdata` linked). Scratch: `/home/willyg/code/uiux-scratch/r17-shell/`.

Files you own: `src/manic/ui/main_window.py`, `settings_window.py`, `standard_chooser.py`,
`recovery_dialog.py`, `left_toolbar.py`, `sidebar_widgets.py`, `compound_list_widget.py`,
`sample_list_widget.py`, `docs/**`, and their feature-named tests (`tests/test_main_window_shell.py`,
`tests/test_sidebar.py`, `tests/test_settings_window.py`, ...). Others own the charts files and
`documentation_viewer.py`.

Findings (round 12; reproduce each first):
1. Opus #1: the quit prompt says "Use File > Export Method..." but the menu item is
   "Export Session..." (`main_window.py` ~1139). Name the real command, and make the sentence short.
2. Opus #2 / Sol #2: the Summary keeps its launch width and the three-column check budgets minimum
   panel widths, not the ones the layout will use. Launched at 2560 then narrowed to 1500 or 1280,
   the grid gets 812 / 592 px (3 or 2 scrolling columns) while a fresh launch at the same size fits
   more. Decide from the widths the splitter will actually give, and when the window narrows, give
   the grid its room back (shrink the Summary toward its minimum before it closes). A user-dragged
   Summary width is remembered but must not starve the grid. Prove with resize sequences
   2560 -> 1500 -> 1280 -> 2560 against fresh launches at each size.
3. Opus #5: Review shortcut A on a plot that is not Below threshold (and B where it cannot act)
   does nothing and says nothing, while N says "No flagged plots". Give the same kind of brief
   feedback (`main_window.py` ~675).
4. Opus #8: Settings › Save gives no confirmation beyond the dot clearing. Add a quiet, transient
   confirmation that fits the design (no new clutter that stays on screen).
5. Sol #8: short Settings pages inherit the tallest page's height. Size the dialog to its
   navigation and current page; pages that need more room grow as they do now. Keep one page per
   topic (settled).
6. Sol #3 and #5: the internal-standard chooser and the recovery lists still cut long names at the
   end, scroll horizontally and have no full-name tooltip. Middle elision, full-name tooltips,
   vertical scrolling only, like the sidebar lists. Keep multi-selection in recovery.
7. Sol #4: `docs/Reference_Peak_Validation.md` says "No badge: The peak is healthy", but with no
   internal standard no peak is assessed. Say what the absence of a badge means accurately.
8. Sol #11: article headings repeat their navigation category ("Reference: ...", "Workflow: ...").
   Keep the specific titles; drop the repeated prefix (check the viewer's navigation still groups
   and names them right; the docs index is built from the files, see `documentation_index`).
9. Sol #12: Quick Start's export step recites the dialog. Shorten it to the task; detail stays in
   the User Guide.

Prove each at 2560 light and dark, then the laptop sizes.
