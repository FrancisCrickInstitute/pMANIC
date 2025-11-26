# Reference: Abundance Calculation & MRRF

## Overview
The **Abundances** sheet in the final export reports the absolute amount of each metabolite in your samples (in nanomoles).

This quantification relies on an **Internal Standard (IS)** to normalize for instrument variability (such as injection volume differences) and a **Metabolite Response Ratio Factor (MRRF)** to correct for the fact that different compounds ionize with different efficiencies.

---

## 1. The Abundance Formula

MANIC calculates the abundance for every metabolite in every sample using the following equation:

$$
\text{Abundance}_{met} = \frac{\text{Area}_{total} \times \text{Amount}_{IS}}{\text{Area}_{IS} \times \text{MRRF}}
$$

### Variable Definitions

| Variable | Description | Source |
| :--- | :--- | :--- |
| **$\text{Abundance}_{met}$** | The calculated amount (nmol). | Output Result |
| **$\text{Area}_{total}$** | The **Total Corrected Area** of the metabolite (Sum of all isotopologues). | *Corrected Values* Sheet |
| **$\text{Amount}_{IS}$** | The known amount of Internal Standard added to this specific sample. | Compound List (`int_std_amount`) |
| **$\text{Area}_{IS}$** | The **M+0 Corrected Area** of the Internal Standard. | *Corrected Values* Sheet |
| **MRRF** | The Metabolite Response Ratio Factor. | Calculated from Standards (see below) |

> **⚠️ Technical Note: M+0 vs. Total Area**
> To maintain strict compatibility with the legacy MATLAB algorithms:
> * **Target Metabolites** use the sum of **all** corrected isotopologues (`Total Signal`).
> * **The Internal Standard** uses **only the M+0** corrected isotopologue (`M+0 Signal`).

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
* **$\text{Area}_{IS, std}$**: M+0 corrected area of the Internal Standard in an MM file.
* **$\text{Conc}_{IS}$**: The known amount of Internal Standard in the mix (`amount_in_std_mix`).

### Interpretation
* **MRRF = 1.0**: The metabolite and internal standard have identical ionization efficiency.
* **MRRF > 1.0**: The metabolite produces a stronger signal than the IS per unit of mass.
* **MRRF < 1.0**: The metabolite produces a weaker signal.

---

## 3. Data Requirements

For these calculations to execute, your **Compound List** must be populated with the following metadata. Missing values will cause the export to fail with an error.

| Column | Requirement | Usage in Formula |
| :--- | :--- | :--- |
| `int_std_amount` | **Sample Dose.** The amount of IS added to biological samples. | Used as $\text{Amount}_{IS}$ for normal samples. |
| `amount_in_std_mix` | **Calibration Dose.** The amount present in the Standard Mixture (MM) files. | Used to calculate MRRF slopes.<br>Also used as $\text{Amount}_{IS}$ if the sample itself is an MM file. |
| `mm_files` | **File Pattern.** (e.g., `*MM*`) | Identifies which files should be used to calculate the MRRF. |

### Dynamic Amount Switching
MANIC is "context-aware" regarding the Internal Standard amount:
1.  **For Biological Samples:** It uses `int_std_amount`.
2.  **For Standard Mixture (MM) Files:** It uses `amount_in_std_mix`.
This ensures that if you verify your standard files in the "Abundances" sheet, they are quantified correctly using their own specific concentration, even if it differs from the biological samples.

---

## 4. Special Cases

### The Internal Standard Itself
In the Abundances sheet, the row for the Internal Standard compound does not undergo calculation. Instead, it simply reports the **Known Amount** (`int_std_amount` or `amount_in_std_mix`) to confirm what value was used for that sample.

### Missing Calibration
If a metabolite cannot be calibrated (e.g., it was not found in the MM files, or `amount_in_std_mix` was 0), MANIC defaults the MRRF to **1.0** and logs a warning. The calculated abundances will essentially be relative to the IS but not absolutely quantified.
