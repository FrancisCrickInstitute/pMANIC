# Reference: Abundance Calculation & MRRF

## Overview
The **Abundances** sheet in the final export reports the absolute amount of each metabolite in your samples (in nanomoles), relative ratios, or raw peak areas depending on your configuration.

This quantification typically relies on an **Internal Standard (IS)** to normalize for instrument variability and a **Metabolite Response Ratio Factor (MRRF)** to correct for ionization efficiency.

---

## 1. The Abundance Formulas

MANIC selects the mathematical path based on the metadata provided in your compound list and whether an Internal Standard is selected.

### Path A: Absolute Abundance (nmol)
Used when an Internal Standard is selected and the metabolite has an `amount_in_std_mix > 0`.

$$
\text{Abundance}_{abs} = \frac{\text{Area}_{total} \times \text{Amount}_{IS}}{\text{Area}_{IS} \times \text{MRRF}}
$$

### Path B: Relative Abundance
Used when an Internal Standard is selected, but the metabolite has an `amount_in_std_mix` of 0 or missing. This bypasses the MRRF to avoid inappropriate scaling.

$$
\text{Abundance}_{rel} = \frac{\text{Area}_{total} \times \text{Amount}_{IS}}{\text{Area}_{IS}}
$$

### Path C: Peak Area
Used when **No Internal Standard** is selected. This reports the raw integrated signal.

$$
\text{Abundance}_{area} = \text{Area}_{total}
$$

### Variable Definitions

| Variable | Description | Source |
| :--- | :--- | :--- |
| **Area_{total}** | The **Total Corrected Area** of the metabolite (Sum of all isotopologues). | *Corrected Values* Sheet |
| **Amount_{IS}** | The known amount of Internal Standard added to this specific sample. | Compound List (`int_std_amount`) |
| **Area_{IS}** | The **reference peak corrected area** of the Internal Standard (M+N, default M+0). | *Corrected Values* Sheet |
| **MRRF** | The Metabolite Response Ratio Factor. | Calculated from Standards |

---

## 2. The MRRF Calculation

The **Metabolite Response Ratio Factor (MRRF)** is a calibration slope calculated globally for the entire session. It determines how "loud" a metabolite's signal is compared to the internal standard.

MANIC scans all files matching your `mm_files` pattern (Standard Mixtures) to derive this factor.

### Formula

$$
\text{MRRF} = \frac{ \text{Mean Response}_{met} }{ \text{Mean Response}_{IS} }
$$

Expanded:

$$
\text{MRRF} = \frac{ \text{Mean} \left( \frac{\text{Area}_{total, std}}{\text{Conc}_{std}} \right) }{ \text{Mean} \left( \frac{\text{Area}_{IS, std}}{\text{Conc}_{IS}} \right) }
$$

* **$\text{Area}_{total, std}$**: Total corrected area of the metabolite in a Standard Mixture (MM) file.
* **$\text{Conc}_{std}$**: The known amount defined in `amount_in_std_mix`.
* **$\text{Area}_{IS, std}$**: Reference peak corrected area of the Internal Standard (M+N) in an MM file.
* **$\text{Conc}_{IS}$**: The known amount of Internal Standard in the mix (`amount_in_std_mix`).

### Interpretation
* **MRRF = 1.0**: The metabolite and internal standard have identical ionization efficiency.
* **MRRF > 1.0**: The metabolite produces a stronger signal than the IS per unit of mass.
* **MRRF < 1.0**: The metabolite produces a weaker signal.

---

## 3. Internal Standard Reference Peak

By default MANIC uses the internal standard **M+0** peak as the reference peak for normalization, peak validation, and MRRF calculation.

If your internal standard is labelled, you can change this in:

**Settings → Labelled Internal Standard...**

Changing the internal standard compound resets the reference peak back to **M+0**.

## 3. Data Requirements

| Column | Requirement | Usage in Formula |
| :--- | :--- | :--- |
| `int_std_amount` | **Sample Dose.** | Used as Amount_{IS} for normal samples. |
| `amount_in_std_mix` | **Calibration Dose.** | Used to calculate MRRF. If 0, the metabolite uses "Relative" mode. |

### Dynamic Amount Switching
MANIC is "context-aware" regarding the Internal Standard amount:
1.  **For Biological Samples:** It uses `int_std_amount`.
2.  **For Standard Mixture (MM) Files:** It uses `amount_in_std_mix`.
This ensures that if you verify your standard files in the "Abundances" sheet, they are quantified correctly using their own specific concentration, even if it differs from the biological samples.


---

## 4. Special Cases

### The Internal Standard Itself
In the Abundances sheet, the row for the Internal Standard compound does not undergo calculation. Instead, it simply reports the **Known Amount** (`int_std_amount` or `amount_in_std_mix`) to confirm what value was used for that sample.

### No Internal Standard Selected
If you clear the internal standard selection, MANIC will export the sum of corrected isotopologue areas for all compounds. The units in the Excel header will automatically change to **"Peak Area"**.

### Missing Calibration
If a metabolite has no `amount_in_std_mix` defined, it is treated as **Relative**. It is normalized to the Internal Standard signal but is not scaled by an MRRF.
