# MRRF Calibration

## Overview

Metabolite Response Ratio Factor (MRRF) enables absolute quantification by correcting for differential ionization efficiency between metabolites and the internal standard.

## MRRF Calculation

From standard mixtures:

```
MRRF = (Signal_met/Conc_met) / (Signal_IS/Conc_IS)
```

Where:
- Signal_met = Mean metabolite total corrected signal in MM samples
- Conc_met = Known concentration (`amount_in_std_mix`)
- Signal_IS = Mean internal standard M+0 signal in MM samples
- Conc_IS = Internal standard concentration

## Sample Quantification

```
Abundance = (Total_Corrected_sample × IS_amount) / (IS_M0_sample × MRRF)
```

Where:
- Signal_sample = Total corrected signal for metabolite
- IS_amount = Internal standard added (`int_std_amount`)
- Signal_IS_sample = Internal standard signal in sample
- MRRF = Pre-calculated response factor

> **Failure conditions:** If no internal standard is selected, or if either `int_std_amount` or `amount_in_std_mix` is missing for that compound, the export aborts rather than emitting partial Abundance data.

Units match those used for `int_std_amount`.

## Required Configuration

### Compound Library
- `amount_in_std_mix`: Metabolite concentration in standards
- `int_std_amount`: Internal standard amount added to samples
- `mmfiles`: Pattern to identify standard mixture files (e.g., "*MM*")

### Standard Mixtures
- Must contain all target metabolites
- Known concentrations required
- Identified by mmfiles pattern matching

## Implementation Details

### Standard Identification
```python
# From calibration.py
mm_samples = provider.resolve_mm_samples(mm_files_field)
```

Patterns support:
- Wildcards: `*` anywhere (translated to SQL LIKE `%`)
- Multiple patterns separated by comma/semicolon/newline
- Case-insensitive matching
- Special characters (`%`, `_`) are treated literally

### Current vs. Historical Calculation

**Current (Python MANIC):**
- Calculates mean signals first (per your configuration)
- Uses IS M+0 only
- Uses corrected EICs for all compounds (including unlabeled)

**Historical (MATLAB MANIC v3.3.0):**
- Sum-based calculation
- IS M+0 only

Note: Mean vs. sum aggregation can differ if MM sample counts vary or contain outliers.

## Changes from MANIC v3.3.0 and Below

- **Previous**: Sum-based calculation
- **Current**: Mean-based calculation
- **Impact**: Minor differences when standard concentrations vary
