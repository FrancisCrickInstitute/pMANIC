# Reference: Mass Tolerance

## Overview
Mass spectrometers detect ions with high precision (e.g., `204.8723` Da), but analytical workflows typically bin these values into integer mass units (e.g., `205` Da) to group related signals.

The **Mass Tolerance** setting controls how this binning occurs. It is a critical parameter that corrects for the systematic mass calibration drift often observed in GC-MS instruments, where fragment ions tend to drift slightly higher than their theoretical integer values.

---

## The Binning Algorithm

MANIC uses an **Asymmetric Offset-and-Round** algorithm. This is mathematically identical to the method used in the legacy MATLAB tool (GVISO) to ensuring data consistency.

### Concept
Instead of a symmetric window (e.g., `205 ± 0.2`), MANIC subtracts a fixed offset from the detected mass before rounding to the nearest integer. This effectively creates a "capture window" that is shifted to lower masses.

### Formula
For a detected mass $m$ and a tolerance offset $\tau$:   

1.  **Offset:** Subtract the tolerance from the detected mass.
    $$m' = m - \tau$$
2.  **Round:** Round the result to the nearest integer (using half-up rounding).
    $$M_{bin} = \lfloor m' + 0.5 \rfloor$$

### Example
**Target Mass:** 205 Da   
**Tolerance Setting:** 0.2 Da   

| Detected Mass | Calculation ($m - 0.2$) | Rounded Integer | Result |
| :--- | :--- | :--- | :--- |
| **204.7** | $204.5$ | **205** | ✅ Match |
| **204.8** | $204.6$ | **205** | ✅ Match |
| **205.0** | $204.8$ | **205** | ✅ Match |
| **205.6** | $205.4$ | **205** | ✅ Match |
| **205.7** | $205.5$ | **206** | ❌ No Match |

**Resulting Window:** The effective window for "205" is approximately **204.7 to 205.7**. This captures ions that have drifted up to +0.7 Da higher than expected, which is common in quadrupole instruments.

---

## Configuration

**Settings → Mass Tolerance...**   

* **Default:** `0.20 Da`
* **Range:** `0.01` to `1.00` Da
* **Impact:** This setting is applied during the **Import Raw Data (CDF)** step.
    * If you change this setting, you **must** re-import your CDF files for the change to take effect.
    * Plots and integrations will not update automatically until the underlying data is re-extracted.

---

## Appendix: Legacy Comparison (Technical Note)

For users migrating from the MATLAB version of MANIC (v3.3.0), there is a known but minor discrepancy in how **duplicate peaks** are handled within a single scan.

### The Scenario
Instruments may record multiple peaks within a single scan that all round to the same integer bin (e.g., peaks at `204.8` and `205.1` both bin to `205`).

### Handling Difference
* **Python (Current):** Sums the intensity of all peaks falling into the bin. This is the theoretically correct approach (conserving total ion current).
* **MATLAB (Legacy):** Due to an array indexing quirk, it retains only the *last* peak encountered, discarding the others.

### Impact
In datasets where these "duplicate" peaks are frequent, the Python version may report **Raw Values** that are higher than the legacy tool.
