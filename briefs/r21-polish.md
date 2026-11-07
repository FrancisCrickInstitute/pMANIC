# Iteration 19, group polish (round 16 finding)

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r18-linux.md` first and follow it (shared
rules, headless run, fences, report). Overrides: base commit `4f1b3999`, 773 tests at base, scratch
`/home/willyg/code/uiux-scratch/r21-polish/`, the round 16 reports are
`/home/willyg/code/pMANIC-notes/reviews/round-16/sol-review.md` and `opus-report.md`. Sol's probe:
`/home/willyg/code/uiux-scratch/review-r16-sol/popup_verified.py` and `popup_verified/`.

Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r21-polish`
(branch `uiux/r21-polish`, base `4f1b3999`; `testdata` linked).
Files you own: `src/manic/ui/chart_popup_dialog.py`, `chart_style.py` (only if sharing the rule
needs it), and their feature-named tests (`tests/test_chart_popups.py`, `tests/test_identity_chart.py`),
plus the one test named in item 2.

Round 16 averaged 9.95 (Opus 10.0, Sol 9.9). This is the last finding. Keep it minimal.

1. Sol #1: in the enlarged Identity popup (Alanine, hover Qualifier 1 of `Sample_04_ratio_fail`),
   the cell tooltip shows on entry but disappears when the pointer rests: Qt's resting
   `QEvent.ToolTip` request reaches the popup's viewport event filter
   (`chart_popup_dialog.py` ~763), which does not handle it, and the scene hides a tip none of its
   items own. A one-pixel move does not restore it; leaving and re-entering does. The Summary
   already handles this in `SummaryRows` (`chart_style.py` ~234). Apply the same ownership rule to
   the popup: while a cell (or a row) is under the pointer, the resting request keeps its tip;
   leave and close still hide. Reuse the Summary's rule rather than a second copy if that is the
   smaller change. Test with real mouse events (cell hover, then a rest with no further movement)
   and assert the tip text is still showing; it must fail on base.
2. Sol's note: a header-fold test passes only with the app stylesheet's font (it expects the grid
   header to fold at 520 px; with the default unstyled font the header is smaller). Find it (Sol's
   `header-results.json` under the probe folder names it) and make it independent of whether an
   earlier test applied the stylesheet, asserting the same user-visible result. Do not change app
   code for this.

Prove item 1 in light and dark with screenshots of the popup tip after a rest.
