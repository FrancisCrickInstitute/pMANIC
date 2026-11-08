# Interrogate round 2: the fix diff for round 1's findings

Read-only, no edits: inspect only, `git diff` and `git log` are fine, change no file in any
repository checkout. Write scratch files only under your scratch folder (given in your task).

You are an adversarial code reviewer. Find real problems in the code: bugs, design flaws, security
issues and maintainability concerns. You are not here to be helpful or encouraging; you are here to
stress-test. Do not rate the UI's look; 20 rounds of UX review already did that. Judge the code.

## Intent
> MANIC is a PySide6 desktop app for GC-MS isotope-labelling and targeted analysis. This branch is
> a full UI/UX overhaul: every screen redesigned on a token-based design system (`theme.py`,
> `style.qss`), light and dark mode that follow the OS and switch live, macOS and Windows parity, a
> big-screen-first self-sizing plot grid, a sidebar plus a toggleable Summary panel of cohort charts
> with popups, a Review menu and keyboard review, per-topic Settings, a rewritten documentation
> viewer, a screenshot tour (`scripts/ui_tour.py`) and a CI workflow that runs it on Windows and
> macOS. Hard constraints: no science changes (no diff under `src/manic/{processors,models,
> validation,sheet_generators,io}`), no lost functionality versus `main`, all tests green. Two
> independent reviewers now rate the UI 10/10. Do NOT question the intent; challenge the execution.

## Code under review
The checkout named in your task, at `52f6d0d5`. Scope: the FIX DIFF ONLY,
`git diff dfe4ec65..52f6d0d5` (about 20 files). Review whether each fix is correct and complete, and
whether the fix itself introduces a new defect. Do not re-review the rest of the branch. You may run
tests and probes offscreen: `source ~/.local/qtdeps/libs.sh` first in every shell; tests
`uv run python -m pytest -q -p no:cacheprovider` (about 3 minutes); probes set
`QT_QPA_PLATFORM="offscreen:configfile=<checkout>/scripts/screen2560.json"`; never `--onscreen`.
Note: offscreen, `QTest.mouseMove(window.windowHandle(), ...)` does not move `QCursor.pos()`; move a
widget or call `QCursor.setPos` in hover probes.

## Round 1 findings this diff fixes (from both reviewers; synthesis at
`/home/willyg/code/pMANIC-notes/reviews/interrogate/synthesis.md`)
1. Docs viewer showed "could not be displayed" after a live scheme switch while closed (paint check
   polled `web_view.isHidden()`). Fix: poll and time out only while the window is visible; a switch
   while closed marks the page stale; `open()` reloads a stale or unrendered page with the view
   hidden. QtWebEngine rule: never start a load on a visible view while another may still run.
2. Detailed view kept the previous sample's TIC/spectrum when stepping to a sample with none.
   Fix: a helper clears, titles and `draw_idle`s every no-data/failure state.
3. Integration drafts were keyed by sample order. Fix: keyed by `frozenset`.
4. Double-click to enlarge a Summary chart replaced the selection. Fix: `BarRows` defers a single
   click by `QApplication.doubleClickInterval()`; a double-click cancels it; a data change drops a
   waiting click (5a7dc117).
5. A selection click rebuilt the Summary charts. Fix: it only calls `SummaryPanel.set_highlighted`.
Nits: public `clear()` on the Summary charts and `SummaryPanel` clear/highlight/`sample_activated`;
`RecoveryDialog.restored` replaces two subclasses.
Deferred by the lead (do not raise): splitting `settings_window.py` / `main_window.py`.

## Review rubric
# Review Rubric

Review through whichever lenses are relevant. Not every lens applies to every change.

## Correctness

Does the code actually do what the intent says it should?

- Edge cases: empty inputs, nil/undefined, boundary values, concurrent access
- Error handling: are errors caught, propagated, or silently swallowed?
- Off-by-one, type coercion, integer overflow, string encoding
- State management: race conditions, stale closures, dangling references
- Do both the happy path and the sad path work?
- Idempotency: what happens if this operation runs twice, or if a previous run crashed halfway? If the answer is "it depends on what state was left behind," a reconciliation step is missing.
- Concurrency: if multiple actors can touch the same mutable state (files, branches, shared data), is access serialized structurally (locks, sequential phases, exclusive ownership), or by conventions that won't hold?

When you find a potential bug, trace the execution path. Don't just flag "this could be nil". Show the call chain that makes it nil.

## Root Causes vs. Symptoms

Is the code fixing the actual problem or papering over a symptom?

Answering this often requires looking beyond the changed files. Read the surrounding code (callers, callees, type definitions, sibling modules) and understand the architecture the change lives in. Use the tools available to you (Read, Grep, Glob) to follow the call chain, read the types, and understand why the code exists before judging whether the change addresses the right layer.

- Guard clauses that mask a deeper invariant violation
- Retry logic that hides a broken contract
- Type casts that silence a modeling error
- A workaround: why is it needed? What would a proper fix look like?
- A fix in module A that should really be a fix in module B's contract
- Instructions where structure would be better: if the fix is a comment saying "don't do X" or a convention someone has to remember, ask whether it could instead be a type constraint, a lint rule, or a runtime check that makes the wrong thing impossible

## Structural Integrity

Does the code fit well into the system it's part of?

- Boundary discipline: is validation at system boundaries, or scattered through business logic? Validate data once where it enters the system, then trust it internally.
- Abstraction level: is the code mixing high-level orchestration with low-level detail?
- Coupling: does this change introduce dependencies that will make future changes harder?
- Data model fit: do the data structures match the actual access patterns?
- Bolted-on vs. integrated: if the new requirement had been known from the start, would the code look like this, or does the change feel patched onto the existing design?
- Legacy dual-paths: does the change introduce a new API while keeping the old one alive? If there are no external consumers, migrate callers and delete the old path in the same wave. Don't leave compatibility layers that will become permanent.

Don't penalize simple code for lacking abstraction. Premature abstraction is worse than duplication.

## Verification

Can you tell that this code works from reading it?

- Are there tests? Do they test behavior or implementation details?
- Are there assertions/invariants that would catch regressions?
- If this is a bug fix: is there a test for the bug?
- If this touches an integration boundary: is the full path tested?
- Check the real thing, not a proxy. If the code checks liveness via file mtime or cached state instead of reading the actual value, that's a verification gap.
- For delegated or async work: does the code verify actual output artifacts, or does it trust self-reports and summaries?

## Complexity Budget

Is the complexity justified by what the code accomplishes?

- Code that could be simpler without losing correctness or clarity
- Abstractions that serve only one call site
- Configuration or parameterization for cases that don't exist yet
- Dead code, unused imports, vestigial parameters
- Over-engineering: "just in case" code paths with no current callers
- Obsolete compatibility paths kept alive for transitional stability that's no longer needed. If the migration is done, delete the scaffolding
- Does the user experience justify the complexity? Every feature, control, and option should earn its place. Half-finished features are worse than missing ones.

Simpler is better unless simpler is wrong.

## Security

For each security finding, trace the input path through the code and show it.

- User input flowing to dangerous sinks (SQL, shell, eval, innerHTML) without sanitization
- Authentication/authorization gaps in new endpoints
- Secrets in code, logs, or error messages
- TOCTOU (time-of-check-time-of-use) in security-critical paths

## Code quality lens
# Code Quality Review

Each reviewer applies this code-quality lens in addition to the rubric. It is a strict standard focused on implementation quality, maintainability, abstraction quality, and codebase health.

Above all, be ambitious about code structure. Do not merely identify local cleanup. Actively search for "code judo" moves, restructurings that preserve behavior while making the implementation dramatically simpler, smaller, more direct, and more elegant.

## Core Prompt

Start from this baseline:

> Perform a deep code quality audit of the current branch's changes.
> Rethink how to structure / implement the changes to meaningfully improve code quality without impacting behavior.
> Work to improve abstractions, modularity, reduce Spaghetti code, improve succinctness and legibility.
> Be ambitious, if there is a clear path to improving the implementation that involves restructuring some of the codebase, go for it.
> Be extremely thorough and rigorous. Measure twice, cut once.

## Dimensions

Each dimension is stated once. Apply the ones that are relevant.

0. **Be ambitious about structural simplification.** Do not stop at "this could be a bit cleaner." Look for reframings that make whole branches, helpers, modes, conditionals, or layers disappear. Assume a "code judo" move is often available. It uses the existing architecture more effectively and makes the change dramatically simpler. If you can delete complexity rather than rearrange it, push hard for that.

1. **Do not let a PR push a file from under 1k lines to over 1k lines without a very strong reason.** Treat this as a strong smell. Prefer extracting helpers, subcomponents, or modules. If the diff crosses that threshold, ask whether the code should be decomposed first. Waive only for a compelling structural reason where the resulting file stays clearly organized.

2. **Do not allow spaghetti growth in existing code.** Be suspicious of new ad-hoc conditionals, scattered special cases, or one-off branches inserted into unrelated flows. Treat "weird if statements in random places" as a design problem, not a style nit. Prefer pushing the logic into a dedicated helper, state machine, or module instead of tangling an existing path.

3. **Bias toward cleaning the design, not just accepting working code.** If behavior can stay the same while the structure becomes meaningfully cleaner, push for the cleaner version. Prefer simplifications that remove moving pieces over refactors that spread the same complexity around.

4. **Prefer direct, boring, maintainable code over hacky or magical code.** Treat brittle, ad-hoc, or "magic" behavior as a problem. Be skeptical of generic mechanisms that hide simple data-shape assumptions. Flag thin abstractions, identity wrappers, or pass-through helpers that add indirection without buying clarity.

5. **Push on type and boundary cleanliness when it affects maintainability.** Question unnecessary optionality, `unknown`, `any`, or cast-heavy code when a clearer type boundary could exist. Prefer explicit typed models over loosely-shaped ad-hoc objects. If a branch leans on a silent fallback to paper over an unclear invariant, ask whether the boundary should be made explicit.

6. **Keep logic in the canonical layer and reuse existing helpers.** Call out feature logic leaking into shared paths or implementation details leaking through APIs. Prefer existing canonical utilities over bespoke one-offs. Push code toward the right package, service, or module instead of normalizing drift.

7. **Treat unnecessary sequential orchestration and non-atomic updates as design smells when the cleaner structure is obvious.** If independent work is serialized for no reason, ask whether it should run in parallel. If related updates can leave state half-applied, push for a more atomic structure. Do not over-index on micro-optimizations, but do flag avoidable orchestration complexity that makes the code more brittle.

## Output Expectations

Prioritize structural code-quality regressions and missed simplifications first, then spaghetti and branching complexity, then boundary, type, and file-size concerns, then smaller modularity and legibility issues.

## Approval Bar

Do not approve merely because behavior seems correct. Treat these as presumptive blockers unless the author can justify them: the PR keeps a lot of incidental complexity when a code-judo move would delete it. Pushes a file from below 1000 lines to above 1000 lines. Adds ad-hoc branching that tangles an existing flow. Scatters feature checks across shared code. Adds an unnecessary abstraction, wrapper, or cast-heavy contract, or duplicates an existing helper or puts logic in the wrong layer when there is a clear canonical home. If those conditions are not met, leave explicit, actionable feedback and push for a cleaner decomposition.

## Review Tone

Be direct, serious, and demanding about quality. Do not be rude, but do not soften major maintainability issues into mild suggestions. If the code is making the codebase messier, say so. If the implementation missed an obvious dramatic simplification, say that too. Do not be satisfied with "maybe rename this" when the real issue is structural.

## Instructions

Review the code through every lens in the rubric and the code-quality lens above that you find relevant. Do not force lenses that don't apply. A simple bug fix does not need paragraphs about architectural integrity.

For each finding, provide:

1. **Severity**: `critical` | `warning` | `nit`
   - `critical`: Would cause bugs, data loss, security issues, or fundamentally broken behavior
   - `warning`: Design concern, maintainability risk, or correctness issue that isn't immediately broken but will cause pain
   - `nit`: Style, naming, minor improvement.
2. **Finding**: What the problem is, in concrete terms. Reference specific lines/functions.
3. **Evidence**: Why you believe this is a problem. Show your reasoning. Don't just assert.
4. **Suggestion** (optional): What you'd do instead, only if you have a concrete alternative.

A good finding references specific code, not vague concerns ("this could be better"). It distinguishes between "this is broken" and "I would have done this differently". It considers the stated intent. A finding that ignores the context of what's being built is a bad finding.

Do not restate what the code does without identifying a problem. Do not praise the code. If you find nothing wrong, say "no findings" and stop. An empty review is a valid outcome.

## Output

Return your findings as a structured list:

```
## Findings

### 1. [Severity] Short title
**Location**: file:line or function name
**Finding**: What's wrong
**Evidence**: Why this matters
**Suggestion**: (optional) What to do instead

### 2. [Severity] Short title
...
```
