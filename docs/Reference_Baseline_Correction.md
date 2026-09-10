# Reference: Baseline Correction

## Overview

Baseline correction is a technique for removing the contribution of background signal from chromatographic peak areas. It improves accuracy by accounting for elevated baseline levels that would otherwise inflate integrated areas.

MANIC uses a **linear baseline subtraction** algorithm that fits a straight line through points at the edges of the integration window and subtracts the area under this line from the total peak area.

---

## How It Works

### Algorithm Steps

1. **Need six points.** If the window has fewer than 6 points, baseline correction is skipped.
2. **Collect edge samples.** Take the first 3 and last 3 points in the window (time and intensity).
3. **Fit one line.** Fit a degree-1 polynomial (`np.polyfit`) through those six points together. This is not a mean of each edge joined by a line.
4. **Trapezoid under the line.** Baseline area is $0.5 \times (B(t_{\mathrm{first}}) + B(t_{\mathrm{last}})) \times \mathrm{width}$, where $B(t)$ is the fitted line.
5. **Clamp the line at zero, then subtract.** Baseline values below zero contribute no area, so the baseline can only reduce peak area. Subtract that area from the peak area. A negative result is set to 0.

### Mathematical Formulation

Let $(t_1, I_1), (t_2, I_2), (t_3, I_3)$ be the first three points and $(t_{n-2}, I_{n-2}), (t_{n-1}, I_{n-1}), (t_n, I_n)$ the last three. Fit

$$B(t) = st + c$$

so that the six points lie nearest that line in the least-squares sense.

$$\text{Area}_{baseline} = \tfrac{1}{2}\left(B(t_1) + B(t_n)\right) \times w$$

$w$ is the time span (time-based) or the unit-spacing width (legacy).

$$\text{Area}_{corrected} = \max\left(0,\ \text{Area}_{total} - \text{Area}_{baseline}\right)$$

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

The fit uses the same six edge points for time-based and legacy integration. Only the width used in the trapezoid changes.
