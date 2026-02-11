# Workflow: Process External Data

## Overview
The **Process External Data** feature allows you to re-process external results using MANIC's algorithms, even if you have lost the original raw mass spectrometry files (CDFs).

It reads a **"Raw Values"** Excel file, pairs it with a **Compound List**, and generates a fully calculated result workbook (including Corrected Values, % Label, and Abundances).

---

## When to use this
Use this workflow **only** if:
1.  You have a correctly formatted compound list and an excel file with a sheet comparable to the "Raw Values" output from MANIC.
2.  You want to apply the MRRF calibration or Correction calculations.
3.  **You do not have the original .CDF files.** (If you *do* have the CDFs, please use the standard "Import Raw Data" workflow in Step 2, as it is more accurate).

---

## ⚠️ Scientific Limitation: Approximate Mode

Because the original raw time-series data is missing, MANIC cannot perform its standard **Per-Timepoint Correction**. Instead, it must use an **Approximate Mode**:

| Standard Workflow | Approximate Mode (Process External Data) |
| :--- | :--- |
| **1. Correct Timepoints** (Matrix algebra on every scan) | **1. Sum Totals** (Read integer areas from Excel) |
| **2. Integrate** ("Clean" peak area) | **2. Correct Totals** (Apply matrix algebra to the single sum) |

> **Impact:**
> * For clean, high-intensity peaks, the results are nearly identical (< 0.1% difference).
> * For messy or low-intensity peaks, this method is slightly less accurate because it cannot distinguish between baseline noise and true signal overlap.

---

## Procedure

### Prerequisites
* **Legacy Results File:** An Excel (`.xlsx`) or CSV file containing a table of uncorrected peak areas.
* **Matching Compound List:** A Compound Definition file (Step 1) that matches the metabolite names in your legacy file. This is required to provide the *Molecular Formulas* and *Label Atoms* needed for correction.

### Steps
1.  Navigate to **File → Process External Data...**.
2.  **Select Results File:** Browse to your inputs file.
3.  **Select Compound List:** Browse to the corresponding definition file.
4.  **Output Filename:** Choose where to save the new results (e.g., `reprocessed_results.xlsx`).
5.  Click **Run Update**.

### Result
MANIC will generate a new 5-sheet Excel workbook.
* **Raw Values:** Copied directly from your input file.
* **Corrected Values:** Recalculated using the Approximate Mode.
* **Abundances:** Recalculated using the internal standard from your Compound List.
