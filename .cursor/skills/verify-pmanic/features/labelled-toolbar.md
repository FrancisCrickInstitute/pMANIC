# Labelled toolbar charts

In a labelled session the left toolbar shows Label Incorporation above Total Abundance. Identity stays hidden.

## Sub-features

- `labelled-ratios` shows `isotopologueRatioWidget`.
- `labelled-abundance` shows `totalAbundanceWidget` under the ratio chart.
- `labelled-identity-hidden` keeps `targetedQc` hidden.

## How to get to it (user POV)

- Choose `Labelled isotope-tracing analysis` at startup.
- Load compounds and CDF files, then select a compound. The two charts fill in the left toolbar.

## Driving it with verify-pmanic

Preconditions:

- Doctor is green.
- `QT_QPA_PLATFORM=offscreen`.

- **Build toolbar.** Run `PYTHONPATH=src .venv/bin/python .cursor/skills/verify-pmanic/scripts/verify_pmanic.py drive toolbar-labelled --out artifacts/verify-pmanic/toolbar-labelled`.
- **Check stack.** `toolbar-labelled.json` has `"ok": true`. `isotopologueRatioWidget.hidden` is false. `totalAbundanceWidget.hidden` is false. `targetedQc.hidden` is true. `isotopologueRatioWidget.index` is less than `totalAbundanceWidget.index`.
- **Proof.** Keep the JSON and `toolbar-labelled.png`. The grab is the left toolbar, not the graph grid.

## Gotchas

- Empty charts still prove visibility and order. Filled bars need loaded EICs, which this harness does not import.
- Do not treat a labelled toolbar as proof of unlabelled layout.
