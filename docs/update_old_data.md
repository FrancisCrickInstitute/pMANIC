## Update Old Data (Approximate Mode)

This tool rebuilds a MANIC Excel export from two external inputs without reading the internal database:

- Compounds list (Excel/CSV): same columns as the normal importer
- Raw Values workbook (Excel): identical structure to MANIC’s Raw Values sheet

It generates all five sheets (Raw Values, Corrected Values, Isotope Ratios, % Label Incorporation, Abundances) and is intended for legacy or partial datasets.

### How It Differs From The Normal Export

The standard Export Data uses per‑timepoint EIC data from the database:
- Corrects natural isotope abundance at each timepoint
- Applies non‑negativity constraints per timepoint and may use constrained optimization for ill‑conditioned cases
- Integrates the corrected time series to obtain totals

Update Old Data operates on integrated totals from the Raw Values sheet:
- Computes “Corrected Values” from the integrated isotopologue areas using the direct linear solve when suitable
- Falls back to a constrained optimizer only when the correction matrix is ill‑conditioned
- Because per‑timepoint constraints are not applied, “correct the sum” may differ from “sum of per‑timepoint corrections”

As a result, small upstream differences can appear and may be amplified in downstream quantities (especially Abundances via MRRF).

### MRRF and Abundances In Approximate Mode

- MRRF uses the same MATLAB‑compatible convention:
  - Numerator: mean corrected signal for each metabolite over its own MM sample set (from that compound’s `mmfiles`)
  - Denominator: mean corrected signal for the internal standard over its own MM sample set (from the ISTD’s `mmfiles`)
  - Concentrations come from `amount_in_std_mix` (for both metabolite and ISTD)
- Update Old Data resolves MM samples only from the Raw Values workbook sample names using case‑insensitive substring matching of `mmfiles` tokens.
- If the workbook does not contain the required MM samples or concentrations are missing, MRRF may fall back to 1.0, which changes Abundances.

### When To Use Each

- Use Export Data (normal) when you want exact reproducibility based on the stored EICs and per‑timepoint corrections.
- Use Update Old Data when you only have a compounds list and a Raw Values export and need a best‑effort rebuild of downstream sheets.

### Practical Tips

- Ensure the Raw Values workbook includes the MM samples referenced in `mmfiles` and that names match the tokens.
- Ensure the compounds file includes `amount_in_std_mix` for the internal standard and each metabolite, and `int_std_amount` for the internal standard.
- Expect minor differences in Corrected Values and derived quantities; larger differences typically trace back to missing/unequal MM coverage or concentrations.

### Why Corrected Totals Can Be Zero

In approximate mode, correction is applied to the integrated isotopologue vector (the totals from Raw Values), not to each timepoint. If that integrated vector is well explained by natural abundance under the chemistry model (or the system is ill‑conditioned), the best non‑negative corrected vector can legitimately be near zero. This differs from the normal export, where some timepoints may carry labeling and survive per‑timepoint constraints; integrating those timepoints stays non‑zero.

Zeros in Update Old Data therefore do not necessarily indicate an error — they reflect the limitation of correcting integrated vectors. If zeros occur unexpectedly, verify formula/label metadata in the compounds file and that isotopologue columns match `label_atoms + 1` for each compound.
