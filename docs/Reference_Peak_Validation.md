# Reference: Peak Validation

## Overview
MANIC includes an automated quality control system to identify weak or low-quality peaks.   

Instead of requiring you to manually inspect every chromatogram for noise, the software automatically flags peaks that fall below a minimum intensity threshold relative to your internal standard.

---

## 1. The Validation Rule

A peak is considered **Invalid/Weak** (and flagged red) if its total integrated area is too small compared to the Internal Standard in that same sample.  

> **⚠️ Requirement: Internal Standard**
> Automated validation requires an Internal Standard to be selected. If no standard is selected, all peaks are treated as "Valid" (white) by default.

### Formula
$$\text{Area}_{metabolite} < (\text{Area}_{IS} \times \text{Threshold})$$

* **$\text{Area}_{metabolite}$**: The total raw area of the target peak.
* **$\text{Area}_{IS}$**: The total raw area of the Internal Standard in the current sample.
* **$\text{Threshold}$**: The configurable percentage limit (Default: **0.05** or 5%).

### Example
* **Internal Standard Area:** 1,000,000
* **Threshold:** 5% (0.05)
* **Minimum Required Area:** 50,000

| Metabolite Area | Result | Status |
| :--- | :--- | :--- |
| **80,000** | $80,000 > 50,000$ | ✅ **Valid** (White) |
| **20,000** | $20,000 < 50,000$ | ❌ **Invalid** (Red) |

---

## 2. Visual Indicators

The validation status is communicated in two places:

### 1. In the Application (Step 4)
When reviewing integration, look at the background colour of the mini-plots:
* **⚪ White Background:** The peak is healthy.
* **🔴 Red Background:** The peak is weak.

### 2. In the Exported Excel File (Step 5)
In the final results workbook (specifically the **Abundances** sheet):
* **Normal Cells:** Valid data.
* **Red Cells:** The value was calculated, but the underlying peak failed validation. Treat these quantitative results with caution. This highlighting is disabled if no internal standard was used for the export.

---

## 3. Configuration

You can adjust the strictness of this check in the settings.

**Settings → Minimum Peak Area...**

* **Default:** `0.05` (5%)
* **Range:** `0.0` to `1.0`
* **Usage:**
    * Increase this value (e.g., to `0.10`) to be stricter and flag more peaks.
    * Decrease this value (e.g., to `0.01`) to accept weaker signals.
    * Set to `0.0` to disable validation warnings entirely.
