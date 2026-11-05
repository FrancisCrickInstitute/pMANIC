# Data Interpretation

When you export data from MANIC (Step 5), the application generates a multi-sheet Excel workbook. This document explains the labelled (isotope-tracing) sheets. Unlabelled sessions write **Raw Values** and **Abundances** in the same matrix layout, then add **Qualifier QC**. See [Unlabelled Targeted Analysis](Unlabelled_Targeted_Analysis.md#8-excel-export).

---

## 1. Raw Values
**Description:** The direct area-under-the-curve (AUC) for each peak, summed from the extracted ion chromatogram.

* **Correction:** None. These are raw signals.
* **Units:** Arbitrary Counts (Intensity × Time).
    * *Note:* If using "Legacy Mode," values will be ~100× larger than "Time-Based" values.
* **Use Case:** Quality control. Use this to check if a sample had low overall signal or injection issues.
* **Deconvolution:** When chromatographic peak deconvolution is on, these areas come from the selected model curve, or from the raw in-window scans when an ion of that compound and sample fails to fit. See [Failed ions put the whole envelope on scans](Reference_Chromatographic_Peak_Deconvolution.md#failed-ions-put-the-whole-envelope-on-scans).

[Integration Methods](Reference_Integration_Methods.md) compares Time-Based and Legacy integration.

---

## 2. Corrected Values
**Description:** The "pure" peak areas after the **Natural Isotope Abundance Correction** has been applied.

* **Correction:** Mathematically deconvoluted to remove signal from naturally occurring heavy isotopes (¹³C, etc.). When chromatographic deconvolution is on, this correction is applied to the same measurement used for Raw Values.
* **Units:** Arbitrary Counts (Intensity × Time).
* **Use Case:** This is your primary dataset for relative quantification if you are not using an internal standard. It represents the true experimental label distribution.

> **Why are some values small/zero?**
>
> The correction algorithm subtracts the "natural" contribution. If a peak is entirely due to natural background (unlabelled), the corrected value for heavier isotopologues will properly be zero.

[Natural Isotope Correction](Reference_Natural_Isotope_Correction.md) explains the matrix-based correction.

---

## 3. Isotope Ratio
**Description:** The normalized distribution of isotopologues for each compound.

* **Calculation:** Each isotopologue's corrected area divided by the total corrected area for that compound.

    $$\text{Ratio}_i = \frac{\text{Area}_i}{\sum \text{Area}_{total}}$$

* **Units:** Unitless fraction (Sum of all isotopologues = 1.0).
* **Use Case:** Comparing labelling patterns (e.g., "M+3 enrichment") across samples with different concentrations. Since it is normalized, it is independent of the total amount of metabolite.

---

## 4. % Label Incorporation
**Description:** The percentage of the total metabolite pool that contains the experimental label.

* **Correction:** Includes a background subtraction derived from your MM files (standard mixture) to account for impurities.
* **Units:** Percentage (0 to 100%).
* **Formula:**

    $$\% \text{Label} = \frac{\text{Labelled}_{corrected}}{\text{Total}_{original}} \times 100$$

* **Use Case:** Quickly assessing how "labelled" a specific pool is.

---

## 5. % Carbons Labelled (optional)
**Description:** Off by default. Tick **Include % Carbons Labelled sheet** in **Export Data** to write this sheet. It is the percentage of *excess* label incorporated into the carbon pool, relative to the MM files (standard mixture) background. This is also known as **Atom Percent Excess**.

* **Units:** Percentage (0 to 100%).
* **Calculation:**
    1. Calculate weighted enrichment of the sample:

        $$\text{Enrichment}_{sample} = \frac{\sum (i \times \text{Area}_i)}{N \times \sum \text{Area}_{total}} \times 100$$

    2. Calculate weighted enrichment of MM files (standard mixture), averaged if there are several.
    3. Subtract the background:

        $$\%\ \text{Carbon Labelled} = \max(0, \text{Enrichment}_{sample} - \text{Enrichment}_{MM})$$

    Where:

    * $i$ is the isotopologue number (0, 1, 2...).
    * $N$ is the maximum number of labelable atoms in the molecule.
    * Area is the **Corrected Value** (NAC applied).

* **Use Case:** Answers "How much of the carbon in this pool came from my labelled substrate?" by removing any natural or background enrichment present in the standards.

> **Note:** MM files (standard mixture) display 0% carbon labelled because their enrichment equals the baseline. This is expected behaviour.

---

## 6. Abundances
**Description:** The absolute amount of metabolite present in the sample.

* **Units:** **nmol** when an internal standard and `amount_in_std_mix` are set. **Relative** when an internal standard is set but `amount_in_std_mix` is missing or 0. **Peak Area** when no internal standard is selected.
* **Calculation:** Derived relative to the **Internal Standard** using the **MRRF** (Metabolite Response Ratio Factor) determined from MM files (standard mixture).
* **Requirements:**
    * An Internal Standard must be selected.
    * `int_std_amount` and `amount_in_std_mix` must be defined in your Compound List.

[Abundance Calculation](Reference_Abundance_Calculation.md) derives the formula and the MRRF slopes.

---

## Color Codes & Validation
MANIC automatically validates every peak during export. You may see coloured cells in your Excel file:

* **⚪ White (Normal):** No warning/flag applied.
* **🔴 Light Red (Warning):** **Low Intensity.**
    * The peak area was less than **0.5%** (default) of the Internal Standard reference peak area.
    * *Action:* Check the raw chromatogram. This data may be noise.
* **🟣 Light Purple (Reviewed):** **Accepted below threshold.** You chose *Accept Peak (Below Threshold)* for this peak from the plot right-click menu or the **Review** menu. The value is kept and the colour records the manual decision. The colour stays until you clear the review.
* **🟤 Tan (Reviewed):** **Marked as bad.** You chose *Mark Peak as Bad* for this peak. The value is still exported; the colour flags it for exclusion downstream.
* **🔵 Blue text (Info):** **Baseline correction disabled** for this compound.
    * The compound name in the header row is written in blue across sheets.
    * This corresponds to the compound's **Baseline correction** checkbox being unchecked in the UI.
* **⬜ Grey (Info):** **Relative units** in the **Abundances** sheet.
    * In the Abundances sheet "Units" row, a grey cell indicates the value is reported as `Relative`/`rel` rather than `nmol`.

[Peak Validation](Reference_Peak_Validation.md) covers the threshold and how to change it.
