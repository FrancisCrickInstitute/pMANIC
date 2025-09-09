# Natural Isotope Abundance Correction

## Overview

Natural isotope abundance correction is a critical step in processing isotope-labeled mass spectrometry data. This mathematical procedure removes the predictable background signal caused by naturally occurring heavy isotopes, revealing the true experimental labeling pattern.

## The Problem: Natural Isotope "Smearing"

### What Causes the Problem?

All elements have naturally occurring heavy isotopes:
- **Carbon**: ¹²C (98.93%) and ¹³C (1.07%) 
- **Nitrogen**: ¹⁴N (99.632%) and ¹⁵N (0.368%)
- **Hydrogen**: ¹H (99.985%) and ²H (0.015%)
- **Oxygen**: ¹⁶O (99.757%), ¹⁷O (0.038%), ¹⁸O (0.205%)
- **Silicon**: ²⁸Si (92.23%), ²⁹Si (4.68%), ³⁰Si (3.09%)

### The "Detective" Analogy

Think of your raw mass spectrometry data as a **blurry photograph** of the true labeling pattern. Natural abundance has "smeared" the sharp, true signal across multiple mass channels.

The correction algorithm is like a **detective** who:
1. **Knows the blurring pattern** (natural abundance distributions)
2. **Has the blurry photo** (your raw data)
3. **Reconstructs the sharp original** (true experimental labeling)

## Mathematical Approach

### Linear System Formulation

Natural abundance correction solves a linear equation system:

```
Measured_Distribution = Correction_Matrix × True_Distribution
```

Where:
- **Measured_Distribution**: Your raw isotopologue data [M+0, M+1, M+2, ...]
- **Correction_Matrix**: Theoretical natural abundance patterns
- **True_Distribution**: The corrected result (what we solve for)

### Building the Correction Matrix

For each compound, MANIC builds a matrix where:
- **Each column** represents the expected measured pattern for a pure labeled state
- **Element [i,j]** is the contribution of true M+j to measured M+i

#### Example: Glucose (C₆H₁₂O₆) with 6 labelable carbons

The correction matrix accounts for:
1. **Unlabeled carbons**: Natural ¹³C abundance from non-labeled positions
2. **Labeled carbons**: Experimental ¹³C from your labeled substrate  
3. **Other elements**: Natural abundance from H, N, O, Si atoms
4. **Derivatization**: Additional atoms from TBDMS, MeOX, methylation

### Matrix Inversion Methods

MANIC uses two approaches depending on matrix properties:

#### Fast Direct Solver (Well-Conditioned Matrices)
- **When**: Matrix condition number < 10¹⁰
- **Method**: Direct linear algebra (`np.linalg.solve`)
- **Speed**: ~100x faster than optimization
- **Use case**: Most small-to-medium molecules (< 20 carbons)

#### Robust Optimization (Ill-Conditioned Matrices)  
- **When**: Matrix condition number ≥ 10¹⁰ or small datasets
- **Method**: Constrained optimization (SLSQP)
- **Constraints**: Non-negativity, mass conservation
- **Use case**: Large molecules, complex derivatization patterns

## Algorithm Performance

### Optimization Features

1. **Matrix Caching**: Pre-computed correction matrices are reused across samples
2. **Vectorized Processing**: Entire chromatographic time series corrected simultaneously  
3. **Adaptive Algorithm Selection**: Automatic choice between fast and robust methods
4. **Batch Operations**: Multiple samples processed efficiently

### Typical Performance
- **Matrix reuse across samples**: 5-10x speedup via caching
- **Vectorized time series**: 20-100x speedup for chromatographic data
- **Combined improvement**: ~50-200x faster than naive implementations

## Compound Configuration

### Critical Settings

#### Label Atoms (`labelatoms` column)
- **Labeled compounds**: Set to number of positions that can incorporate label
  - Example: Glucose with U-¹³C₆ → `labelatoms = 6`
  - Example: Alanine with [3-¹³C] → `labelatoms = 1`
- **Internal standards**: **MUST be set to 0** (no labeling expected)
  - Example: scyllo-inositol internal standard → `labelatoms = 0`

#### Formula (`formula` column)  
- **Base molecular formula** before derivatization
- **Standard format**: C₆H₁₂O₆ → `C6H12O6`
- **Used for**: Calculating natural abundance patterns

#### Derivatization Counts
- **`tbdms`**: Number of TBDMS (tert-butyldimethylsilyl) groups
  - Each adds: C₆H₁₅Si (minus H replaced)
- **`meox`**: Number of MeOX (methoxyamine) groups  
  - Each adds: CH₃ON
- **`me`**: Number of methylation modifications
  - Each adds: CH₂

## Common Issues and Solutions

### Problem: "All corrected values are zero"

**Cause**: Internal standard configured as labeled compound
```
# Wrong: Internal standard with labelatoms > 0
scyllo-Ins: labelatoms = 4  # Creates mathematical paradox

# Correct: Internal standard with labelatoms = 0  
scyllo-Ins: labelatoms = 0  # No correction applied, raw data copied
```

**Solution**: Set `labelatoms = 0` for all internal standards

### Problem: "Negative corrected values"

**Cause**: Usually incorrect derivatization counts or formula
- Check TBDMS, MeOX, methylation counts
- Verify molecular formula matches actual compound

**Solution**: Review compound library configuration

### Problem: "Correction taking very long"

**Cause**: Ill-conditioned matrices forcing optimization fallback
- Common with large molecules (> 30 carbons)
- Complex derivatization patterns

**Solutions**: 
- Verify derivatization counts are accurate
- Consider reducing number of isotopologues tracked
- Check for unrealistic labeling patterns

## Validation and Quality Control

### Expected Results
1. **Mass conservation**: Total signal should be preserved
2. **Non-negativity**: All corrected values ≥ 0
3. **Reasonable patterns**: Corrected ratios should reflect biology

### Diagnostic Checks
1. **Compare Raw vs Corrected**: Large changes suggest misconfiguration
2. **Check internal standards**: Should show minimal correction 
3. **Validate with known samples**: Test with fully labeled/unlabeled controls

## Technical Implementation

### Core Algorithm Location
- **File**: `src/manic/processors/natural_abundance_correction.py`
- **Main class**: `NaturalAbundanceCorrector`
- **Key method**: `correct_time_series()`

### Processing Workflow
1. **Import**: Raw EIC data imported from instrument files
2. **Correction**: Natural abundance correction applied per compound/sample
3. **Storage**: Corrected data stored in `eic_corrected` database table
4. **Export**: Corrected values appear in "Corrected Values" Excel sheet

### Caching and Memory
- **Matrix cache**: ~1-10KB per unique compound formula
- **Cache lifetime**: Cleared after batch processing
- **Memory impact**: Minimal compared to raw data files (MB-GB)

## Best Practices

1. **Validate configurations**: Always check `labelatoms` values match experimental design
2. **Test with controls**: Use fully labeled and unlabeled standards
3. **Monitor condition numbers**: Watch for algorithm fallbacks in logs
4. **Review patterns**: Sanity-check corrected isotopologue distributions
5. **Keep backups**: Natural abundance correction modifies data irreversibly

---

*Natural abundance correction is the foundation of accurate isotope-labeled metabolomics. Proper compound configuration is essential for reliable results.*