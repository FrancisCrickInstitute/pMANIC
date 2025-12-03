# Reference: Label Incorporation & Carbon Enrichment

## Overview

MANIC produces two distinct metrics to quantify isotopic labelling. While they are related, they answer different biological questions:

1.  **% Label Incorporation:** Answers the binary question *"How much of the pool contains **any** label?"*
2.  **% Carbons Labelled:** Answers the stoichiometric question *"How much of the total carbon atoms in this pool came from the labelled substrate?"*

**Important:** These metrics are calculated using data that has already undergone **Theoretical Natural Isotope Correction**.

In addition to that theoretical correction, both metrics rely on **Empirical Background Correction** using your Standard Mixture (MM) files to remove residual instrument noise and impurity.

---

## 1. Empirical Background Correction

Before calculating either metric, MANIC establishes a "base level" using the files defined in the `mm_files` column.

Even after theoretical natural isotope correction, "unlabelled" standards (MM files) often show a small residual amount of "labelled" signal due to instrument noise. MANIC calculates the average background signal in the MM files and subtracts it from the biological samples to ensure that unlabelled controls report as **0%**.

> **Note:** If no MM files are defined for a compound, the base level defaults to 0.

---

## 2. % Label Incorporation

This metric represents the percentage of the total metabolite pool that contains **at least one** heavy isotope. It does not distinguish between a molecule with 1 label (M+1) and a molecule with 6 labels (M+6).

### The Calculation

The calculation isolates the labeled signal and removes the background noise ratio found in the MM files.

$$\text{Labelled Signal}_{corr} = \sum_{i=1}^{N} \text{Area}_{M+i} - (\text{Ratio}_{MM} \times \text{Area}_{M+0})$$

$$\text{% Label Inc} = \frac{\text{Labelled Signal}_{corr}}{\text{Total Area}} \times 100$$

**Where:**
* **$\sum \text{Area}_{M+i}$**: The sum of all labelled isotopologues (M+1 to M+N).
* **$\text{Ratio}_{MM}$**: The average ratio of $(\text{Labelled} / \text{M+0})$ found in the Standard Mixture files.
* **$\text{Total Area}$**: The sum of all isotopologues (M+0 to M+N).

The result is clamped to **0%** if the subtraction results in a negative number.

---

## 3. % Carbons Labelled (Carbon Enrichment)

The **% Carbons Labelled** is a metric that quantifies the *excess* isotopic labelling within a metabolite pool, relative to the Standard Mixture (MM) background.

### The Calculation

The calculation is performed in two steps:

### Step 1: Calculate Weighted Enrichment

For each sample, calculate the weighted average enrichment on the **Natural Isotope Abundance Corrected** data:

$$\text{Enrichment}_{sample} = \frac{\sum_{i=0}^{N} (i \times \text{Area}_{M+i})}{N \times \sum_{i=0}^{N} \text{Area}_{M+i}} \times 100$$

**Where:**
* **$i$**: The isotopologue number (number of labelled atoms).
    * M+0 has weight 0.
    * M+1 has weight 1.
    * M+6 has weight 6.
* **$N$**: The total number of labelable atoms in the molecule (e.g., 6 for Glucose).
* **$\text{Area}_{M+i}$**: The corrected peak area for the $i$-th isotopologue.

### Step 2: Subtract Background

Calculate the same enrichment for all Standard Mixture (MM) files, average them, then subtract:

$$\text{% Carbon Labelled} = \max(0, \text{Enrichment}_{sample} - \text{Enrichment}_{MM})$$

The result is clamped to 0 to prevent negative values.

---

## Conceptual Comparison

Consider **Glucose** (6 Carbons, $N=6$) with a theoretical MM background of **0%**.

### Scenario A: Light Labelling
Every molecule in the pool contains exactly one <sup>13</sup>C atom (100% M+1).

* **% Label Incorporation:** **100%**
    * *Reason:* Every molecule has "some" label.
* **% Carbons Labelled:** **16.7%**
    * *Calculation:* $(1 \times 100) / (6 \times 100) = 1/6$.
    * *Reason:* Only 1 out of 6 carbons is labelled.

### Scenario B: Heavy Labelling
Every molecule in the pool contains six <sup>13</sup>C atoms (100% M+6).

* **% Label Incorporation:** **100%**
    * *Reason:* Every molecule has "some" label.
* **% Carbons Labelled:** **100%**
    * *Calculation:* $(6 \times 100) / (6 \times 100) = 1$.
    * *Reason:* All carbons are labelled.

### Scenario C: Mixed Pool (50/50)
The pool is a 50/50 mix of Unlabelled (M+0) and Fully Labelled (M+6).

* **% Label Incorporation:** **50%**
    * *Reason:* Half the molecules have a label.
* **% Carbons Labelled:** **50%**
    * *Reason:* Half the total carbon atoms in the jar are <sup>13</sup>C.
