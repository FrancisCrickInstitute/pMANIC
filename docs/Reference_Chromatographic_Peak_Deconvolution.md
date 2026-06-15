# Reference: Chromatographic Peak Deconvolution

## Overview

Chromatographic peak deconvolution separates partially overlapping extracted ion chromatogram (EIC) signals before peak area integration. In MANIC this is distinct from natural isotope correction: chromatographic deconvolution works in retention-time space, while natural isotope correction works across isotopologue abundances after integration.

When enabled, MANIC fits a chromatographic context around the expected retention time. Crucially, the fitted model only *replaces* the raw trace when there is something genuine to deconvolve: if the window contains two or more overlapping peaks and the fit is good, the component nearest the expected retention time is selected for integration and the others are excluded. For a well-resolved single peak there is nothing to separate, so MANIC integrates and displays the **raw trace** directly - this matches standard practice (raw integration is the reference method for resolved peaks) and avoids the risk of a curve fit distorting a clean peak.

The integration offsets do not define the fitted curve. They only cut out the part of the selected fitted curve that contributes to the final area. This prevents moving an integration boundary from changing the shape of the fitted peak itself.

## One curve for display and integration

When deconvolution is on **and warranted** (a genuine overlap with a good fit), the fitted peak is a continuous analytic model (Gaussian, Bi-Gaussian, or EMG). MANIC keeps that continuous model and uses the *same* curve for both the picture and the number:

- **Plots** (grid view and the detailed view) draw the model evaluated on a dense grid, so the selected peak is a genuinely smooth curve rather than straight lines joining the acquisition scan points. The faint raw EIC is still drawn underneath, untouched.
- **Integration** integrates that same dense model over the loffset/roffset window, instead of trapezoidal integration of the model sampled only at the scan points.

This guarantees the displayed peak is exactly what is integrated. Because trapezoidal integration of a smooth peak is already accurate, the exported areas change only marginally versus the previous scan-point integration (typically well under 0.1% for normally sampled peaks, and at most a couple of percent for very coarsely sampled peaks), always in the more accurate direction. Legacy (unit-spacing) integration is unaffected and remains scan-point based. The raw trace is never smoothed.

If baseline correction is enabled, MANIC keeps the usual edge-based baseline correction but applies it to the selected deconvolved signal. Excluded components are removed before the baseline is estimated.

## Joint Isotopologue Model

For labeled compounds, MANIC fits all isotopologue traces together as a small signal matrix:

```text
observed[channel, time] ~= baseline[channel, time]
                         + sum(component_shape[component, time]
                               * channel_weight[channel, component])
```

Each component has one shared chromatographic elution shape and a non-negative weight in each isotopologue channel. This is a targeted version of the same idea used in GC-MS spectral deconvolution: signals that belong to the same chemical component should rise and fall together over time.

This is especially useful when one isotopologue trace contains a shoulder or interference that is weak or invisible in another trace. The shared model can use the multi-channel evidence rather than deciding independently for each isotopologue.

## Per-Compound Settings

Both the resolution level and the peak-shape fit type are stored **per compound** (persisted in the session database), not as a single global option. Each compound can use a different setting, and the choice applies to all of that compound's samples.

Settings are edited from **Settings → Chromatographic Peak Deconvolution (selected compound)...** with a compound selected. The current value for the selected compound is shown in the status bar, and both fields are written to the export changelog so a processed result can be reproduced exactly.

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
- **No genuine overlap to resolve (the resolved-peak early-out):** before fitting, MANIC detects how many peaks the raw window contains (`_detect_components`). If there are fewer than two, there is nothing to deconvolve, so it **skips the fit entirely** and integrates the raw trace. Because most targeted peaks are single and well-resolved, this is the dominant export speedup - a clean single peak costs essentially nothing instead of a full curve fit that would only be discarded.
- **A window that is too messy to be worth fitting (the noise gate):** also before any curve fitting, MANIC scores the window's smoothness as the lag-1 autocorrelation of its first differences. A real elution peak rises then falls, so consecutive slopes share sign (a positive score) even when the peak is sparsely sampled or weak; pure noise alternates sign (a score near -0.5). Windows scoring below the active threshold are skipped outright - no model is fit, no overlay is drawn, and integration uses the raw trace. This is both a correctness choice (fitting noise is meaningless) and the single biggest export speedup, because noise-dominated windows are otherwise the most expensive to fit and are discarded anyway.

  The gate is a **per-compound** setting chosen from four presets (stored in `compounds.deconvolution_noise_gate`, mapped to thresholds in `NOISE_GATE_PRESETS`):

  | Preset | Threshold | Behaviour |
  |---|---|---|
  | `off` | `None` | gate disabled - always attempt a fit (only flat/empty windows are skipped) |
  | `lenient` | `-0.3` | skip only near-pure noise |
  | `balanced` (default) | `-0.1` | skip noise and weak-peak-in-heavy-noise |
  | `aggressive` | `+0.1` | only fit clearly smooth peaks |

  The default `balanced` (`-0.1`) sits in the empty gap between the noise population (~`-0.5`) and genuine peaks (`>= +0.3`), biased slightly toward keeping borderline peaks (the safer error for quantitation, since the usable-fit checks can still reject a poor fit). Change it per compound in the deconvolution dialog.
- **A fit is attempted but no usable model is found** (the optimizer fails to converge, or every candidate is rejected for being non-finite or contributing too little signal): MANIC falls back to **integrating the raw trace over the loffset/roffset window** - exactly the result you would get with deconvolution turned off. No component overlays are drawn, and the plot simply shows the raw EIC.
- **A fit succeeds but does not reproduce the data (the fit-quality net):** after fitting an apparent overlap, MANIC checks the result (`_fit_reproduces_window`). The model is kept **only** when (a) the fit actually uses at least two components and (b) the reconstruction reproduces the raw window well (relative residual at or below `FIT_QUALITY_MAX_REL_RESIDUAL`). If the fit collapses to one component or does not match the data - for example a clean peak that got over-split with the wrong fragment selected - MANIC discards the model and integrates the **raw trace** instead. This is the safeguard against a clean peak being mangled by an over-flexible or mis-converged fit, which would badly under-count the area.
- **Unexpected numerical failure during fitting:** any error in the fit is caught and treated as "no usable model", so it routes to the same raw-trace fallback rather than raising an error. This protects both interactive plotting and bulk export.

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
