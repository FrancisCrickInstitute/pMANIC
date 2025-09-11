# Integration Methods

## Available Methods

### Time-Based Trapezoidal Integration (Default)

Calculates peak area using actual time intervals:

```
Area = Σᵢ [(Iᵢ + Iᵢ₊₁)/2] × (tᵢ₊₁ - tᵢ)
```

- Units: Intensity × time
- Physically meaningful results
- Instrument-independent

### Legacy Unit-Spacing Integration

Assumes unit spacing between data points:

```
Area = Σᵢ [(Iᵢ + Iᵢ₊₁)/2]
```

- Values ~100× larger than time-based
- Compatible with MATLAB MANIC v3.3.0
- Available via Settings → Legacy Integration Mode

## Integration Window

Defined by:
- **Retention Time (tr)**: Peak center
- **Left Offset (loffset)**: Time before tr
- **Right Offset (roffset)**: Time after tr

```
Integration Start = tr - loffset
Integration End = tr + roffset
```

## Method Selection

### Use Time-Based When:
- Starting new studies
- Publishing results
- Comparing across instruments

### Use Legacy When:
- Comparing with MATLAB MANIC v3.3.0 or earlier
- Maintaining historical continuity

## Configuration

Settings → Legacy Integration Mode
- Off: Time-based integration
- On: Legacy unit-spacing

The active method is documented in export changelog.md.

## Effect on Export Values

| Worksheet | Time-Based | Legacy |
|-----------|------------|--------|
| Raw Values | Smaller values (intensity·time) | ~100× larger |
| Corrected Values | Proportionally smaller | ~100× larger |
| Isotope Ratios | No difference (normalized) | No difference |
| % Label | Minimal difference | Minimal difference |
| Abundances | Scaled by MRRF | Scaled by MRRF |

## Changes from MANIC v3.3.0 and Below

- **Previous**: Legacy unit-spacing as default
- **Current**: Time-based as default, legacy available in settings
