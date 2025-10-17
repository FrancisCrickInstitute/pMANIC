# Peak Area Validation

## Overview

Peak validation identifies chromatographic peaks with insufficient signal for reliable quantification by comparing total peak areas against the internal standard. This ensures data quality by flagging metabolites with weak signals that may not be trustworthy for quantitative analysis.

## Algorithm

The validation compares the **total peak area** (sum of all isotopologues) for each compound against the internal standard's total peak area:

```
Compound_Total = M0 + M1 + M2 + ... + Mn
IS_Total = M0 + M1 + M2 + ... + Mn (for internal standard)
Threshold = IS_Total × Minimum_Ratio
Valid = (Compound_Total ≥ Threshold)
```

**Key points:**
- Each compound is integrated using its **own retention time and offset boundaries**
- Session overrides (user-adjusted RT/offsets) are automatically respected
- The internal standard is integrated using its **own retention time and offset boundaries**
- Default minimum ratio: 5% (0.05)

## Integration Boundaries

Each compound uses its own integration parameters, which can be customized per sample via session overrides:

- **Retention Time (RT)**: Center of the integration window
- **Left Offset (loffset)**: Time before RT to start integration
- **Right Offset (roffset)**: Time after RT to end integration

Integration window: `[RT - loffset, RT + roffset]`

When you adjust these parameters for specific plots, the validation automatically updates to use the new boundaries.

## Visual Indicators

### In Plots
- **Valid peaks**: Normal white background
- **Invalid peaks**: Red background
- **No validation**: Normal appearance when:
  - No internal standard selected
  - Minimum ratio set to 0
  - Validation disabled

### In Excel Export
- **Invalid cells**: Light red background (`#FFCCCC`)
- Applied to **all isotopologue columns** for failed sample/compound combinations
- Appears in **all 5 sheets**:
  - Raw Values
  - Corrected Values
  - Isotope Ratios
  - % Label Incorporation
  - Abundances

## Configuration

**Settings → Minimum Peak Area**

- Default: 0.05 (5% of internal standard total area)
- Range: 0.001-1.000
- Step: 0.001
- Setting to 0 disables validation

The threshold is applied globally to all compounds across all samples.

## Scope

- Applies to **all isotopologues** (not just M0)
- Validation uses **total area** (sum of all isotopologues)
- Each compound validated against its own integration boundaries
- Internal standard must be selected for validation to occur

## Implementation Details

### Data Flow

1. **Import/Cache**: Peak areas calculated during bulk data load using `DataProvider.load_bulk_sample_data()`
2. **Validation**: `DataProvider.validate_peak_area()` compares totals using cached data
3. **UI Display**: Invalid plots shown with red background in real-time
4. **Excel Export**: Validation computed once, applied to all 5 sheets

### Cache Invalidation

Validation cache is automatically invalidated when:
- Session activity changes (RT, offsets adjusted)
- Mass tolerance changes
- Integration mode changes (time-based ↔ legacy)
- New CDF data imported

### Performance

- **Negligible impact**: Validation uses pre-computed cached areas (simple sum)
- **Fast plotting**: Cached provider instance reused across validations
- **Efficient export**: Validation computed once, reused for all sheets

## Changes from MANIC v3.3.0 and Below

### v3.3.0 and Earlier
- No automatic quality control
- Manual visual inspection required

### Current Version
- **Peak height → Peak area**: Now uses scientifically accurate total area instead of maximum height
- **All isotopologues**: Validation considers complete peak signal, not just M0
- **Per-compound boundaries**: Each compound validated using its own integration parameters
- **Session-aware**: Respects user-adjusted RT/offsets automatically
- **Excel highlighting**: Failed validations visible in exported data
- **Real-time updates**: Validation colors update immediately when parameters change


