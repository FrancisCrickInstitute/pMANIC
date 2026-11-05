# Peak Validation

MANIC includes an automated quality control system to identify weak or low-quality peaks.   

Instead of requiring you to manually inspect every chromatogram for noise, the software automatically flags peaks that fall below a minimum intensity threshold relative to your internal standard.

---

## 1. The Validation Rule

A peak is considered **Invalid/Weak** (and flagged **Below threshold**) if its total integrated area is too small compared to the Internal Standard in that same sample.  

> **Requirement: Internal Standard**
>
> Automated validation requires an Internal Standard to be selected. If no standard is selected, no peak gets a **Below threshold** badge.

### Formula
$$\text{Area}_{metabolite} < (\text{Area}_{IS} \times \text{Threshold})$$

* **$\text{Area}_{metabolite}$**: The total raw area of the target peak.
* **$\text{Area}_{IS}$**: The internal standard reference peak area (M+N, default M+0) in the current sample.
* **$\text{Threshold}$**: The configurable limit set under [Configuration](#3-configuration).

### Example
* **Internal Standard Area:** 1,000,000
* **Threshold:** 0.5% (0.005)
* **Minimum Required Area:** 5,000

| Metabolite Area | Result | Status |
| :--- | :--- | :--- |
| **8,000** | $8,000 > 5,000$ | ✅ **Valid** (no badge) |
| **2,000** | $2,000 < 5,000$ | ❌ **Invalid** (Below threshold) |

---

## 2. Visual Indicators

The validation status is communicated in two places:

### 1. In the Application (Step 4)
When reviewing integration, look under each plot's sample name:

* **No badge:** The peak is healthy.
* **Below threshold** (light red badge and tile): The peak is weak. Right-click the plot, or open the **Review** menu, and choose **Accept Peak (Below Threshold)** or **Mark Peak as Bad** to record a decision. The badge then reads **Accepted** (light purple) or **Marked bad** (tan).

### 2. In the Exported Excel File (Step 5)
Every sheet of the results workbook fills a peak's cells by its status:

* **No fill:** Valid data.
* **Light red:** The value was calculated, but the underlying peak failed validation. Treat these quantitative results with caution.
* **Light purple** or **tan:** You accepted the peak or marked it as bad.

---

## 3. Configuration

You can adjust the strictness of this check in the settings.

**Settings → Peak validation**, **Minimum area ratio**

* **Default:** `0.005` (0.5%)
* **Range:** `0` to `1.0`. `0` turns the check off.
* **Usage:**
    * Increase this value (e.g., to `0.05`) to be stricter and flag more peaks.
    * Decrease this value (e.g., to `0.001`) to accept weaker signals.

If your internal standard is labelled, you can choose which isotopologue peak is the reference peak:

**Settings → Internal standard**, **Reference peak**
