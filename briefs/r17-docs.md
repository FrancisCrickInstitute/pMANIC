# Iteration 15, group docs viewer

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r17-linux.md` first and follow it. Its
QtWebEngine rules bind you: never start a load on a visible QWebEngineView while another load may
still run; any change to the viewer's loading must pass 30 consecutive runs of
`tests/test_documentation_viewer.py` with no crash (report the count).

Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r17-docs`
(branch `uiux/r17-docs`, base `fd447a30`; `testdata` linked). Scratch: `/home/willyg/code/uiux-scratch/r17-docs/`.
Files you own: `src/manic/ui/documentation_viewer.py` and `tests/test_documentation_viewer.py`.

Finding (both reviewers, round 12: Sol #1, Opus #3): on the CI macOS runner in dark mode the first
documentation page (Quick Start) is a blank frame with no content, progress or retry
(`/home/willyg/code/pMANIC-notes/reviews/round-12/shots/ci-macos-15-dark/17_documentation__DocumentationViewer.png`;
the light run and Linux render it). Two earlier first-paint fixes crashed QtWebEngine and were
reverted: read `git show b804ecf` and `git log -S` history of `documentation_viewer.py` to learn
what failed before you design. Goal: the first page never shows as a blank frame; keep the loading
state until the article has actually painted visible content (for example confirm through
`runJavaScript` after load that the body has rendered text and a frame has passed), with a bounded
recovery (retry once, then the existing "failed to render" message with its Retry). No new load on
a visible view while one runs.

You cannot run macOS here. Make the change obviously safe, prove it on Linux (tour
`17_documentation__DocumentationViewer*.png` in light and dark, 30 clean test runs, a test that
asserts the user-visible state while the page is not yet painted), and describe in your report
exactly what to look for in the CI macOS dark shot after merge. If you conclude the fix cannot be
made safely, say so with evidence instead of shipping a risky change.
