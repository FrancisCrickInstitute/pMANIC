# MRRF Calibration

## Overview

Metabolite Response Ratio Factor (MRRF) enables absolute quantification by correcting for differential ionization efficiency between metabolites and the internal standard.

## MRRF Calculation

From standard mixtures:

```
MRRF = (Signal_met/Conc_met) / (Signal_IS/Conc_IS)
```

Where:
- Signal_met = Mean metabolite signal in MM samples
- Conc_met = Known concentration (`amount_in_std_mix`)
- Signal_IS = Mean internal standard signal in MM samples
- Conc_IS = Internal standard concentration

## Sample Quantification

```
Abundance = (Signal_sample × IS_amount) / (Signal_IS_sample × MRRF)
```

Where:
- Signal_sample = Total corrected signal for metabolite
- IS_amount = Internal standard added (`int_std_amount`)
- Signal_IS_sample = Internal standard signal in sample
- MRRF = Pre-calculated response factor

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
- Wildcards: `*MM*`
- Multiple patterns: `*MM_01*,*MM_02*,*standard*`

### Current vs. Historical Calculation

**Current (Python MANIC):**
- Calculates mean signals first
- Treats each measurement equally

**Historical (MATLAB MANIC v3.3.0):**
- Sums all signals, then divides
- Weights by signal contribution

Both approaches are equivalent when standard concentrations are uniform.

## Changes from MANIC v3.3.0 and Below

- **Previous**: Sum-based calculation
- **Current**: Mean-based calculation
- **Impact**: Minor differences when standard concentrations vary
