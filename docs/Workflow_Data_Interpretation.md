# Workflow: Data Interpretation

## Overview
When you export data from MANIC (Step 5), the application generates a multi-sheet Excel workbook. This document explains the purpose, units, and derivation logic for each sheet in that report.

---

## 1. Raw Values
**Description:** The direct area-under-the-curve (AUC) for each peak, summed from the extracted ion chromatogram.

* **Correction:** None. These are raw signals.
* **Units:** Arbitrary Counts (Intensity × Time).
    * *Note:* If using "Legacy Mode," values will be ~100× larger than "Time-Based" values.
* **Use Case:** Quality control. Use this to check if a sample had low overall signal or injection issues.

> **📖 Deep Dive:**
> Understand the mathematical difference between Time-Based and Legacy integration in **[Reference: Integration Methods](Reference_Integration_Methods.md)**.

---

## 2. Corrected Values
**Description:** The "pure" peak areas after the **Natural Isotope Abundance Correction** has been applied.

* **Correction:** Mathematically deconvoluted to remove signal from naturally occurring heavy isotopes (¹³C, etc.).
* **Units:** Arbitrary Counts (Intensity × Time).
* **Use Case:** This is your primary dataset for relative quantification if you are not using an internal standard. It represents the true experimental label distribution.

> **Why are some values small/zero?**
> The correction algorithm subtracts the "natural" contribution. If a peak is entirely due to natural background (unlabelled), the corrected value for heavier isotopologues will properly be zero.

> **📖 Deep Dive:**
> Learn how the matrix-based correction algorithm works in **[Reference: Natural Isotope Correction](Reference_Natural_Isotope_Correction.md)**.

---

## 3. Isotope Ratios
**Description:** The normalized distribution of isotopologues for each compound.

* **Calculation:** Each isotopologue's corrected area divided by the total corrected area for that compound.

    $$\text{Ratio}_i = \frac{\text{Area}_i}{\sum \text{Area}_{total}}$$

* **Units:** Unitless fraction (Sum of all isotopologues = 1.0).
* **Use Case:** Comparing labelling patterns (e.g., "M+3 enrichment") across samples with different concentrations. Since it is normalized, it is independent of the total amount of metabolite.

---

## 4. % Label Incorporation
**Description:** The percentage of the total metabolite pool that contains the experimental label.

* **Correction:** Includes a background subtraction derived from your Standard Mixture (MM) files to account for impurities.
* **Units:** Percentage (0–100%).
* **Formula:**

    $$\% \text{Label} = \frac{\text{Labelled}_{corrected}}{\text{Total}_{original}} \times 100$$

* **Use Case:** Quickly assessing how "labelled" a specific pool is.

---

## 5. % Carbons Labelled
**Description:** The percentage of *excess* label incorporated into the carbon pool, relative to the Standard Mixture (MM) background. This is also known as **Atom Percent Excess**.

* **Units:** Percentage (0–100%).
* **Calculation:**
    1. Calculate weighted enrichment of the sample:
       $$\text{Enrichment}_{sample} = \frac{\sum (i \times \text{Area}_i)}{N \times \sum \text{Area}_{total}} \times 100$$
    2. Calculate weighted enrichment of Standard Mixture (MM) files (averaged if multiple).
    3. Subtract the background:
       $$\text{APE} = \max(0, \text{Enrichment}_{sample} - \text{Enrichment}_{MM})$$

    Where:
    * $i$ is the isotopologue number (0, 1, 2...).
    * $N$ is the maximum number of labelable atoms in the molecule.
    * Area is the **Corrected Value** (NAC applied).

* **Use Case:** Answers "How much of the carbon in this pool came from my labelled substrate?" by removing any natural or background enrichment present in the standards.

> **Note:** Standard Mixture (MM) samples will display 0% APE since their enrichment equals the baseline. This is expected behaviour.

---

## 6. Abundances
**Description:** The absolute amount of metabolite present in the sample.

* **Units:** **nmol**.
* **Calculation:** Derived relative to the **Internal Standard** using the **MRRF** (Metabolite Response Ratio Factor) determined from your standard curves.
* **Requirements:**
    * An Internal Standard must be selected.
    * `int_std_amount` and `amount_in_std_mix` must be defined in your Compound List.

> **📖 Deep Dive:**
> For the full derivation of the formula and how MRRF slopes are calculated, see **[Reference: Abundance Calculation](Reference_Abundance_Calculation.md)**.

---

## Color Codes & Validation
MANIC automatically validates every peak during export. You may see coloured cells in your Excel file:

* **⚪ White (Normal):** Valid peak. Area > Threshold.
* **🔴 Light Red (Warning):** **Low Intensity.**
    * The total peak area was less than **5%** (default) of the Internal Standard's area.
    * *Action:* Check the raw chromatogram. This data may be noise.

> **📖 Deep Dive:**
> See **[Reference: Peak Validation](Reference_Peak_Validation.md)** for details on threshold algorithms and how to adjust them.
