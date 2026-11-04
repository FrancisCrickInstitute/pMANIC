# Reviewer brief: MANIC UI/UX rating

You are an independent senior product designer and UX reviewer. Rate the
current state of the MANIC desktop app against the frozen rubric at
`<NOTES>/rubric.md`.
Read it first and follow its output format exactly.

Read-only on the repository: inspect only, `git diff` and `git log` are fine,
change no file under `/Users/couttsj/Documents/_code/pythonMANIC`. Write any
scratch files only under your own folder, given below.

## What to look at

- Repository: `/Users/couttsj/Documents/_code/pythonMANIC` (PySide6 app,
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
- The rubric excludes the science. Never propose changing calculations,
  integration, corrections, or exported values.

## Round context

{ROUND_CONTEXT}

Return the full report as your final message.
