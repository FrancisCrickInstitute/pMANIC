# Reference: Natural Isotope Correction

In mass spectrometry, the signal for a biological molecule is spread across multiple mass channels due to the natural presence of heavy isotopes (¹³C ≈ 1.1%, ¹⁵N ≈ 0.4%, ³⁷Cl ≈ 24%, ⁸¹Br ≈ 49%, and others).   

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
To find the true abundances ($x$), MANIC solves the linear system at every timepoint:

$$x = A^{-1} \cdot b$$

This is a single solve of $A x = b$. There is no later scaling by the diagonal of $A$.

> **Changed in MANIC 5.0. Corrected Values differ from 4.x. Ratio sheets move by less than half a percentage point.**
>
> Versions up to 4.x performed the solve and then divided each isotopologue by
> the matching diagonal element of $A$, an extra step inherited from the legacy
> MATLAB flow. That step has no basis in $A x = b$ and inflated every channel by
> $1 / A_{jj}$.
>
> **What we measured.** Two lab datasets (dataset_1, 522 pairs; dataset_2,
> 2662 pairs) re-run through both corrections. 4.x equals 5.0 divided by
> $A_{jj}$ to a relative deviation of $3.6 \times 10^{-10}$. Corrected Values
> fall by a median of 18% and 26% (max 39%). Isotope Ratio, % Label
> Incorporation and % Carbons Labelled move by less than half a percentage
> point; the largest change found was an Isotope Ratio of 45.30% becoming
> 45.78%. This is because $A_{jj}$ varies by at most 3.3% across one
> compound's channels and a near-common factor cancels in a ratio.
> Abundances with an MRRF computed from MM files change by a median of about
> 0.1% (max 2.5%); the MRRF absorbs the shift. Abundances with an assumed MRRF
> of 1.0 fall by 15 to 35% and are labelled Relative in 5.0. The inflation
> tracks molecule size and derivatisation, not the number of labelled
> positions.
>
> **What this means for you.** Do not compare 4.x Corrected Values, or 4.x
> abundances of compounds without MM-file calibration, against 5.0 output;
> reprocess the older data with 5.0 first. Ratio sheets and calibrated nmol
> amounts from 4.x remain usable. The README's *Upgrading to MANIC 5* section
> has the full tables.

MANIC treats the tracer as 99% isotopically pure. One percent of labelled positions still carry the light isotope. That is a fixed constant, typical of commercial ¹³C tracers. Get in touch if your tracer differs.

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

> **Critical Assumption for TBDMS**
>
> For TBDMS derivatization, MANIC assumes the standard **[M-57]+ fragment** (loss of the t-butyl group) for the first derivatization group, but assumes any **additional** groups remain intact.
>
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

The envelope that enters this correction must be the same kind of measurement on every ion: the dense selected curves when chromatographic peak deconvolution fitted every non-empty ion, otherwise the raw in-window scans. See [Failed ions put the whole envelope on scans](Reference_Chromatographic_Peak_Deconvolution.md#failed-ions-put-the-whole-envelope-on-scans), and [One fit for display and integration](Reference_Chromatographic_Peak_Deconvolution.md#one-fit-for-display-and-integration) for how baseline correction fits in.

The **Show corrected data** preview (**Settings → General**, **Natural abundance** section) uses that same order on screen; [Natural Abundance Correction preview](Reference_Chromatographic_Peak_Deconvolution.md#natural-abundance-correction-preview) describes what it draws. Time-based Label Incorporation bars and the Corrected Values sheet use the same raw fit and integration path, so the spreadsheet number is the bar number. Legacy export remains scan-point based and uses different units. The toggle does not write `eic_corrected`. Export still fills that table when you export.

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

MM files (standard mixture) also supply an empirical background that MANIC subtracts from **% Label Incorporation** and **% Carbons Labelled**. See [Empirical Background Correction](Reference_Label_Incorporation_Carbon_Enrichment.md#1-empirical-background-correction). The **Corrected Values** sheet reports the corrected intensities ($x$) before that subtraction.
