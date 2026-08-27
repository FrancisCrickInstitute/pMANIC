# Unlabelled toolbar charts

In an unlabelled session the left toolbar shows Identity above Total Abundance. The isotopologue ratio chart stays hidden.

## Sub-features

- `unlabelled-identity` shows `targetedQc`.
- `unlabelled-abundance` shows `totalAbundanceWidget` under Identity.
- `unlabelled-ratios-hidden` keeps `isotopologueRatioWidget` hidden.

## How to get to it (user POV)

- Choose `Unlabelled targeted analysis` at startup.
- Load a targeted compound list and CDF files, then select a compound. Identity and Total Abundance sit in the left toolbar.

## Driving it with verify-pmanic

Preconditions:

- Doctor is green.
- `QT_QPA_PLATFORM=offscreen`.

- **Build toolbar.** Run `PYTHONPATH=src .venv/bin/python .cursor/skills/verify-pmanic/scripts/verify_pmanic.py drive toolbar-unlabelled --out artifacts/verify-pmanic/toolbar-unlabelled`.
- **Check stack.** `toolbar-unlabelled.json` has `"ok": true`. `targetedQc.hidden` is false. `totalAbundanceWidget.hidden` is false. `isotopologueRatioWidget.hidden` is true. `targetedQc.index` is less than `totalAbundanceWidget.index`.
- **Proof.** Keep the JSON and `toolbar-unlabelled.png`.

## Gotchas

- If `totalAbundanceWidget.hidden` is true, the unlabelled abundance chart is missing. That is a failed proof.
- Identity can refresh against the selected sample. Abundance uses every current sample. Do not require those sets to match.
- Bar values are Q-ion area. A screenshot does not prove that. Use the pytest named in [load-compounds](./load-compounds.md) for numbers.
