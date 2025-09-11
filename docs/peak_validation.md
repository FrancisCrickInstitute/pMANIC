# Peak Height Validation

## Overview

Peak validation identifies chromatographic peaks with insufficient signal for reliable quantification by comparing m0 peak heights against the internal standard.

## Algorithm

```
Threshold = Height_IS × Minimum_Ratio
Valid = (Height_m0 ≥ Threshold)
```

Default minimum ratio: 5% (0.05)

## Visual Indicators

- **Valid peaks**: Normal white background
- **Invalid peaks**: Red background (rgba(255, 200, 200, 120))
- **No validation**: Normal appearance when no internal standard selected

## Configuration

Settings → Minimum Peak Height
- Default: 0.05 (5%)
- Range: 0.000-1.000
- Step: 0.001

From main_window.py, the threshold is user-configurable through the settings menu.

## Scope

- Applies only to m0 (unlabeled) peaks

## Changes from MANIC v3.3.0 and Below

- **Previous**: No automatic quality control
- **Current**: Visual validation with red highlighting and configurable threshold