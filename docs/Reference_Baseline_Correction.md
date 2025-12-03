# Reference: Baseline Correction

## Overview

Baseline correction is a technique for removing the contribution of background signal from chromatographic peak areas. It improves accuracy by accounting for elevated baseline levels that would otherwise inflate integrated areas.

MANIC uses a **linear baseline subtraction** algorithm that fits a straight line through points at the edges of the integration window and subtracts the area under this line from the total peak area.

---

## How It Works

### Algorithm Steps

1. **Identify Edge Points:** Take the first 3 and last 3 data points within the integration window.
2. **Calculate Edge Averages:** Compute the mean intensity at each edge.
3. **Fit Linear Baseline:** Draw a straight line connecting these two averaged edge points.
4. **Calculate Baseline Area:** Integrate the area under this line using the trapezoidal rule.
5. **Subtract from Peak:** The baseline area is subtracted from the total integrated peak area.

### Mathematical Formulation

Given an integration window from $t_{left}$ to $t_{right}$:

$$I_{left} = \frac{1}{3}\sum_{i=1}^{3} I_i$$

$$I_{right} = \frac{1}{3}\sum_{i=n-2}^{n} I_i$$

The baseline is a linear function:

$$B(t) = I_{left} + \frac{(I_{right} - I_{left})}{(t_{right} - t_{left})} \times (t - t_{left})$$

The corrected area is:

$$\text{Area}_{corrected} = \text{Area}_{total} - \text{Area}_{baseline}$$

### Negative Value Handling

If the baseline subtraction results in a negative area (which can occur when the baseline estimate exceeds the actual signal), the value is **clamped to zero**. This prevents physically meaningless negative abundances.

---

## Visual Representation

When baseline correction is enabled, MANIC displays the fitted baseline as a **dashed line** on both:
- The main chromatogram grid plots
- The detailed EIC view (accessed via right-click → View Detailed...)

The baseline line uses the same color as its corresponding isotopologue trace, making it easy to see which baseline applies to which signal.

---

### Considerations

- **Default Behavior:** Baseline correction is **enabled by default** for all compounds.
- **Per-Compound Setting:** The setting is stored per compound, not per sample. All samples for a given compound share the same baseline correction state.
- **Effect on Ratios:** Since baseline correction is applied to all isotopologues equally, isotopologue *ratios* are generally less affected than absolute abundances.

---

## Configuration

### Enabling/Disabling

The baseline correction checkbox is located in the left toolbar, between the Integration Window and the Label Incorporation chart.

1. **Select a Compound** from the compound list.
2. **Toggle the Checkbox** labeled "Baseline correction".
3. **Observe the Change:** The plots will immediately refresh to show (or hide) the dashed baseline lines.

### Visual Indicators

| State | Display |
| :--- | :--- |
| **Enabled** | Blue checkbox with white checkmark ✓ |
| **Disabled** | Gray unchecked box |

---

## Effect on Exported Data

When baseline correction is enabled, it is applied to **all sheets** in the exported workbook, including:

- **Raw Values Sheet:** Contains baseline-corrected integrated areas.
- **Corrected Values Sheet:** Natural isotope correction applied to baseline-corrected areas.
- **All Derived Sheets:** Ratios, % Label, and Abundances all use the baseline-corrected values.

This ensures consistent quantification throughout the entire analysis pipeline.

---

## Technical Notes

### Compatibility with Integration Methods

Baseline correction works with both integration methods:
- **Time-Based Integration (Default):** Baseline area calculated using actual time units.
- **Legacy Integration:** Baseline area calculated using unit-spacing.

### Edge Cases

| Situation | Behavior |
| :--- | :--- |
| Fewer than 6 points in window | Baseline correction skipped (insufficient data) |
| Negative corrected area | Clamped to zero |
| Zero intensity at edges | Baseline treated as horizontal at zero |

### Algorithm Origin

This implementation matches the baseline correction algorithm used in the legacy MATLAB GVISO tool, ensuring numerical compatibility with historical analyses.
