# Integration Methods: Legacy vs Time-Based

## Overview

MANIC supports two integration methods for peak area calculation. Understanding the difference between these methods is crucial for proper data interpretation and ensuring compatibility when transitioning from MATLAB MANIC.

## Available Integration Modes

### 1. Time-Based Integration (Default - Recommended)
- **How to enable**: Default setting (Legacy Integration Mode: Off)
- **Method**: Uses actual time intervals between data points
- **Results**: Physically meaningful values with proper units
- **Best for**: New studies, scientific accuracy, method validation

### 2. Legacy Unit-Spacing Integration (MATLAB Compatible)
- **How to enable**: Settings → "Legacy Integration Mode: On"
- **Method**: Assumes unit spacing between data points (ignores time)
- **Results**: Values ~100× larger than time-based method
- **Best for**: Direct comparison with MATLAB MANIC results

## Technical Implementation

### Legacy Unit-Spacing Integration (MATLAB Compatible)
```python
peak_area = np.trapz(intensity_data)  # No time data provided
```

When legacy mode is enabled, only intensity values are used for integration. This assumes **unit spacing** between data points, calculating area as if each time step equals 1 unit, regardless of actual time intervals.

**Result**: "Unitless Area" - larger numerical values that match MATLAB MANIC.

### Time-Based Integration (Default)
```python
peak_area = np.trapz(intensity_data, time_data)  # Time data included
```

The default method provides both intensity and time arrays to calculate true area under the curve using actual time intervals between data points.

**Result**: "True Area" - physically meaningful values with proper units (intensity × time).

## Choosing the Right Method

### Use Time-Based Integration (Default) When:
- Starting new studies or method development
- Seeking scientifically accurate, physically meaningful results
- Comparing between different instruments or sampling rates
- Publishing results that need to be reproduced on other systems

### Use Legacy Integration When:
- Transitioning from MATLAB MANIC and need direct comparison
- Validating that the conversion is working correctly  
- Collaborating with groups still using MATLAB MANIC
- Temporarily matching legacy datasets during transition period

## Value Differences

The integration method affects **all calculated values** throughout the analysis:

### Raw Values Worksheet
- **Legacy**: ~100× larger peak areas
- **Time-based**: Smaller, physically meaningful areas

### Corrected Values Worksheet  
- **Legacy**: ~100× larger corrected areas
- **Time-based**: Proportionally smaller corrected areas

### Abundances Worksheet
- **Legacy**: Similar to MATLAB MANIC absolute concentrations
- **Time-based**: Different absolute values, but same relative ratios

## Real-World Example

Consider a chromatographic peak sampled every 0.01 minutes with 100 data points:

### Legacy Integration (MATLAB Compatible)
- Treats each data point as 1 unit apart
- Area calculated as if peak spans 100 units  
- **Result**: Large numerical value (matches MATLAB)

### Time-Based Integration (Default)
- Uses actual time spacing (0.01 minutes between points)
- Area calculated over actual 1.0 minute span (100 × 0.01)
- **Result**: Value 100× smaller, but physically correct

## How to Switch Between Methods

### Via Settings Menu
1. Go to **Settings** → **Legacy Integration Mode**
2. **Off** (default): Time-based integration  
3. **On**: Legacy unit-spacing integration (MATLAB compatible)
4. Changes apply immediately to new exports

### Verification
- Check the **changelog.md** file generated with each export
- Integration method is clearly documented in the "Processing Settings" section
- Expected value scale is noted for reference

## Important Considerations

### Data Interpretation
- **Absolute values**: Will differ dramatically between methods
- **Relative ratios**: Remain consistent between methods  
- **Statistical comparisons**: Valid within each method
- **Literature comparison**: Note which method was used

### Method Validation
- Use legacy mode when validating conversion from MATLAB MANIC
- Switch to time-based mode for new studies and publications
- Document the integration method in all analytical reports

### Best Practices
1. **Choose one method** and use consistently throughout a study
2. **Document the method** in your materials and methods section
3. **Include integration method** in data sharing and collaboration
4. **Validate key results** if switching between methods mid-study

## Conclusion

Both integration methods are scientifically valid approaches that serve different purposes:

- **Time-based integration** provides physically meaningful, scientifically rigorous results
- **Legacy integration** ensures compatibility and smooth transition from MATLAB MANIC

The choice depends on your specific needs: scientific accuracy for new work, or compatibility for transitional validation. The key is understanding the difference and using the appropriate method consistently.