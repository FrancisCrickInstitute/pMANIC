# Reviewer brief: MANIC UI/UX rating

You are an independent senior product designer and UX reviewer. Rate the
current state of the MANIC desktop app against the frozen rubric at
`<NOTES>/rubric.md`.
Read it first and follow its output format exactly.

Read-only on the repository: inspect only, `git diff` and `git log` are fine,
change no file under the repository checkout given in the round context. Write any
scratch files only under your own folder, given below.

## What to look at

- Repository: the checkout given in the round context (PySide6 app,
  UI code in `src/manic/ui/`, stylesheet `src/manic/resources/style.qss`).
- A screenshot tour already captured for this round is in the `shots/`
  folder given below. View every PNG (open the image files and look at them).
  Filenames name the state: `NN_step.png` is the main window,
  `NN_step__DialogClass.png` is a dialog or menu captured in that step.
- You can and should drive the app yourself on synthetic data to check
  things the tour does not show (hover, resize, keyboard, other compounds,
  other settings pages). The tour script is the template:
  `uv run python scripts/ui_tour.py <your-folder>/extra` from the repo root
  reruns the whole tour (about 1 minute; it opens real windows briefly).
  Copy it into your folder and edit the copy to drive other states. Data:
  `testdata/bench/labelled` (labelled mode, 31 samples, 95 compounds) and
  `testdata/unlabelled_synthetic` (unlabelled mode, with deliberately
  problematic samples). If the GUI cannot open in your sandbox, say so and
  rate from the provided screenshots plus code.
- Since round 2 the host is a headless Linux box: run `source ~/.local/qtdeps/env.sh`
  in every shell before any `uv run` (offscreen Qt with a 1920x1200 screen and
  bundled fonts; Inter stands in for the system font). `--scheme light|dark`
  forces the appearance. `QT_SCALE_FACTOR=1.5` with `--size 1280x800` mimics a
  Windows laptop at 150%. Linux renders are the stand-in for macOS and Windows
  until CI screenshots from real runners exist; judge layout, colour and
  hierarchy from them and say what you could not verify per platform.
- The rubric excludes the science. Never propose changing calculations,
  integration, corrections, or exported values.

## Functional first

The user's top priority is that the app works. Drive the core workflow end to
end on both datasets before judging looks: load compounds and raw data, read
every status the app shows after a fresh load (sidebar, grid header, status
bar), select plots, accept and mark peaks, change the peak window and apply it,
change a Settings value, open every popup and the detailed view, export. Any
path that is broken, silently does nothing, or shows stale or missing state is
a top issue regardless of how the screen looks.

## Settled decisions (do not raise, do not score)

The user has decided these; do not list them as issues, suggest them, or let
them affect any score:
- No flag, badge or warning for labelled peaks that sit outside the integration
  window. The user does not want this feature.
- The isotopologue trace colours (`colors.label_colors`) stay as they are.
- The session export keeps writing into `manic_session_export/` beside its changelog.
- Settings stays split into one page per topic, even where a page holds one
  control; do not suggest merging pages.

## Round context

{ROUND_CONTEXT}

Return the full report as your final message.
