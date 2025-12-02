# Reference: Carbon Enrichment Calculation

## Overview

The **% Carbons Labelled** (also known as Average Enrichment or Fractional Carbon Contribution) is a metric that quantifies the total extent of isotopic labelling within a metabolite pool.

Unlike **% Label Incorporation**, which answers the binary question "Is this molecule labelled?", Carbon Enrichment answers "How much of the carbon in this pool is labelled?".

---

## The Calculation

The calculation is a weighted average performed on the **Natural Isotope Abundance Corrected** data.

$$ \% \text{Enrichment} = \frac{\sum_{i=0}^{N} (i \times \text{Area}_{M+i})}{N \times \sum_{i=0}^{N} \text{Area}_{M+i}} \times 100 $$

**Where:**
* **$i$**: The isotopologue number (number of labelled atoms).
    * M+0 has weight 0.
    * M+1 has weight 1.
    * M+6 has weight 6.
* **$N$**: The total number of labelable atoms in the molecule (e.g., 6 for Glucose).
* **$\text{Area}_{M+i}$**: The corrected peak area for the $i$-th isotopologue.

---

## Conceptual Example

Consider **Glucose** (6 Carbons, $N=6$).

### Scenario A: Light Labelling
Every molecule in the pool contains exactly one <sup>13</sup>C atom (100% M+1).

* **% Label Incorporation:** 100% (Every molecule is "labelled").
* **% Carbons Labelled:**

$$ \frac{1 \times 100}{6 \times 100} \times 100 = \mathbf{16.7\%} $$

    *(Only 1 out of 6 carbons is labelled)*

### Scenario B: Heavy Labelling
Every molecule in the pool contains six <sup>13</sup>C atoms (100% M+6).

* **% Label Incorporation:** 100% (Every molecule is "labelled").
* **% Carbons Labelled:**

$$ \frac{6 \times 100}{6 \times 100} \times 100 = \mathbf{100\%} $$

    *(All 6 carbons are labelled)*

### Comparison
This metric allows you to distinguish between pathways that produce singly-labelled intermediates (e.g., certain TCA cycle fluxes) versus those that preserve intact carbon chains (e.g., gluconeogenesis from fully labelled precursors).

---

## Data Source

This calculation uses the **Natural Isotope Corrected** values.

1. **Raw Data** is extracted from the CDF files.
2. **Natural Correction** removes the signal from naturally occurring isotopes (1.1% <sup>13</sup>C).
3. **Enrichment** is calculated on the remaining signal.

*Note: Unlike "% Label Incorporation", this metric does not subtract the background signal found in Standard Mixture (MM) files. It represents the enrichment of the corrected experimental data.*
