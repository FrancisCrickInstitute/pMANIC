# Integration Methods

MANIC supports two approaches to integrate chromatographic peaks.

## Time-Based Trapezoidal Integration (Default)

Calculates peak area using actual time intervals:

```
Area = Σᵢ [(Iᵢ + Iᵢ₊₁)/2] × (tᵢ₊₁ - tᵢ)
```

- Units: Intensity × time
- Physically meaningful results
- Instrument-independent

## Legacy Unit-Spacing Integration (MATLAB/GVISO)

Assumes unit spacing between data points (Δt = 1), matching historical MATLAB GVISO exports:

```
Area = Σᵢ [(Iᵢ + Iᵢ₊₁)/2]
```

- Values ~100× larger than time-based
- Use when reproducing MATLAB GVISO numbers
- Toggle via Settings → Legacy Integration Mode

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

Use Time-Based when:
- Starting new studies
- Publishing results
- Comparing across instruments

Use Legacy when:
- Comparing with MATLAB GVISO
- Maintaining historical continuity

## Configuration

Settings → Legacy Integration Mode
- Off: Time-based integration
- On: Legacy unit-spacing

The active method is recorded in the export changelog.

## NA Correction Timing

Natural abundance correction is applied per timepoint before integration for all compounds (including unlabeled) to match GVISO downstream calculations.

## Effect on Export Values

| Worksheet | Time-Based | Legacy |
|-----------|------------|--------|
| Raw Values | Intensity·time | ~100× larger |
| Corrected Values | Scaled with Raw | ~100× larger |
| Isotope Ratios | No difference | No difference |
| % Label | Minimal difference | Minimal difference |
| Abundances | Scaled by MRRF | Scaled by MRRF |

## Changes from MANIC v3.3.0 and Below

- Previous: Legacy unit-spacing as default
- Current: Time-based as default; legacy available in settings
