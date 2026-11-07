# Cleanup pass before the PR (the hill climb reached 10.0 / 10.0 in round 20)

Read `/home/willyg/code/pMANIC-notes/briefs/impl-common-r18-linux.md` first and follow it (shared
rules, headless run, fences, report). Overrides: base commit `ece68c12`, 814 passed + 8 skipped at
base, scratch `/home/willyg/code/uiux-scratch/r25-cleanup/`. Round 20 reports:
`/home/willyg/code/pMANIC-notes/reviews/round-20/opus-report.md` and `sol-review.md`.

Worktree (your only writable place): `/home/willyg/code/pMANIC/.claude/worktrees/r25-cleanup`
(branch `uiux/r25-cleanup`, base `ece68c12`; `testdata` linked). You may edit any file under
`src/manic/ui/`, `src/manic/resources/`, `scripts/ui_tour.py`, `.github/workflows/ui-tour.yml`,
`docs/` and `tests/`. Science fence as always.

Both reviewers rate the app 10/10. Change NOTHING a user would see, except item 1's fix. Every item
must leave the tours pixel-identical at 2560 light and dark (compare against
`/home/willyg/code/uiux-scratch/m22/light-2560` and `dark-2560`; a toast caught at a different moment
is the only acceptable difference).

1. Opus round 20 #1 (hardening): `BarRows._show_at(None)` (`chart_style.py` ~252) calls the global
   `QToolTip.hideText()` whenever its own `_showing` is set, so a chart whose bookkeeping went stale
   can hide another chart's fresh tip. Hide only a tip this chart owns (e.g. the visible tooltip text
   equals `_showing`). Test: two charts; the second raises a tip by `refresh()` under a placed cursor,
   the cursor moves to the first, data changes on both; the first chart's tip stays.
2. `.github/workflows/ui-tour.yml`: remove the temporary `push` trigger and its comment (keep
   `pull_request` with its paths and `workflow_dispatch`). The PR will run it.
3. Dead code from the overhaul. The docs headings no longer carry "Reference: "/"Workflow: "
   prefixes, so the prefix stripping in `documentation_viewer.py` (~234) and its prefixed test
   fixtures are dead: remove them (this is not a loading change; still run
   `tests/test_documentation_viewer.py` and report it). Then sweep `src/manic/ui` and
   `scripts/ui_tour.py` for code the overhaul left unused (functions, methods, constants, imports,
   tokens in `theme.py`/`style.qss` nothing references): use `uvx vulture` and `uvx ruff check
   --select F401,F841` on the files changed versus `origin/main`, confirm each candidate by grep
   (Qt slots, signal names, stylesheet object names and tour attributes are used indirectly), and
   delete what is truly dead. List what you removed and what you kept with the reason.
4. Comments: run the no-comments discipline over the files changed versus `origin/main` in
   `src/manic/ui`: delete comments that narrate what the code does, restate a name, or refer to
   review rounds, findings, reviewers or past states ("now", "no longer", "used to"); keep only a
   non-obvious why. Do not touch code behaviour.
5. Tests: list the 10 slowest (`--durations=10`). For any that is slow because of its setup rather
   than what it protects, make it cheaper without weakening what it asserts. Remove tests that only
   restate implementation or duplicate another test (the user's directive). Report before/after
   suite time.

Run the full suite and the five tours before you report; commit in units of one concern each.
