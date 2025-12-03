# Reference: Natural Isotope Correction

## Overview
In mass spectrometry, the signal for a biological molecule is spread across multiple mass channels due to the natural presence of heavy isotopes (¹³C ≈ 1.1%, ¹⁵N ≈ 0.4%, etc.).   

For example, even a completely unlabelled metabolite will produce a signal at **M+0** (100%), **M+1** (~6%), and **M+2** (~0.5%).   

To quantify experimental labelling accurately, MANIC must mathematically remove this "natural background" spread. It uses a **Matrix-Based Deconvolution** algorithm to solve for the true abundance of each labelled isotopologue.   

---

## 1. The Algorithm (Matrix Inversion)

MANIC models the relationship between the **Measured Raw Signal ($b$)** and the **True Isotopologue Abundance ($x$)** as a linear system:   

$$A \cdot x = b$$

Where:
* **$b$ (Vector):** The raw intensities measured by the instrument at M+0, M+1, M+2, etc.
* **$x$ (Vector):** The unknown "true" amounts of unlabelled (M+0), 1-labelled (M+1), etc.
* **$A$ (Matrix):** The **Correction Matrix**. Each column $j$ represents the theoretical isotopic distribution of a compound with exactly $j$ labels.

### The Solution
To find the true abundances ($x$), MANIC inverts the matrix (or solves the system) for every timepoint:

$$x = A^{-1} \cdot b$$

### Why this matters
Unlike simpler "subtraction" methods, this approach correctly handles **overlapping distributions**. For example, the M+2 bin contains signal from:
1.  True 2-labelled compound.
2.  Natural isotope tail of the 1-labelled compound.
3.  Natural isotope tail of the unlabelled compound.
The matrix solver disentangles all these contributions simultaneously.

---

## 2. Correction Matrix Construction

The matrix $A$ is built dynamically for each compound based on its **Molecular Formula** and **Labeling Constraints**.

### Inputs
The algorithm requires the following metadata from your Compound List:
1.  **Formula:** (e.g., `C6H12O6`)
2.  **Derivatization Counts:** (TBDMS, MeOX, Me)
3.  **Label Element:** (e.g., `C`)
4.  **Label Atoms:** The maximum number of labelable positions (e.g., `6` for Glucose).

### Derivatization Adjustments
Before building the matrix, MANIC adjusts the molecular formula to include the atoms added by chemical derivatization.   

> **⚠️ Critical Assumption for TBDMS**
> For TBDMS derivatization, MANIC assumes the standard **[M-57]+ fragment** (loss of the t-butyl group) for the first derivatization group, but assumes any **additional** groups remain intact.
> * **First Group:** Loss of reactive hydrogen (-1 H), addition of TBDMS (+15 H), and loss of t-butyl fragment (-9 H).
> * **Additional Groups:** Standard replacement of Hydrogen with TBDMS.

| Group | Added Formula (Approx) | Net Atom Change |
| :--- | :--- | :--- |
| **Me** (Methylation) | $-CH_2$ | +1 C, +2 H (per group) |
| **MeOX** (Methoxyamine) | $=N-O-CH_3$ | +1 C, +3 H, +1 N (per group) |
| **TBDMS (1st Group)** | $-Si(CH_3)_2$ ([M-57]+) | **+2 C, +5 H, +1 Si** |
| **TBDMS (2nd+ Groups)** | $-Si(CH_3)_2C_4H_9$ (Intact) | **+6 C, +14 H, +1 Si** (per additional group) |

---

## 3. Per-Timepoint Correction

A key feature of MANIC (compared to the legacy v3.3.0 tool) is that this correction is applied **before integration**.   

* **Legacy:** Integrate raw M+0, M+1, M+2 peaks $\rightarrow$ Apply correction to the total areas.
* **MANIC:** Apply correction to every scan (timepoint) $\rightarrow$ Integrate the "Corrected Chromatogram."

This provides higher accuracy because it prevents baseline noise or interfering peaks at specific timepoints from skewing the global correction.   

---

## 4. Interpretation of Results

The values in the **Corrected Values** sheet represent the **Calculated Abundance of the Isotopologue**, not just the "cleaned" raw signal.   

### Example: Unlabeled Compound
If you analyze a purely unlabeled standard:
* **Raw Signal ($b$):** You see 100 counts at M+0.
* **Natural Physics:** We know M+0 is only ~92% of the total pool for this molecule (due to natural ¹³C).
* **Corrected Value ($x$):** MANIC calculates the "True Unlabeled Amount" as $100 / 0.92 \approx 109$.

**Result:** Corrected values for M+0 are typically **higher** than raw values because they account for the signal "lost" to natural heavy isotopes.   

### Non-Negativity
The algorithm enforces a non-negativity constraint. If noise causes the mathematical solution to be negative (e.g., $-0.5$), it is clamped to **0**.   

---

## 5. Empirical Background Correction (MM Files)

In addition to the theoretical matrix correction described above, MANIC applies an **Empirical Background Correction** to the final "% Label Incorporation" and "% Carbon Labelled" results.

### Why is this needed?
Even after theoretical correction, "unlabelled" standards (MM files) often show a small residual amount of "labelled" signal due to:
* Impurities in the standard.
* Imperfections in the theoretical natural abundance constants.
* Instrument noise or baseline integration errors.

### How it works
1.  **Calculate Base Level:** MANIC scans all files matching the `mm_files` pattern for a compound. It calculates the average ratio of **Corrected Labelled / Corrected M+0** in these standards.
2.  **Subtract Base Level:** This "Background Ratio" is subtracted from the labeled/unlabeled ratio of every biological sample before the final "% Label Incorporation" & "% Carbon Labelled" is calculated.

$$\text{Label Signal}_{final} = \text{Label Signal}_{raw} - (\text{Ratio}_{background} \times \text{M+0 Signal}_{sample})$$

*Note: This correction specifically affects the **% Label Incorporation** & **% Carbon Labelled** sheets. The **Corrected Values** sheet reports the raw corrected intensities ($x$) before this background subtraction.*
