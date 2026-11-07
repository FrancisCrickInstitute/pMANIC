# Interrogate synthesis (round 1), origin/main...dfe4ec65

Reviewers: A = codex/gpt-6.1-sol (xhigh), 2 findings; B = claudeAgent/claude-opus-5-5 (high), 6 findings.
All Act-on items are introduced by this branch (sample stepping and integration drafts do not exist on main).

## Act on
1. (B critical) Docs viewer reports "could not be displayed" after a live scheme switch while closed:
   the paint check polls `web_view.isHidden()`, which stays false when the window closes; the reload
   on theme change then times out twice and shows the error with Retry; `open()` does not reload.
2. (A critical) Detailed view: stepping to a sample with no TIC / no spectrum leaves the previous
   sample's TIC and spectrum on screen under the new name (no redraw after the no-data branch).
3. (A critical) An unapplied integration draft is keyed by sample order; re-selecting the same set in
   another order (e.g. Ctrl+A after clicking each plot) hides the draft and shows the stored value.
4. (B warning) Double-click to enlarge a Summary chart first replaces the grid's multi-selection (the
   first click's release selects the row).
5. (B warning) A selection click rebuilds the Summary charts (re-reads EICs, recomputes areas, ~165 ms)
   where only `set_highlighted` is needed (0.1 ms); the comment claims the opposite.
Batched nits: (B #6) public `clear()`/highlight on the Summary charts instead of private `_clear_chart`;
(B #5) recovery dialog subclasses that only rename a signal.

## Consider (deferred to a follow-up PR)
- (B warning) split `settings_window.py` pages and extract a panel-layout object from `main_window.py`:
  sound, but a large structural refactor at 10/10 immediately before the PR.

## Dismissed
- none.

## Agreement map
No finding was raised by both; the two models covered different ground (A: data/state correctness in
the detailed view and drafts; B: lifecycle, interaction and structure). Each Act-on item was reproduced
by its reviewer with a probe on the real app, so single-model provenance does not lower its weight.
