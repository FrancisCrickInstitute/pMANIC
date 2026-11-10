# Process External Data

The **Process External Data** feature allows you to re-process external results using MANIC's algorithms, even if you have lost the original raw mass spectrometry files (CDFs).

It reads a **Raw Values** workbook, pairs it with a compound list, and writes five sheets: **Raw Values**, **Corrected Values**, **Isotope Ratio**, **% Label Incorporation**, and **Abundances**.

It rebuilds labelled exports only, so the compound list needs **mass0** and **labelAtoms** columns. The start screen offers it in labelled sessions; **File → Process External Data...** offers it in both modes.

---

## When to use this
Use this workflow **only** if:

1.  You have a correctly formatted compound list and an excel file with a sheet comparable to the "Raw Values" output from MANIC.
2.  You want to apply the MRRF calibration or Correction calculations.
3.  **You do not have the original .CDF files.** If you do have the CDFs, use **File → Load Raw Data (CDF)** instead. That path is more accurate.

---

## Scientific Limitation: No Re-integration

Both workflows correct the integrated areas, so the correction is the same. Without the original raw time-series data, MANIC cannot redo the integration:

| Standard Workflow | Process External Data |
| :--- | :--- |
| **1. Integrate** (MANIC integrates the raw traces) | **1. Read Areas** (Take the areas from your workbook as they are) |
| **2. Correct** (Matrix algebra on the integrated areas) | **2. Correct** (The same matrix algebra on those areas) |

> **Impact:**
>
> * If your areas came from a MANIC export with the same settings, the Corrected Values match.
> * Otherwise they differ wherever the original integration differs from MANIC's: the window, baseline correction, deconvolution, or integration units.

---

## Procedure

### Prerequisites
* **Legacy Results File:** An Excel (`.xlsx`) workbook with a **Raw Values** sheet of uncorrected peak areas, laid out like MANIC's own Raw Values export. CSV files are not accepted. Each compound needs label atoms + 1 isotopologue columns. If a compound has a different number, the rebuild stops before writing anything and names that compound.
* **Matching Compound List:** A Compound Definition file (Step 1) that matches the metabolite names in your legacy file. This is required to provide the *Molecular Formulas* and *Label Atoms* needed for correction.

### Steps
1.  Choose **File → Process External Data...**.
2.  In **Process external data**, set **Compounds file** with **Browse…**.
3.  Set **Raw Values workbook** with **Browse…**. If a file cannot be used, the reason shows under its field and **Rebuild export…** stays off.
4.  Optionally choose an **Internal standard**. The list fills in once a compound list is chosen. A standard without both `int_std_amount` and `amount_in_std_mix` is listed under **No amount: exports peak areas**, and choosing it writes **Peak Area** abundances.
5.  Click **Rebuild export…**.
6.  In **Save Rebuilt Export**, choose the output workbook and save.

### Result
MANIC writes five sheets.

* **Raw Values:** Copied from your input workbook.
* **Corrected Values:** Recalculated from the areas in your workbook.
* **Isotope Ratio:** Normalized corrected values that sum to 1.0.
* **% Label Incorporation:** Experimental label percentages.
* **Abundances:** Recalculated using the optional internal standard from the dialog.
