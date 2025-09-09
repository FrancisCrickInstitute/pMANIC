# Integration Methods: MATLAB vs Python MANIC

## Overview

This document explains the fundamental difference between the integration methods used in MATLAB MANIC and Python MANIC, and why Python MANIC uses the scientifically correct time-based approach.

## The Key Difference

### MATLAB MANIC: Unit-Spacing Integration
```matlab
peak_area = trapz(validIonData(:, intBoundaries), 2)
```

MATLAB's `trapz` function, when given only intensity values, assumes **unit spacing** between data points. This means it calculates area as if each time step equals 1 unit, regardless of the actual time intervals in your chromatogram.

**Result**: "Unitless Area" - a numerical value that doesn't correspond to real physical units.

### Python MANIC: Time-Based Integration  
```python
peak_area = np.trapz(intensity_data, time_data)
```

Python MANIC explicitly provides both intensity and time arrays to `np.trapz`. This calculates the true area under the curve using actual time intervals between data points.

**Result**: "True Area" - physically meaningful values with proper units (intensity × time).

## Why This Matters

The difference in integration methods causes Python MANIC to produce values approximately **100× smaller** than MATLAB MANIC. This is not an error—it reflects the difference between:

- **MATLAB**: Arbitrary numerical integration ignoring time scale
- **Python**: Scientifically accurate integration respecting actual time intervals

## Real-World Example

Consider a chromatographic peak sampled every 0.01 minutes:

### MATLAB Method
- Treats each data point as 1 unit apart
- Peak with 100 data points = area calculated over 100 units
- **Result**: Large numerical value

### Python Method  
- Uses actual time spacing (0.01 minutes between points)
- Same peak = area calculated over 1.0 minute (100 × 0.01)
- **Result**: Value 100× smaller, but physically correct

## Why Python MANIC Uses Time-Based Integration

1. **Scientific Accuracy**: Results have meaningful physical units
2. **Reproducibility**: Results are independent of sampling rate
3. **Standard Practice**: Follows established analytical chemistry conventions
4. **Quantitative Reliability**: Enables proper comparison between different instruments and methods

## Impact on Your Data

When comparing results between MATLAB and Python MANIC:

- **Raw values will differ by ~100×** due to integration method
- **Relative ratios between samples remain the same**
- **Statistical analysis and comparisons are unaffected**
- **Python values are scientifically more accurate**

## Conclusion

Python MANIC's time-based integration provides scientifically rigorous quantification that properly accounts for chromatographic time scales. While absolute values differ from MATLAB MANIC, the relative relationships between samples are preserved, and the results are more physically meaningful.