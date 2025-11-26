# Natural Isotope Abundance Correction

## Overview

Natural isotope correction removes the contribution of naturally occurring heavy isotopes from mass spectrometry measurements to isolate experimental labeling.

## Natural Isotope Abundances

Elements in biological molecules contain:
- Carbon: ¹³C (1.07%)
- Nitrogen: ¹⁵N (0.368%)
- Hydrogen: ²H (0.015%)
- Oxygen: ¹⁷O (0.038%), ¹⁸O (0.205%)
- Silicon (derivatization): ²⁹Si (4.68%), ³⁰Si (3.09%)

## Mathematical Method

We solve a linear system: `A × x = b`

Where:
- `A` = Correction matrix built by convolving elemental isotope distributions (MATLAB-aligned derivatization)
- `x` = True isotopologue distribution (fractions)
- `b` = Measured isotopologue distribution (normalized per timepoint)

## Algorithm Implementation

### Solver (Direct Only)
- Normalize each timepoint so intensities sum to 1
- Solve `A × x = b` via direct linear algebra (no optimization path)
- Rescale by the original total intensity
- Divide each isotopologue by the diagonal element of `A`
- Clamp negatives to 0

We report condition numbers for diagnostics, but always use the direct solver for parity with MATLAB GVISO and performance.

### Unlabeled (1×1) Case
- For compounds with `labelatoms = 0` (single isotopologue), the normalized constrained MATLAB solution reduces to `cordist = 1`, so the corrected intensity equals the original total before a single diagonal division. The implementation special‑cases this 1×1 case to match MATLAB behavior.

### Performance
- Matrix caching (reuse per compound/derivatization)
- Vectorized time series processing

## Compound Configuration

### Required Parameters

**Label Atoms** (`labelatoms`):
- Number of positions that can incorporate label
- Internal standards must have `labelatoms = 0`

**Molecular Formula** (`formula`):
- Standard notation (e.g., C6H12O6)

**Derivatization (MATLAB-aligned)**:
- `tbdms`: `C += (t−1)*6 + 2`, `H += (t−1)*15 + 6 − t`, `Si += t`
- `meox`: `N += m`, `C += m`, `H += 3m` (no O term)
- `me`: `C += e`, `H += 2e`

### Example Configuration

```
name: Glucose
formula: C6H12O6
labelatoms: 6
tbdms: 5
meox: 1
me: 0
```

Total formula after derivatization follows the rules above (matches MATLAB GVISO).

## Common Issues

### All Corrected Values Are Zero
- Check `labelatoms` and formula/derivatization settings

### Negative Corrected Values
- Caused by parameter mismatch; verify compound configuration

## How MM Files Factor In

Natural abundance correction itself does not use MM files. MM files are used afterwards to estimate and subtract background labeling for the “% Label Incorporation” sheet:

1) Compute background ratio from MM samples (using corrected signals):
   `background = mean( (Σ labeled) / M0 )`

2) For each sample:
   `corrected_labeled = (Σ labeled) − background × M0`

3) `% label = corrected_labeled / (M0 + corrected_labeled) × 100`

This makes `% label` robust to systematic background signal observed in standards.

## Changes from MANIC v3.3.0 and Below

### Algorithm
- **Previous**: Mixed direct/optimization paths, conventional derivatization
- **Current**: Direct solver only; MATLAB-aligned derivatization

### Scope
- NA correction is applied to all compounds (including unlabeled) for GVISO parity.

### Performance
- **Previous**: Matrix recalculated for each sample
- **Current**: Matrix caching reduces computation 5-10×
