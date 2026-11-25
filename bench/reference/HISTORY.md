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
## 2026-11-10, #284

The Qualifier QC sheet is laid out as a matrix like Raw Values, with one block of columns per compound. No number is computed differently.

**unlabelled**

| Sheet | Numbers | Changed | Typical change | Largest change | Other cells changed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw Values | 3200 | 0 |  |  |  |
| Abundances | 3200 | 0 |  |  |  |
| Qualifier QC | 17797 | 161 | 1e+02% | 1e+02% | 77155 |

## 2026-11-10, #297

Each compound on the Qualifier QC sheet gains an Outcome column (Pass, Partial, Fail, Not detected or No qualifiers). No number is computed differently.

**unlabelled**

| Sheet | Numbers | Changed | Typical change | Largest change | Other cells changed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw Values | 3200 | 0 |  |  |  |
| Abundances | 3200 | 0 |  |  |  |
| Qualifier QC | 17797 | 11636 | 1e+02% | 1e+02% | 14330 |

## 2026-11-10, #283

Samples where the internal standard has no signal or no known amount can no longer be calibrated, so their abundances are now left empty instead of reporting raw peak areas or zeros. Where the standard has no signal, the sample's peaks also fail validation.

**labelled**

| Sheet | Numbers | Changed | Typical change | Largest change | Other cells changed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Abundances | 2665 | 0 |  |  | 470 |

**unlabelled**

| Sheet | Numbers | Changed | Typical change | Largest change | Other cells changed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Abundances | 2903 | 0 |  |  | 297 |

## 2026-11-10, #313

Natural-isotope correction now runs once on the integrated isotopologue areas instead of on every scan, so noise in channels with no real label no longer adds false label; corrected values, ratios and abundances of labelled compounds move, most for small or empty peaks, while raw values, the internal standard and unlabelled exports do not.

**labelled**

| Sheet | Numbers | Changed | Typical change | Largest change | Other cells changed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Corrected Values | 14388 | 1076 | 15% | 1e+02% |  |
| Isotope Ratio | 14388 | 1456 | 5.5% | 1e+02% |  |
| % Label Incorporation | 3135 | 735 | 0.17% | 1e+02% |  |
| % Carbons Labelled | 3135 | 1027 | 0.2% | 1e+02% |  |
| Abundances | 2665 | 739 | 0.1% | 1e+02% | 1 |

The one other cell is Glycerol's Abundances unit, nmol to Relative: its MM-file peaks have no raw signal, and the old per-scan correction gave them a corrected area from noise alone, so an MRRF was computed from nothing. Unlabelled numbers did not change.

## 2026-11-25, #334

Every workbook gains a Notes sheet, placed last, that lists the analyst's sample notes; it is the header row alone when there are no notes, and no value on any other sheet changes.

**labelled**

| Sheet | Numbers | Changed | Typical change | Largest change | Other cells changed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Notes | 0 | 0 |  |  | 3 |

**unlabelled**

| Sheet | Numbers | Changed | Typical change | Largest change | Other cells changed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Notes | 0 | 0 |  |  | 3 |

## 2026-11-25, #299

Deconvolution now fits the same context that extraction guarantees (`max(0.20, max(loffset, roffset) + 0.10)` min, inclusive), so changing the displayed tR window no longer alters fitted areas. Labelled benchmark values do not change (default extracts are `0.20` min), though any real session with offsets `<= 0.15` min and a manually widened extract (`> 0.20` min) now fits `max(0.20, max(loffset, roffset) + 0.10)` min instead of `0.25` min. On the unlabelled benchmark, the 22 wide-offset compounds (`> 0.15` min) receive their full `0.10` min flank buffer (394 Raw Values changed, median 0.15%, with 19 cells moving by more than 5% including `U027`/`Bio_011` and `U071`/`Bio_028` moving from `0` to non-zero and `U071` shifts up to 75%, and 8 Qualifier QC outcome flips).

**unlabelled**

| Sheet | Numbers | Changed | Typical change | Largest change | Other cells changed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw Values | 3200 | 394 | 0.15% | 1e+02% |  |
| Abundances | 2903 | 164 | 1.2% | 1e+02% |  |
| Qualifier QC | 17799 | 1336 | 0.15% | 1e+02% | 10 |
