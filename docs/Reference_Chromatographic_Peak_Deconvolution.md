# Reference: Chromatographic Peak Deconvolution

## Overview

Chromatographic peak deconvolution separates partially overlapping extracted ion chromatogram (EIC) signals before peak area integration. In MANIC this is distinct from natural isotope correction: chromatographic deconvolution works in retention-time space, while natural isotope correction works across isotopologue abundances after integration.

When enabled, MANIC fits peak shapes to the signal around the expected retention time. Crucially, the fitted model only *replaces* the raw trace when there is genuinely something to separate: if the window contains two or more overlapping peaks and the fit is good, MANIC keeps the peak nearest the expected retention time and removes the others. For a well-resolved single peak there is nothing to separate, so MANIC integrates and displays the **raw trace** directly - this matches standard practice (raw integration is the reference method for resolved peaks) and avoids a curve fit distorting a clean peak.

The integration offsets (loffset/roffset) do not change the shape of the fitted curve - they only decide which slice of the selected peak is added up for the final area. So moving an integration boundary changes how much of the peak is counted, not the peak's fitted shape.

## One curve for display and integration

When deconvolution is on **and warranted** (a genuine overlap with a good fit), the fitted peak is a continuous analytic model (Gaussian, Bi-Gaussian, or EMG). MANIC keeps that continuous model and uses the *same* curve for both the picture and the number:

- **Plots** (grid view and the detailed view) draw the model evaluated on a dense grid, so the selected peak is a genuinely smooth curve rather than straight lines joining the acquisition scan points. The faint raw EIC is still drawn underneath, untouched.
- **Integration** integrates that same dense model over the loffset/roffset window, instead of trapezoidal integration of the model sampled only at the scan points.

This guarantees the displayed peak is exactly what is integrated. Because adding up a smooth peak is already accurate, the exported areas barely change versus the previous scan-point integration (typically well under 0.1% for normally sampled peaks, and at most a couple of percent for very coarsely sampled ones), and the change is always toward the more accurate value. Legacy (unit-spacing) integration is unaffected and stays scan-point based. The raw trace is never smoothed.

If baseline correction is enabled, MANIC keeps the usual edge-based baseline correction but applies it to the selected deconvolved signal. Excluded components are removed before the baseline is estimated.

## Joint Isotopologue Model

For labeled compounds, MANIC fits all isotopologue traces together as a small signal matrix:

```text
observed[channel, time] ~= baseline[channel, time]
                         + sum(component_shape[component, time]
                               * channel_weight[channel, component])
```

Each component has one shared chromatographic elution shape and a non-negative weight in each isotopologue channel. This is a targeted version of the same idea used in GC-MS spectral deconvolution: signals that belong to the same chemical component should rise and fall together over time.

This is especially useful when one isotopologue trace contains a shoulder or interference that is weak or invisible in another. By fitting all the traces together, the shared model can pool the evidence across them rather than guessing separately for each isotopologue.

## Consistency Across Raw, Corrected, and Abundance Results

For a labeled compound, the **same selected chromatographic component** feeds every export sheet. When deconvolution is warranted, MANIC deconvolves the raw isotopologue matrix once and then:

- integrates the selected component to produce the **Raw Values**, and
- applies natural isotope correction to that *same* selected component (not to the full unresolved trace) before integrating it for the **Corrected Values** (and therefore the **Isotope Ratios**, **% Label Incorporation**, and **Abundances** that derive from them).

In the time-based (non-legacy) path, that selected component is integrated by the same routine for both sheets, so raw and corrected areas differ *only* by the isotope correction. The practical upshot: turning deconvolution on or off for a compound moves its raw, corrected, and abundance numbers together. (Earlier development builds could leave corrected values tied to the unresolved full trace even when raw values changed; that is fixed.)

Because one deconvolution pass produces both areas, enabling deconvolution does not double the fitting work at export. With caching and the fit-skipping checks below, bulk export stays practical.

## Per-Compound Settings

The resolution level, peak-shape fit type, and noise gate are stored **per compound** (persisted in the session database), not as a single global option. Each compound can use a different setting, and the choice applies to all of that compound's samples.

Settings are edited from **Settings → Chromatographic Peak Deconvolution** with a compound selected. The current value for the selected compound is shown in the status bar, and the settings are written to the export changelog so a processed result can be reproduced exactly.

### Applying settings to all compounds

The settings dialog includes an **"Apply these settings to all compounds"** checkbox. When ticked (and confirmed), the chosen resolution, fit type, and noise gate are written to every compound at once, overwriting their previous values. There is no separate global flag - the per-compound settings stay the single source of truth, so a bulk apply flows through display, export, the changelog, and session export automatically. To disable deconvolution everywhere, set the resolution to `Off` and tick the box.

## Resolution Levels

Chromatographic peak deconvolution can be turned off, or run at levels `1` through `7`.

```text
off -> raw traces are unchanged
1   -> coarse, conservative splitting
4   -> default medium-resolution behavior
7   -> fine, most aggressive splitting
```

The resolution level controls a preset bundle:

- smoothing window size
- minimum peak prominence
- minimum peak height
- minimum peak width
- maximum candidate component count
- model families considered
- strength of BIC evidence needed to accept more complex fits

Higher levels use less smoothing and allow narrower or weaker candidate components. Lower levels require stronger evidence before splitting a peak.

Legacy labels are mapped internally for compatibility:

```text
low    -> 2
medium -> 4
high   -> 6
```

## Peak Shape Models

MANIC compares a small set of common chromatographic peak shapes:

- **Gaussian:** symmetric and stable. This is the simplest model and remains useful for clean peaks.
- **Bi-Gaussian:** separate left and right widths around the apex. This handles fronting or tailing with one extra shape parameter.
- **Exponentially modified Gaussian (EMG):** a Gaussian peak convolved with an exponential tailing process. This is a standard model for asymmetric chromatographic peaks.

By default (**Auto** fit type) the model is chosen with the Bayesian Information Criterion (BIC), which rewards lower residual error but penalizes extra parameters. This prevents the most flexible model from always winning when the improvement is not meaningful.

### Manual fit-type override

The per-compound **fit type** can override automatic selection:

- **Auto:** compare the available shapes and pick the best by BIC (default behaviour, and the recommended choice).
- **Gaussian:** force a symmetric Gaussian shape.
- **Bi-Gaussian:** force the asymmetric bi-Gaussian shape.
- **EMG:** force the exponentially modified Gaussian shape.

When a specific shape is forced, MANIC restricts the model family to that single shape instead of searching across all of them. This is useful when you already know the expected peak behaviour for a compound, or to keep results consistent. Component-count selection (how many overlapping peaks to resolve) still follows the resolution level.

## Performance

Joint deconvolution is more expensive than raw integration because it may fit several candidate component counts and peak shapes. MANIC limits the cost by:

- fitting only inside a bounded retention-time context around the target peak
- capping candidate components by resolution level
- using cheaper models at lower levels
- reserving EMG for higher-resolution settings
- rejecting tiny components that do not explain enough signal
- falling back to simpler results if fitting fails

For normal isotopologue counts and integration windows, the cost should remain practical. The highest levels should be used when resolving difficult coelution is more important than processing speed.

Repeated work is also avoided by caching: identical fits (same window data, level, and fit type) are computed once and reused, so opening plots, recalculating ratios, and exporting do not refit the same trace multiple times.

## Behaviour on Messy or Unfittable Traces

Deconvolution is designed to degrade gracefully and never block integration. Two checks run **before** the expensive fit (so the fit is skipped entirely in the common cases), and a quality net runs **after** it:

- **Deconvolution off, too few points, or an empty integration window:** the raw trace is used unchanged.
- **No genuine overlap (the resolved-peak early-out):** MANIC first counts the peaks in the raw window (`_detect_components`). With fewer than two there is nothing to separate, so it **skips the fit** and integrates the raw trace. Since most targeted peaks are single and well-resolved, this is the largest export speedup - a clean peak costs almost nothing instead of a curve fit that would be discarded anyway.
- **A window that is too messy to be worth fitting (the noise gate):** also before any curve fitting, MANIC measures how *smooth* the window is - it checks whether consecutive steps in the signal tend to go the same direction (technically, the lag-1 autocorrelation of the trace's first differences). A real peak rises then falls, so its steps mostly share a direction (a positive score) even when the peak is weak or sparsely sampled; pure noise jitters up and down at random (a score near -0.5). Windows scoring below the active threshold are skipped outright - no model is fit, no overlay is drawn, and integration uses the raw trace. This is both a correctness choice (fitting noise is meaningless) and the single biggest export speedup, since noise-dominated windows are otherwise the slowest to fit and are discarded anyway.

  The gate is a **per-compound** setting chosen from four presets (stored in `compounds.deconvolution_noise_gate`, mapped to thresholds in `NOISE_GATE_PRESETS`):

  | Preset | Threshold | Behaviour |
  |---|---|---|
  | `off` | `None` | gate disabled - always attempt a fit (only flat/empty windows are skipped) |
  | `lenient` | `-0.3` | skip only near-pure noise |
  | `balanced` (default) | `-0.1` | skip noise and weak-peak-in-heavy-noise |
  | `aggressive` | `+0.1` | only fit clearly smooth peaks |

  The default `balanced` (`-0.1`) sits in the gap between typical noise (~`-0.5`) and genuine peaks (`>= +0.3`), leaning slightly toward keeping borderline peaks - the safer choice for quantitation, because the later fit-quality checks can still reject a bad fit. Change it per compound in the deconvolution dialog.
- **A fit is attempted but no usable model is found** (the optimizer fails to converge, or every candidate is non-finite or too weak to matter): MANIC integrates the **raw trace** over the loffset/roffset window - exactly the deconvolution-off result. No overlays are drawn.
- **A fit succeeds but does not reproduce the data (the fit-quality net):** after fitting, MANIC keeps the model (`_fit_reproduces_window`) **only** if it genuinely uses at least two components *and* reconstructs the raw window well (relative residual at or below `FIT_QUALITY_MAX_REL_RESIDUAL`). If it collapses to one component or misfits - e.g. a clean peak over-split with the wrong fragment selected - MANIC discards it and integrates the **raw trace**. This guards against an over-flexible or mis-converged fit mangling a clean peak and under-counting its area.
- **Unexpected numerical failure during fitting:** any error is caught and treated as "no usable model", routing to the same raw-trace fallback rather than raising. This protects both plotting and bulk export.

In short, MANIC only lets the model replace the raw trace for genuine, well-fit overlaps; in every other case - off, too few points, too messy, no usable fit, a resolved single peak, or a poor fit - it integrates and displays the raw trace. It never zeroes out, blanks the plot, or aborts an export.

## Scientific Background

The method combines ideas from three common areas of chromatographic data processing:

- **Peak-shape fitting:** Gaussian, bi-Gaussian, and EMG functions are widely used to model chromatographic peaks, especially asymmetric tailing peaks.
- **Model selection:** BIC-style penalties are used to avoid unnecessary components or overly flexible peak shapes.
- **Multi-channel deconvolution:** GC-MS tools such as AMDIS use the fact that ions from one compound share a chromatographic shape. MANIC applies the same principle to isotopologue traces rather than full mass spectra.

Relevant literature:

- Foley, J. P. and Dorsey, J. G. (1984). *A review of the exponentially modified Gaussian (EMG) function: evaluation and subsequent calculation of universal data*. Journal of Chromatographic Science, 22, 40-46.
- Di Marco, V. B. and Bombi, G. G. (2001). *Mathematical functions for the representation of chromatographic peaks*. Journal of Chromatography A, 931, 1-30.
- Stein, S. E. (1999). *An integrated method for spectrum extraction and compound identification from gas chromatography/mass spectrometry data*. Journal of the American Society for Mass Spectrometry, 10, 770-781.
- Tautenhahn, R., Bottcher, C. and Neumann, S. (2008). *Highly sensitive feature detection for high resolution LC/MS*. BMC Bioinformatics, 9, 504.
- Yu, T. and Peng, H. (2010). *Quantification and deconvolution of asymmetric LC-MS peaks using the bi-Gaussian mixture model and statistical model selection*. BMC Bioinformatics, 11, 559.
- Kalambet, Y., Kozmin, Y., Mikhailova, K., Nagaev, I. and Tikhonov, P. (2011). *Reconstruction of chromatographic peaks using the exponentially modified Gaussian function*. Journal of Chemometrics, 25, 352-356.
- Wei, X., Shi, X., Kim, S., Patrick, J. S., Binkley, J., Kong, M., McClain, C. and Zhang, X. (2014). *Data dependent peak model based spectrum deconvolution for analysis of high resolution LC-MS data*. Analytical Chemistry, 86, 2156-2165.
