# Mass Tolerance

## Algorithm

MANIC uses an offset-and-round method for mass matching:

```python
offset_mass = detected_mass - tolerance_offset
rounded_mass = round(offset_mass)
is_match = (rounded_mass == target_integer_mass)
```

## Behavior Example

Target mass 319 with offset 0.2 Da:

| Detected | Calculation | Rounded | Match |
|----------|-------------|---------|-------|
| 318.7 | 318.7 - 0.2 = 318.5 | 319 | Yes |
| 319.0 | 319.0 - 0.2 = 318.8 | 319 | Yes |
| 319.5 | 319.5 - 0.2 = 319.3 | 319 | Yes |
| 319.7 | 319.7 - 0.2 = 319.5 | 320 | No |

Effective window: 318.7 to 319.5 Da (asymmetric)

## Configuration

Settings → Mass Tolerance
- Default: 0.2 Da
- Range: 0.01-1.0 Da
- Requires data re-import after change

## Rationale

The asymmetric window corrects for systematic mass calibration drift common in GC-MS instruments where heavier fragments read at higher apparent masses.

## Changes from MANIC v3.3.0 and Below

- **Previous**: Same method but unconfigurable.
- **Current**: User-configurable offset with documentation
