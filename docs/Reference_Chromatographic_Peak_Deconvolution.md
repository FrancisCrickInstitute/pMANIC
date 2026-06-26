# Reference: Chromatographic Peak Deconvolution

## Overview

Chromatographic peak deconvolution separates partially overlapping extracted ion chromatogram (EIC) signals before peak area integration. In MANIC this is distinct from natural isotope correction: chromatographic deconvolution works in retention-time space, while natural isotope correction works across isotopologue abundances after integration.

When enabled, MANIC fits peak shapes to the signal around the expected retention time. The fitted model replaces the raw trace only when there is an overlap to resolve: if the window contains two or more overlapping peaks and the fit is acceptable, the component nearest the expected retention time is selected for integration and the others are excluded. For a well-resolved single peak there is no overlap to resolve, so MANIC integrates and displays the **raw trace** directly; fitting a model in this case would introduce optimization and parameter error without separating any signal, and could distort the peak.

The integration offsets (loffset/roffset) do not alter the shape of the fitted curve; they only determine which portion of the selected peak contributes to the final area. Moving an integration boundary therefore changes how much of the peak is integrated, not its fitted shape.

## One curve for display and integration

When deconvolution is on and warranted (a genuine overlap with an acceptable fit), the selected peak is a continuous analytic model (Gaussian, Bi-Gaussian, or EMG). The same continuous curve is used for both display and integration:

- **Plots** (grid and detailed views) draw the model evaluated on a dense grid, so the selected peak appears as a smooth curve rather than straight segments joining the acquisition scans. The faint raw EIC is drawn underneath, unchanged.
- **Integration** integrates that same densely-evaluated model over the loffset/roffset window, rather than applying trapezoidal integration to the model sampled only at the scan points.

The displayed peak is therefore identical to the integrated peak. Dense evaluation changes the exported areas only marginally relative to scan-point integration (typically under 0.1% for normally sampled peaks, and at most a few percent for very coarsely sampled peaks), in the direction of higher accuracy. Legacy (unit-spacing) integration is unaffected and remains scan-point based. The raw trace itself is never smoothed.

If baseline correction is enabled, MANIC keeps the usual edge-based baseline correction but applies it to the selected deconvolved signal. Excluded components are removed before the baseline is estimated.

## Joint Isotopologue Model

For labeled compounds, MANIC fits all isotopologue traces together as a small signal matrix:

```text
observed[channel, time] ~= baseline[channel, time]
                         + sum(component_shape[component, time]
                               * channel_weight[channel, component])
```

Each component has one shared chromatographic elution shape and a non-negative weight in each isotopologue channel. This is a targeted version of the same idea used in GC-MS spectral deconvolution: signals that belong to the same chemical component should rise and fall together over time.

This is especially useful when one isotopologue trace contains a shoulder or interference that is weak or absent in another. By fitting all traces together, the shared model pools evidence across channels rather than estimating each isotopologue independently.

## Consistency Across Raw, Corrected, and Abundance Results

For a labeled compound, the **same selected chromatographic component** feeds every export sheet. When deconvolution is warranted, MANIC deconvolves the raw isotopologue matrix once and then:

- integrates the selected component to produce the **Raw Values**, and
- applies natural isotope correction to that *same* selected component (not to the full unresolved trace) before integrating it for the **Corrected Values** (and therefore the **Isotope Ratios**, **% Label Incorporation**, and **Abundances** that derive from them).

In the time-based (non-legacy) path, the selected component is integrated by the same routine for both sheets, so raw and corrected areas differ only by the isotope correction. Consequently, enabling or disabling deconvolution for a compound moves its raw, corrected, and abundance values together. (Earlier development builds could leave corrected values tied to the unresolved full trace even when raw values changed; this is resolved.)

Because a single deconvolution pass produces both areas, enabling deconvolution does not double the fitting work at export. Together with caching and the fit-skipping checks described below, this keeps the bulk-export cost manageable.

## Per-Compound Settings

The resolution level, peak-shape fit type, and noise gate are stored **per compound** (persisted in the session database), not as a single global option. Each compound can use a different setting, and the choice applies to all of that compound's samples.

Settings are edited from **Settings → Chromatographic Peak Deconvolution** with a compound selected. The current value for the selected compound is shown in the status bar, and the settings are written to the export changelog so a processed result can be reproduced exactly.

### Applying settings to all compounds

The settings dialog includes an **"Apply these settings to all compounds"** checkbox. When ticked (and confirmed), the chosen resolution, fit type, and noise gate are written to every compound, overwriting their previous values. There is no separate global flag: the per-compound settings remain the single source of truth, so a bulk update propagates consistently to display, export, the changelog, and session export. To disable deconvolution for all compounds, set the resolution to `Off` and tick the box.

## Resolution Levels

Chromatographic peak deconvolution can be turned off, or run at levels `1` through `7`.

```text
off -> raw traces are unchanged
1   -> coarse, conservative splitting
4   -> default high-resolution behavior (resolves weak shoulders)
7   -> finest, most aggressive splitting
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

The ladder is deliberately recentred so the default level `4` is as **selective** (aggressive at splitting overlaps) as earlier builds' level `6`, while keeping a modest compute budget. Selectivity is governed by the detection fields (smoothing, prominence, height, width, BIC evidence, minimum component fraction); processing cost is governed separately by the maximum component count, the model families considered (EMG being the most expensive), and the optimizer budget. Raising selectivity without inflating those cost fields keeps the more aggressive default fast for both export and interactive browsing. Levels `5`-`7` extend past the earlier top end, adding more candidate components, the EMG model, and a larger optimizer budget for the hardest coelutions.

Legacy labels are mapped internally for compatibility:

```text
low    -> 2
medium -> 4
high   -> 6
```

## Peak Shape Models

MANIC compares a small set of common chromatographic peak shapes:

- **Gaussian:** symmetric peak shape; the simplest model, appropriate for clean, symmetric peaks.
- **Bi-Gaussian:** separate left and right widths about the apex, modelling fronting or tailing with one additional shape parameter.
- **Exponentially modified Gaussian (EMG):** a Gaussian convolved with an exponential decay, a standard model for asymmetric chromatographic peaks.

By default (**Auto** fit type) the model is selected by the Bayesian Information Criterion (BIC), which rewards lower residual error while penalising additional parameters. This prevents the most flexible model from being selected when its reduction in residual error is not statistically meaningful.

### Manual fit-type override

The per-compound **fit type** can override automatic selection:

- **Auto:** compare the available shapes and pick the best by BIC (default behaviour, and the recommended choice).
- **Gaussian:** force a symmetric Gaussian shape.
- **Bi-Gaussian:** force the asymmetric bi-Gaussian shape.
- **EMG:** force the exponentially modified Gaussian shape.

When a specific shape is forced, MANIC restricts the model family to that single shape instead of searching across all of them. This is appropriate when the expected peak behaviour for a compound is known in advance, or where consistent results are required. Component-count selection (how many overlapping peaks to resolve) continues to follow the resolution level.

## Performance

Joint deconvolution is more expensive than raw integration because it may fit several candidate component counts and peak shapes. MANIC limits the cost by:

- fitting only inside a bounded retention-time context around the target peak
- capping candidate components by resolution level
- using cheaper models at lower levels
- reserving EMG for higher-resolution settings
- rejecting tiny components that do not explain enough signal
- falling back to simpler results if fitting fails

For typical isotopologue counts and integration windows, the cost remains modest. The highest levels are intended for cases where resolving difficult coelution outweighs processing speed.

Repeated work is also avoided by caching: identical fits (same window data, level, and fit type) are computed once and reused, so opening plots, recalculating ratios, and exporting do not refit the same trace multiple times.

## Behaviour on Messy or Unfittable Traces

Deconvolution is designed to degrade gracefully and never block integration. Two checks run **before** the expensive fit (so the fit is skipped entirely in the common cases), and a quality net runs **after** it:

- **Deconvolution off, too few points, or an empty integration window:** the raw trace is used unchanged.
- **No genuine overlap (the resolved-peak early-out):** MANIC first counts the peaks in the raw window (`_detect_components`). With fewer than two there is nothing to separate, so it **skips the fit** and integrates the raw trace. Because most targeted peaks are single and well-resolved, this is the largest export speedup: a resolved peak avoids a curve fit that would otherwise be computed and discarded.
- **A window that is too messy to be worth fitting (the noise gate):** also before any curve fitting, MANIC measures the smoothness of the window - specifically, whether consecutive steps in the signal tend to share sign (the lag-1 autocorrelation of the trace's first differences). A real peak rises then falls, so its steps largely share sign (a positive score) even when the peak is weak or sparsely sampled; noise alternates sign (a score near -0.5). Windows scoring below the active threshold are skipped: no model is fit, no overlay is drawn, and integration uses the raw trace. This is both a correctness choice (fitting noise is not meaningful) and a major export speedup, as noise-dominated windows are otherwise the most expensive to fit and are then discarded.

  The gate is a **per-compound** setting chosen from four presets (stored in `compounds.deconvolution_noise_gate`, mapped to thresholds in `NOISE_GATE_PRESETS`):

  | Preset | Threshold | Behaviour |
  |---|---|---|
  | `off` | `None` | gate disabled - always attempt a fit (only flat/empty windows are skipped) |
  | `lenient` | `-0.3` | skip only near-pure noise |
  | `balanced` (default) | `-0.1` | skip noise and weak-peak-in-heavy-noise |
  | `aggressive` | `+0.1` | only fit clearly smooth peaks |

  The default `balanced` (`-0.1`) sits in the gap between typical noise (~`-0.5`) and genuine peaks (`>= +0.3`), biased slightly toward retaining borderline peaks, since the subsequent fit-quality checks can still reject a poor fit. It is set per compound in the deconvolution dialog.
- **A fit is attempted but no usable model is found** (the optimizer fails to converge, or every candidate is non-finite or contributes negligible signal): MANIC integrates the **raw trace** over the loffset/roffset window, equivalent to the deconvolution-off result. No overlays are drawn.
- **A fit succeeds but does not reproduce the data (the fit-quality net):** after fitting, MANIC retains the model (`_fit_reproduces_window`) only if it uses at least two components *and* reconstructs the raw window adequately (relative residual at or below `FIT_QUALITY_MAX_REL_RESIDUAL`). If the fit collapses to one component or fails to reproduce the data - for example, a clean peak that is over-split with the wrong fragment selected - MANIC discards the model and integrates the **raw trace**. This prevents an over-flexible or poorly converged fit from distorting a clean peak and under-counting its area.
- **Unexpected numerical failure during fitting:** any error is caught and treated as "no usable model", routing to the same raw-trace fallback rather than propagating. This protects both interactive plotting and bulk export.

In summary, the model replaces the raw trace only for genuine, well-fit overlaps. In every other case - off, too few points, too messy, no usable fit, a resolved single peak, or a poor fit - MANIC integrates and displays the raw trace. It does not zero out results, blank the plot, or abort an export.

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
