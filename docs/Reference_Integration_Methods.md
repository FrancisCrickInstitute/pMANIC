# Reference: Integration Methods

## Overview
Integration is the process of calculating the "area under the curve" for a chromatogram peak. This area represents the total abundance of the ion detected during the elution window.   

MANIC offers two distinct algorithms for this calculation. The choice of method fundamentally changes the numerical scale of your results.   

---

## 1. Time-Based Integration (Default)

This is the standard, scientifically accurate method.

### How It Works
It calculates the area using the **Trapezoidal Rule** with the actual retention time stamps from the raw data file.
* **X-Axis:** Time (minutes)
* **Y-Axis:** Intensity (counts)
* **Resulting Unit:** Intensity $\times$ Minutes

### Formula
$$\text{Area} = \sum_{i=start}^{end-1} \frac{(I_i + I_{i+1})}{2} \times (t_{i+1} - t_i)$$   
*Where $I$ is intensity and $t$ is time.*   

### Why use this?
* **Physical Meaning:** The area represents a physical quantity (total ion current over time).
* **Robustness:** It remains accurate even if the mass spectrometer's scan rate varies (e.g., if the instrument scans slower at the end of a run).
* **Scale:** Values are typically smaller (e.g., `150,000`).

---

## 2. Legacy Integration (Unit-Spacing)

This method is provided **solely** for backward compatibility with the legacy MATLAB tool (GVISO / MANIC v3.3.0).   

### How It Works
It calculates the area using the Trapezoidal Rule but ignores the time timestamps, assuming a fixed distance of `1` between every data point.   
* **X-Axis:** Scan Index (unitless steps)
* **Y-Axis:** Intensity (counts)
* **Resulting Unit:** Intensity Sum (approximate)

### Formula
$$\text{Area} = \sum_{i=start}^{end-1} \frac{(I_i + I_{i+1})}{2} \times 1$$   

### Why use this?
* **Reproducibility:** Use this *only* if you are comparing new results against a dataset processed years ago with the MATLAB version and need the raw numbers to match exactly.
* **Scale:** Values are significantly larger (typically **60–100× larger** than time-based integration) because they are not scaled down by the small time step (e.g., $0.01$ min).

> **Warning:** Do not mix methods within a single study. The numerical values are not directly comparable.

---

## Configuration

**Settings → Legacy Integration Mode**   

* **Unchecked (Default):** Uses **Time-Based** integration.
* **Checked:** Uses **Legacy** integration.

### Boundary Handling (Technical Note)
Both methods utilize the same "Strict Boundary" logic to determine which points are included in the sum:
* Points typically must fall **strictly inside** the integration window boundaries (`tR - loffset` and `tR + roffset`).
* Points exactly *on* the boundary line are generally excluded to prevent double-counting in adjacent windows.
