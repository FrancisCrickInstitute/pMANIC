# Reference: Chromatographic Peak Deconvolution

## Overview

Chromatographic peak deconvolution separates partially overlapping extracted ion chromatogram (EIC) signals before peak area integration. In MANIC this is distinct from natural isotope correction: chromatographic deconvolution works in retention-time space, while natural isotope correction works across isotopologue abundances after integration.

When enabled, MANIC fits a chromatographic context around the expected retention time instead of using the raw trace directly. Even a single visible peak is smoothed and reconstructed by the model; if multiple components are supported by the data, the component nearest the expected retention time is selected for integration and the other components are excluded.

The integration offsets do not define the fitted curve. They only cut out the part of the selected fitted curve that contributes to the final area. This prevents moving an integration boundary from changing the shape of the fitted peak itself.

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

Deconvolution is designed to degrade gracefully and never block integration:

- **Deconvolution off, too few points, or an empty integration window:** the raw trace is used unchanged.
- **A fit is attempted but no usable model is found** (the optimizer fails to converge, or every candidate is rejected for being non-finite or contributing too little signal): MANIC falls back to **integrating the raw trace over the loffset/roffset window** - exactly the result you would get with deconvolution turned off. No component overlays are drawn, and the plot simply shows the raw EIC.
- **Unexpected numerical failure during fitting:** any error in the fit is caught and treated as "no usable model", so it routes to the same raw-trace fallback rather than raising an error. This protects both interactive plotting and bulk export.

In short, a messy trace that cannot be deconvolved produces the same area as the non-deconvolution path; it does not zero out, blank the plot, or abort an export.

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
