# Reference: Natural Isotope Correction

## Overview
In mass spectrometry, the signal for a biological molecule is spread across multiple mass channels due to the natural presence of heavy isotopes (¹³C ≈ 1.1%, ¹⁵N ≈ 0.4%, ³⁷Cl ≈ 24%, ⁸¹Br ≈ 49%, and others).   

For example, even a completely unlabelled metabolite will produce a signal at **M+0** (100%), **M+1** (~6%), and **M+2** (~0.5%).   

To quantify experimental labelling accurately, MANIC must mathematically remove this "natural background" spread. It uses a **Matrix-Based Deconvolution** algorithm to solve for the true abundance of each labelled isotopologue.   

---

## 1. The Algorithm (Matrix Inversion)

MANIC models the relationship between the **Measured Raw Signal ($b$)** and the **True Isotopologue Abundance ($x$)** as a linear system:   

$$A \cdot x = b$$

Where:
* **$b$ (Vector):** The integrated raw peak areas measured at M+0, M+1, M+2, etc.
* **$x$ (Vector):** The unknown "true" amounts of unlabelled (M+0), 1-labelled (M+1), etc.
* **$A$ (Matrix):** The **Correction Matrix**. Each column $j$ represents the theoretical isotopic distribution of a compound with exactly $j$ labels.

### The Solution
To find the true abundances ($x$), MANIC solves the linear system once for each compound in each sample, on the vector of integrated raw areas:

$$x = A^{-1} \cdot b$$

This is a single solve of $A x = b$. There is no later scaling by the diagonal of $A$.

> **⚠️ Changed in MANIC 5.0. Corrected Values differ from 4.x. This change alone moves the ratio sheets by less than half a percentage point. Correcting the integrated areas (section 3) moves them further for small peaks.**
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
> amounts from 4.x stay within the margins above for this change alone, but
> 5.0 also corrects the integrated areas instead of every scan (see
> [Correct the Integrated Areas](#3-correct-the-integrated-areas)), which moves
> the ratio sheets for small peaks. Reprocess older data with 5.0 before
> comparing any sheet. The README's *Upgrading to MANIC 5* section
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

## 3. Correct the Integrated Areas

MANIC integrates each raw isotopologue trace first, then corrects the integrated areas once. IsoCor and the legacy v3.3.0 tool use the same order.

1. Integrate the raw M+0, M+1, M+2 traces with the compound's normal integration: the integration window, baseline correction, legacy or time-based integration, and chromatographic peak deconvolution. These areas are the **Raw Values**.
2. Solve $A x = b$ once with those areas as $b$. Set any negative result to 0. The result is the **Corrected Values**.

The solve is linear, so correcting the areas gives the same answer as correcting every scan and then integrating, except for the step that sets negatives to 0. That step is why the order matters. In an isotopologue whose true amount is 0, noise swings above and below 0 from scan to scan. Setting each negative scan to 0 before integrating keeps only the positive swings, and that adds a false labelled signal. The smaller the peak, the larger the false label.

> **⚠️ Changed in MANIC 5.0. Corrected Values and the ratio sheets differ from 4.x and from 5.0.0-alpha, most for small peaks.**
> Versions up to 4.x, and 5.0.0-alpha, corrected every scan, set negative scans
> to 0, and then integrated the corrected traces. This added a false labelled
> signal to unlabelled samples. MM-file background subtraction cannot remove
> it, because the false label depends on peak height, and MM peaks and sample
> peaks differ in size.
>
> **What we measured.** Simulated unlabelled lactate (2 TBDMS, 3 label atoms)
> with shot noise and detector noise, baseline correction on, 200 replicates.
> At a 200,000-count apex the label shown fell from 0.12% to 0.03%; at 20,000
> counts, from 0.51% to 0.16%. When M+3 is scanned 0.3 of a scan after M+0,
> as on a quadrupole, the old order showed 0.47% and 0.62%, against 0.03% and
> 0.17% now.
>
> **What this means for you.** Corrected Values, Isotope Ratio,
> % Label Incorporation, % Carbons Labelled and Abundances change. Unlabelled
> and weakly labelled small peaks move the most. Raw Values do not change.
> Reprocess older data with this version before you compare it.

The areas that enter this correction must be the same kind of measurement on every ion. If chromatographic peak deconvolution fitted every non-empty ion of a compound in a sample, each area comes from the dense selected curve. Empty ions contribute zeros. If any ion with real intensity failed to fit, every non-empty ion of that pair is integrated from its raw in-window scans. Empty rows stay zero. See [Failed ions put the whole envelope on scans](Reference_Chromatographic_Peak_Deconvolution.md#failed-ions-put-the-whole-envelope-on-scans).

With baseline correction on, MANIC subtracts the baseline from each raw area before correction. A raw area that falls below zero after baseline subtraction is set to 0 before correction. See [Baseline Correction](Reference_Baseline_Correction.md).

**Settings → Natural Abundance** fits the raw traces, then draws the correction of every scan for the tiles when the compound has a correction formula and labelled atoms. Otherwise, the plot keeps the raw fitted view. Preview draws corrected values at the acquisition scan times. When deconvolution selects a fitted component, preview also retains a faint raw EIC for context. Peaks outside the selected component remain visible in that context but do not enter correction or integration. The corrected trace is a picture only: negative scans are drawn at 0, so it can show small positive blips in an isotopologue whose corrected area is 0. Time-based Isotopologue Ratio bars and the Corrected Values sheet both correct the integrated raw areas. Each bar is one isotopologue's corrected area divided by the sample's total, so it equals the Isotope Ratio sheet number. Legacy export uses unit-spacing integration and different units. Neither the toggle nor export writes `eic_corrected`, and export does not read it for any number. Before export, MANIC checks that it can correct every labelled compound from its raw traces.

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
After the solve, MANIC sets any negative corrected area (e.g., $-0.5$) to **0**. This applies to the integrated areas, not to each scan.

This is the step the MATLAB tool uses. It is not a constrained fit. A non-negative least-squares fit gives a different answer whenever a value would be negative, because it adjusts the other isotopologues to compensate. Setting the negatives to 0 leaves the other isotopologues as the unconstrained solve gave them.

---

## 5. Empirical Background Correction (MM Files)

In addition to the theoretical matrix correction described above, MANIC applies an **Empirical Background Correction** to the final "% Label Incorporation" and "% Carbon Labelled" results. MM files (standard mixture) supply that background.

### Why is this needed?
Even after theoretical correction, unlabelled MM files (standard mixture) often show a small residual amount of labelled signal due to:
* Impurities in the standard.
* Imperfections in the theoretical natural abundance constants.
* Instrument noise or baseline integration errors.

### How it works
1.  **Calculate Base Level:** MANIC scans all files matching the `mm_files` pattern for a compound. It calculates the average ratio of **Corrected Labelled / Corrected M+0** in these standards.
2.  **Subtract Base Level:** This "Background Ratio" is subtracted from the labeled/unlabeled ratio of every biological sample before the final "% Label Incorporation" & "% Carbon Labelled" is calculated.

$$\text{Label Signal}_{final} = \text{Label Signal}_{raw} - (\text{Ratio}_{background} \times \text{M+0 Signal}_{sample})$$

*Note: This correction specifically affects the **% Label Incorporation** & **% Carbon Labelled** sheets. The **Corrected Values** sheet reports the raw corrected intensities ($x$) before this background subtraction.*
