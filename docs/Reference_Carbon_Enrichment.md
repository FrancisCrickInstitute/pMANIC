# Reference: Carbon Enrichment Calculation

## Overview

The **% Carbons Labelled** is a metric that quantifies the *excess* isotopic labelling within a metabolite pool, relative to the Standard Mixture (MM) background.

Unlike **% Label Incorporation**, which answers the binary question "Is this molecule labelled?", Carbon Enrichment answers "How much of the carbon in this pool came from my labelled substrate?".

---

## The Calculation

The calculation is performed in two steps:

### Step 1: Calculate Weighted Enrichment

For each sample, calculate the weighted average enrichment on the **Natural Isotope Abundance Corrected** data:

$$ \text{Enrichment}_{sample} = \frac{\sum_{i=0}^{N} (i \times \text{Area}_{M+i})}{N \times \sum_{i=0}^{N} \text{Area}_{M+i}} \times 100 $$

**Where:**
* **$i$**: The isotopologue number (number of labelled atoms).
    * M+0 has weight 0.
    * M+1 has weight 1.
    * M+6 has weight 6.
* **$N$**: The total number of labelable atoms in the molecule (e.g., 6 for Glucose).
* **$\text{Area}_{M+i}$**: The corrected peak area for the $i$-th isotopologue.

### Step 2: Subtract Background

Calculate the same enrichment for all Standard Mixture (MM) files, average them, then subtract:

$$ \text{% Carbon Labelled} = \max(0, \text{Enrichment}_{sample} - \text{Enrichment}_{MM}) $$

The result is clamped to 0 to prevent negative values.

---

## Conceptual Example

Consider **Glucose** (6 Carbons, $N=6$) with an MM background enrichment of **10%**.

### Scenario A: Light Labelling
Every molecule in the pool contains exactly one <sup>13</sup>C atom (100% M+1).

* **Absolute Enrichment:**

$$ \frac{1 \times 100}{6 \times 100} \times 100 = 16.7\% $$

* **% Carbons Labelled:**

$$ 16.7\% - 10\% = \mathbf{6.7\%} $$

### Scenario B: Heavy Labelling
Every molecule in the pool contains six <sup>13</sup>C atoms (100% M+6).

* **Absolute Enrichment:**

$$ \frac{6 \times 100}{6 \times 100} \times 100 = 100\% $$

* **% Carbons Labelled:**

$$ 100\% - 10\% = \mathbf{90\%} $$

### Scenario C: Standard Mixture Sample
The MM sample itself will always show **0%** since its enrichment equals the baseline.

---

## Why Subtract Background?

The Standard Mixture contains unlabelled compounds that may still show some enrichment due to:
- Natural <sup>13</sup>C abundance (1.1%) not fully removed by correction
- Instrument artifacts or matrix effects
- Trace contamination

By subtracting the MM baseline, you isolate only the *experimental* label incorporation.

---

## Data Source

This calculation uses the **Natural Isotope Corrected** values with MM background subtraction.

1. **Raw Data** is extracted from the CDF files.
2. **Natural Correction** removes the signal from naturally occurring isotopes (1.1% <sup>13</sup>C).
3. **Baseline Enrichment** is calculated from the Standard Mixture (MM) files.
4. **Carbon Enrichment** is calculated by subtracting the baseline from each sample's enrichment.

> **Note:** If no MM files are defined for a compound, the baseline defaults to 0% and absolute enrichment is reported.
