# Sum vs Last-Wins: Mass Binning Discrepancy

## Overview

Python MANIC produces raw values that are 10-55% higher than MATLAB MANIC for the same data (Glycerol). The root cause is a fundamental difference in how the two implementations handle duplicate mass peaks that round to the same integer m/z bin within a single scan.

**Status**: Identified but not yet fixed in Python version.

---

## The Problem in Words

When a mass spectrometer scans a sample, it produces multiple centroid peaks (mass/intensity pairs) per scan. These peaks need to be binned into integer m/z values for analysis. Modern instruments often produce multiple centroid peaks that round to the same integer bin.

For example, in a single scan you might detect:
- Peak at m/z 204.8 with intensity 1000
- Peak at m/z 205.1 with intensity 500

Both peaks round to integer m/z 205 (after applying the -0.2 offset and rounding).

**MATLAB behavior**: Keeps only the **last** intensity value (500)
**Python behavior**: **Sums** both intensity values (1500)

This 3× difference accumulates across all scans in the integration window, leading to systematically higher raw values in Python. The effect varies by compound depending on how many duplicate peaks occur in practice.

---

## Code Locations

### MATLAB Implementation

**File**: `oldmanic/MANIC/inputs/cdf/loadncGv3.m`
**Lines**: 77-87

```matlab
% converting m/z ratios to proper number (getting rid of the 1.7 x 10^-4
% tail ends - TODO: document?
mzind = mzind - 0.2; % needed to report accurate unit masses for larger fragments
mzindround = round(mzind);
mzimat = zeros(1000, length(TIC));
for q = 1 : length(TIC)
    if q == length(TIC)
        ind = (scanIndex(q) + 1) : length(TIC);
    else
        ind = (scanIndex(q) + 1) : (scanIndex(q + 1));
    end
    mzimat(mzindround(ind), q) = mzval(ind);  % ← ASSIGNMENT (last-wins)
end
```

**Key**: Line 86 uses **assignment** (`=`), not accumulation. When `mzindround(ind)` contains duplicate values (e.g., `[205, 205, 206]`), MATLAB's array indexing keeps only the **last** value assigned to each row.

---

### Python Implementation

**File**: `src/manic/io/eic_importer.py`
**Lines**: 216-230

```python
# Precompute MATLAB-aligned half-up rounding of (mass - offset)
offset_masses = all_relevant_mass - mass_tol
rounded_masses = np.floor(offset_masses + 0.5).astype(int)
target_mzs_int = np.floor(target_mzs + 0.5).astype(int)

for label in label_ions:
    target_int = target_mzs_int[label]
    # MANIC's asymmetric mass tolerance method: offset + half-up rounding
    mask = (rounded_masses == target_int)

    # Sum intensities per scan using vectorized bincount operation
    # This efficiently groups intensities by scan index and sums them
    intensities_arr[label] = np.bincount(
        scan_indices[mask], all_relevant_intensity[mask], minlength=num_scans
    )  # ← SUMMATION (accumulates duplicates)
```

**Key**: Lines 228-230 use `np.bincount()` which **sums** all intensities that match the same `scan_indices` value. This is fundamentally different from MATLAB's assignment behavior.

---

## Mathematical Explanation

### Setup

For a single scan `s` containing `n` centroid peaks:
- Raw masses: `m₁, m₂, ..., mₙ`
- Intensities: `I₁, I₂, ..., Iₙ`
- Mass tolerance offset: `τ = 0.2` Da
- Target integer m/z: `M = 205`

### Binning Function

Both implementations use the same rounding rule:

```
bin(m) = floor((m - τ) + 0.5)
```

### Duplicate Detection

Let `D` be the set of indices where peaks bin to target `M`:

```
D = {i : bin(mᵢ) = M}
```

For example, if peaks at m/z 204.8 and 205.1 both bin to 205:
```
D = {i, j}  where i ≠ j
```

### Final Intensity Value

**MATLAB** (last-wins assignment):
```
I_MATLAB(M, s) = I_max(D)  where max(D) is the last index in D
```

**Python** (summation via bincount):
```
I_Python(M, s) = Σ Iₖ  for all k ∈ D
```

### Example

Given a scan with:
- m/z 204.8, intensity 1000 (bins to 205)
- m/z 205.1, intensity 500 (bins to 205)

**MATLAB result**: `I = 500` (last value)
**Python result**: `I = 1500` (sum)
**Ratio**: 3.0×

### Integration Across Scans

Both implementations integrate across `T` scans in the RT window using trapezoidal rule:

```
Raw_Value = trapz(I(205, s₁), I(205, s₂), ..., I(205, sT))
```

If duplicates occur in 40% of scans with an average 1.5× inflation factor, the final raw value ratio would be:

```
Python/MATLAB ≈ 1 + 0.4 × 0.5 = 1.2  (20% higher)
```

This matches the observed 10-55% differences for glycerol and other compounds.

---

## Visual Comparison

### MATLAB: Last-Wins Assignment

```
Scan 1 centroid peaks:
  204.75 → intensity 800  } both round to 205
  205.15 → intensity 600  }

After binning:
  mzimat[205, scan1] = 600  ← only last value kept

Final: I(205, scan1) = 600
```

### Python: Summation via bincount

```
Scan 1 centroid peaks:
  204.75 → intensity 800  } both round to 205
  205.15 → intensity 600  }

After binning:
  bincount sums: 800 + 600 = 1400

Final: I(205, scan1) = 1400
```

**Difference**: 1400 / 600 = 2.33× higher in Python

---

## Why This Happens

### MATLAB Array Indexing Semantics

In MATLAB, when you use array indexing with duplicate indices:

```matlab
A([1, 2, 2, 3]) = [10, 20, 30, 40]
```

The result is:
```matlab
A(1) = 10
A(2) = 30  ← last value wins (overwrites 20)
A(3) = 40
```

This is **assignment semantics**: each index location stores the last value assigned to it.

### NumPy bincount Semantics

In Python, `np.bincount()` is designed for **histogram/aggregation** operations:

```python
indices = [1, 2, 2, 3]
values = [10, 20, 30, 40]
result = np.bincount(indices, values)
# result[2] = 20 + 30 = 50  ← sums duplicates
```

This is **accumulation semantics**: each bin accumulates all values assigned to it.

---

## Impact on Different Compounds

The severity of the discrepancy depends on:

1. **Peak density**: Compounds with more centroid peaks near the target m/z
2. **Mass calibration**: Instruments with systematic offsets produce more duplicates
3. **Isotopologue position**: Higher isotopologues (M+2, M+3) in crowded mass regions

**Glycerol example** (M+0 = 205):
- Observed ratios: 0.965× to 1.546× (Python/MATLAB)
- Average: ~1.2× (20% higher in Python)
- Indicates moderate duplicate frequency in this mass region
