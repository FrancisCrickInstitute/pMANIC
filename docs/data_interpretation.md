# Data Interpretation

## Export Structure

MANIC exports five worksheets representing successive processing stages.

## Raw Values

Direct integration of chromatographic peak areas without correction.

**Contents**: Uncorrected peak areas for each isotopologue (M+0, M+1, M+2, ...)

**Calculation**: Trapezoidal integration within defined window
```
Area = Σᵢ [(Iᵢ + Iᵢ₊₁)/2] × (tᵢ₊₁ - tᵢ)
```

**Use**: Quality control, verifying peak detection

## Corrected Values

Peak areas after mathematical deconvolution to remove natural isotope abundance.

**Algorithm**: Direct linear solve on normalized data
- `A` = Correction matrix (convolution of elemental distributions; MATLAB-aligned derivatization)
- `b` = Measured distribution per timepoint (normalized)
- `x` = True distribution; rescaled by total; divided by diagonal of `A`
− Applies to all compounds (including unlabeled) for GVISO parity

Natural abundances incorporated:
- Carbon: ¹³C (1.07%)
- Nitrogen: ¹⁵N (0.368%)
- Hydrogen: ²H (0.015%)
- Oxygen: ¹⁷O (0.038%), ¹⁸O (0.205%)
- Silicon: ²⁸Si (92.23%), ²⁹Si (4.68%), ³⁰Si (3.09%)

**Use**: Foundation for all downstream calculations

## Isotope Ratios

Normalized corrected values where sum equals 1.0.

**Calculation**:
```
Ratio[M+i] = Corrected[M+i] / Σⱼ(Corrected[M+j])
```

**Use**: Comparing labeling patterns independent of concentration

## % Label Incorporation

Percentage of molecules containing experimental label after background correction.

**Calculation**:
1. Background ratio from standard mixtures (using corrected signals):
   ```
   Background_Ratio = mean( (ΣLabeled) / M+0 ) in MM samples
   ```

2. Background correction:
   ```
   Corrected_Labeled = (ΣLabeled) - (Background_Ratio × Sample_M+0)
   ```

3. Percentage:
   ```
   % Label = (Corrected_Labeled / Total_Signal) × 100
   ```

**Requirements**: Standard mixture files

Note: Integration method (Time‑based vs Legacy) can influence background‑subtracted fractions. For strict MATLAB GVISO parity, enable Legacy Integration Mode before export.

## Abundances

Absolute concentrations calculated through internal standard calibration.

**MRRF Calculation**:
```
MRRF = (Signal_met/Conc_met) / (Signal_IS/Conc_IS)
```

**Sample Quantification**:
```
Abundance = (Total_Corrected × IS_Amount) / (IS_M0 × MRRF)
```

**Units**: nmol (hardcoded in abundances.py)

**Requirements**:
- Internal standard in all samples (IS M+0 used)
- Standard mixtures with known concentrations
- Compound library with `amount_in_std_mix`, `int_std_amount`, and `mmfiles`
