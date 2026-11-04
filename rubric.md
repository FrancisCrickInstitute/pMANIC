# MANIC UI/UX review rubric (frozen)

MANIC is a PySide6 desktop app for GC-MS isotope-labelling and targeted
analysis, used by bench scientists on macOS and Windows laptops. The goal: an
app that is beautiful, easy to use, flexible, and does not feel like typical
clunky science software. The science (integration, corrections, exports) is
out of scope for this review and must never be proposed for change.

Score each factor 1 to 10. Use the anchors. Be strict and calibrated: a 10 is
best-in-class commercial software (Linear, Figma, Apple Pro apps); a 5 is a
typical functional in-house science tool; a 3 is visibly unpolished.

| # | Factor | What to judge |
|---|--------|---------------|
| F1 | Visual design | Typography, colour palette, spacing rhythm, alignment, visual noise. Does it look beautiful? |
| F2 | Layout and hierarchy | Use of space, grouping, what draws the eye first, density appropriate to the task, sidebar organisation. |
| F3 | Onboarding and workflow clarity | Empty states, first-run guidance, obvious next step, labels a new user understands, discoverability of features. |
| F4 | Consistency and polish | Same components look and behave the same across main window and dialogs; icons, buttons, headings, margins, window titles. |
| F5 | Feedback and state | Selection, loading/progress, QC verdicts, errors, status bar, what is active, toasts. |
| F6 | Efficiency and flexibility | Resizing and small screens, keyboard paths, density control, power-user shortcuts, sensible defaults. |
| F7 | Data visualisation | Chart legibility, axes and tick labels, legends, colour meaning, selection highlight, popups and detailed view. |
| F8 | Modern feel | Overall gestalt: does it feel like modern, considered software rather than clunky science software? |
| F9 | Taste (not AI slop) | How much does it look like generic AI-generated UI? 10 shows real taste: deliberate, somewhat distinctive, made for this app and these users, nothing generic. See the F9 anchors below. |

Platforms and appearance (added after round 0 at the user's request): the
app must look and work equally well on macOS and Windows, in light and dark
mode. When screenshots exist for Windows or dark mode, judge every factor
across all of them: a factor scores what the weakest platform/appearance
delivers, not the best. A broken or unreadable dark mode or Windows layout
caps F1, F4 and F8 at 5.

## F9 anchors (added after round 3 at the user's request; important)

Judge every screen, dialog, empty state, and every piece of UI copy.

- 10: real taste. Every element earns its place; the app has a recognisable
  character suited to bench scientists doing GC-MS review; copy is short and
  specific; a designer would not guess it came from a template.
- 7: considered and clean, with a few generic patterns left.
- 5: competent but template-like; could be any SaaS app.
- 3: obvious AI-generated look.

Tells that pull the score down (cite each one you find, with the screenshot
and `file:line`):
- Template layouts: hero heading plus numbered stepper card plus helper
  paragraphs plus a row of links; symmetrical card grids with an icon, title
  and blurb each; decorative badges, pills or chips that carry no information.
- The same status or instruction shown in two or three places at once.
- Wordy copy: explaining what the UI already shows, "You can also…",
  "Simply…", "Let's get started", restating labels in helper text,
  paragraphs where a label would do, marketing tone in a lab tool.
- Generic decoration: gradients, glows, emoji, ornamental icons, rounded
  everything, accent colour used for decoration instead of meaning.
- Uniform sameness: every surface the same card, the same grey helper text,
  no hierarchy chosen for this task.

Overall = mean of F1..F9, one decimal.

## Required output

1. A short verdict paragraph.
2. A table of F1..F9 with score and one-line justification citing screenshot
   filenames (and `file:line` where you read code).
3. The top 12 issues ranked by user impact. For each: what is wrong, where
   (screenshot name and `file:line`), a concrete fix, and expected factor gain.
4. If this is a re-rating round: what improved, what regressed, and anything
   that was lost (a feature, control, or path that existed before but is now
   missing or harder to reach). Losing useful functionality is a severe issue.
5. End with exactly one fenced JSON block:
   ```json
   {"F1": n, "F2": n, "F3": n, "F4": n, "F5": n, "F6": n, "F7": n, "F8": n, "F9": n, "overall": n}
   ```
