# Update Old Data

## Overview

Reconstructs complete MANIC exports from Raw Values when CDF files are unavailable. Uses approximate mode that applies natural abundance correction to integrated totals rather than per-timepoint data.

## Required Input

1. **Compound Definition File** (Excel/CSV)
   - Same structure as standard import
   - Must include formula, labelatoms, derivatization parameters

2. **Raw Values Worksheet** (Excel)
   - From previous MANIC export
   - Column headers: compound names with isotopologue suffixes
   - Sample names must match exactly

## Processing Difference

**Standard Processing:**
```
CDF Files
  → Extract raw EICs (time series for each m/z)
  → Natural abundance correction on each timepoint
  → Store corrected time series in database
  → Integration of raw EICs → Raw Values sheet
  → Integration of corrected time series → Corrected Values sheet
  → Calculate ratios, % label, abundances
```

**Approximate Processing:**
```
Raw Values (integrated raw EICs, no correction)
  → Natural abundance correction on integrated totals
  → Corrected Values (approximate)
  → Calculate ratios, % label, abundances
```

The key difference: Standard mode corrects thousands of individual timepoints in the chromatogram, then integrates. Approximate mode takes already-integrated values and corrects those single sums. This changes how constraints (like non-negativity) are applied and accumulates different rounding errors.

## Expected Differences

| Data Type | Typical Difference |
|-----------|-------------------|
| Corrected Values | 0.5-1% |
| Isotope Ratios | < 0.5% |
| % Label | 1-2% |
| Abundances | 2-3% |

## Use Cases

### Appropriate
- Legacy data recovery

### Inappropriate
- When CDF files are available

## Implementation

The approximation arises from:
- Non-negativity constraints applied once vs. per timepoint
- Different numerical precision accumulation
- Single correction vs. multiple corrections

## MRRF in Approximate Mode

MRRF calculation uses available samples in Raw Values:
- Identifies MM samples by pattern matching
- Calculates from integrated totals
- Same mathematical approach as standard mode

## Changes from MANIC v3.3.0 and Below

- **Previous**: Use approximate approach for standard processing as well. Resulted in lower accuracy.
- **Current**: Full reconstruction from Raw Values export
