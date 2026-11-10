# History of the exported results

Each entry is one pull request that changed a number MANIC exports. The numbers are the
full Excel export of the two synthetic bench datasets, kept in `labelled.tsv` and
`unlabelled.tsv` beside this file. `bench/reference.py update` writes the entries; see
`bench/README.md`.

"Changed" counts numbers that moved by more than 0.05%. "Typical" is the
median relative change among those, and "Largest" the biggest.

## 2026-11-10, #275

Reference created from `main` at `ce85f108`. It already includes the result changes of
#211 (Legacy integration honours deconvolution for multi-ion compounds), #230 (Auto fit
tries every shape on a single peak), #231 (the unlabelled retention-time check can fail)
and #233 (the EMG tail is no longer clipped), which merged the same day and were not
measured against a reference.

| Dataset | Sheets | Numbers |
| --- | --- | ---: |
| labelled | Raw Values, Corrected Values, Isotope Ratio, % Label Incorporation, % Carbons Labelled, Abundances | 52,569 |
| unlabelled | Raw Values, Abundances, Qualifier QC | 45,082 |

## 2026-11-10, #283

Samples where the internal standard has no signal or no known amount can no longer be calibrated, so their abundances are now left empty instead of reporting raw peak areas or zeros, and their peaks are flagged as failing validation.

**labelled**

| Sheet | Numbers | Changed | Typical change | Largest change | Other cells changed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Abundances | 2665 | 0 |  |  | 470 |

**unlabelled**

| Sheet | Numbers | Changed | Typical change | Largest change | Other cells changed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Abundances | 2903 | 0 |  |  | 297 |
