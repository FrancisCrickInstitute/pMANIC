# Mass Tolerance

## Algorithm (MATLAB-Aligned)

Offset-and-round matching (asymmetric window):

```python
offset_mass = detected_mass - tolerance_offset
rounded_mass = floor(offset_mass + 0.5)  # half-up for positive masses
is_match = (rounded_mass == target_integer_mass)
```

This is equivalent to matching within an asymmetric window biased to lower m/z.

## Behavior Example

Target mass 319 with offset 0.2 Da:

| Detected | Calculation            | Rounded | Match |
|----------|------------------------|---------|-------|
| 318.7    | 318.7 - 0.2 = 318.5    | 319     | Yes   |
| 319.0    | 319.0 - 0.2 = 318.8    | 319     | Yes   |
| 319.6    | 319.6 - 0.2 = 319.4    | 319     | Yes   |
| 319.7    | 319.7 - 0.2 = 319.5    | 320     | No    |

Effective window (half-up): approximately 318.7 to 319.7 Da (upper edge exclusive).

## Configuration

Settings → Mass Tolerance
- Default: 0.2 Da
- Range: 0.01–1.0 Da
- Changing tolerance requires data re-import

## Rationale

The asymmetric window corrects for systematic mass calibration drift common in GC-MS SIM where fragments tend to skew high at larger m/z.

## Changes from MANIC v3.3.0 and Below

- Previous: Same method but unconfigurable.
- Current: User-configurable offset; implemented with half-up rounding to mirror MATLAB behavior.
