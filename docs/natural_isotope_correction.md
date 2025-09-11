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

The correction solves: **A × x = b**

Where:
- **A** = Correction matrix (theoretical isotope patterns)
- **x** = True isotopologue distribution
- **b** = Measured isotopologue distribution

## Algorithm Implementation

### Well-Conditioned Matrices (condition number < 10¹⁰)
- Uses direct linear algebra (numpy.linalg.solve)
- ~100× faster than optimization
- Typical for molecules < 20 carbons

**Matrix conditioning**: A well-conditioned matrix has values that are numerically stable to solve. When the condition number is low, small changes in input produce small changes in output.

### Ill-Conditioned Matrices
- Uses constrained optimization (SLSQP)
- Enforces non-negativity and mass conservation
- Required for large molecules or complex derivatization

**Why matrices become ill-conditioned**: As molecules get larger, the correction matrix rows become increasingly similar (many isotope combinations produce similar patterns), making the system harder to solve uniquely.

### Performance Optimization
- Matrix caching: 5-10× speedup
- Vectorized time series processing: 20-100× speedup

## Compound Configuration

### Required Parameters

**Label Atoms** (`labelatoms`):
- Number of positions that can incorporate label
- Internal standards must have `labelatoms = 0`

**Molecular Formula** (`formula`):
- Standard notation (e.g., C6H12O6)

**Derivatization**:
- `tbdms`: Number of TBDMS groups (adds C₆H₁₅Si per group)
- `meox`: Number of methoxyamine groups (adds CH₃ON per group)
- `me`: Number of methyl groups (adds CH₂ per site)

### Example Configuration

```
name: Glucose
formula: C6H12O6
labelatoms: 6
tbdms: 5
meox: 1
me: 0
```

Total formula after derivatization: C₃₇H₈₈O₇NSi₅

## Common Issues

### All Corrected Values Are Zero
- Internal standard has `labelatoms > 0`
- Solution: Set `labelatoms = 0` for internal standards

### Negative Corrected Values
- Incorrect formula or derivatization parameters
- Solution: Verify compound configuration

## Changes from MANIC v3.3.0 and Below

### Algorithm
- **Previous**: Variable implementations
- **Current**: Adaptive selection based on matrix conditioning

### Timing
- **Previous**: Correction after integration
- **Current**: Per-timepoint correction before integration

### Performance
- **Previous**: Matrix recalculated for each sample
- **Current**: Matrix caching reduces computation 5-10×