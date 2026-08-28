# Reference: Chromatographic Peak Deconvolution

## Overview

Chromatographic peak deconvolution separates partially overlapping extracted ion chromatogram (EIC) signals before peak area integration. In MANIC this is distinct from natural isotope correction: chromatographic deconvolution works in retention-time space, while natural isotope correction works across isotopologue intensities before integration.

When enabled, MANIC fits peak shapes to the signal around the expected retention time on every fittable channel of every sample. Export then uses one measurement method for that compound in that sample: dense model areas if every non-empty ion fitted, or the raw in-window scan traces if any ion with real intensity did not. An ion with no finite positive signal inside the integration window is empty. It does not count as a failed fit.

If the window contains two or more overlapping peaks and the fit is acceptable, the component nearest the expected retention time **whose centre sits inside the loffset/roffset window** is selected and the others are excluded. A neighbour whose centre is outside those dashes is never the selected peak. If a successful fit has no centre inside the dashed boundaries, that ion is empty and contributes zero on model, raw-fallback, and legacy paths. A well-resolved single peak becomes a one-component model. A one-component model can also win when splitting an overlap does not improve BIC enough. Too-short or too-messy windows and unusable fits use the raw trace.

The integration offsets (loffset/roffset) decide which component may be selected and which portion contributes to the final area. Each offset also sets the fit context when it exceeds the 0.25-minute minimum, so moving a wider boundary can change the fitted curve.

## Consistency across samples and isotopologues

Deconvolution settings are per compound and apply to every sample. When the level is not `off`, every fittable isotopologue of every sample is fit. A clean M+0 is not left on a raw trapezoid while a sibling ion is modelled: both are fit independently.

Export is stricter still. If any ion with real intensity failed to fit, every non-empty ion of that pair uses the raw in-window scans. Empty ions stay zero. A modelled M+0 is not exported as an isolated-component area beside a raw M+1. Those would be different measurements of the same envelope. An empty ion does not force that fallback.

## One fit for display and integration

When deconvolution is on and every non-empty ion of the compound in that sample has a usable model, the selected peak is a continuous analytic model (Gaussian, Bi-Gaussian, or EMG). Display and export use that same fitted model:

- **Plots** with Natural Abundance Correction preview off draw the model on a dense grid, with the faint raw EIC underneath. With preview on, plots draw the corrected selected model at the acquisition scan times and keep the faint raw EIC for context. Neighbour peaks remain visible but do not enter correction or integration. The y-axis includes both the corrected trace and the raw context.
- **Integration** and export integrate that same densely-evaluated model from the first scan inside the loffset/roffset window to the last, rather than from the offset edges themselves or from the model sampled only at the acquisition scans.

Both views come from the same selected fit, but corrected preview is scan-sampled while time-based export uses the denser grid for a more accurate area. Dense evaluation changes exported areas only marginally relative to scan-point integration (typically under 0.1% for normally sampled peaks, and at most a few percent for very coarsely sampled peaks). Legacy (unit-spacing) integration remains scan-point based. The raw trace itself is never smoothed.

If any ion of a labelled compound in that sample has real intensity and failed to fit, plots and export both use the raw in-window scan traces for non-empty ions. Empty ions stay zero. No fitted curve is drawn. An empty higher ion does not trigger that fallback. Unlabelled tiles draw a curve for each ion that fitted and leave failed ions on the raw trace; export still uses the raw window unless every non-empty ion fitted. See [Failed ions put the whole envelope on scans](#failed-ions-put-the-whole-envelope-on-scans).

If baseline correction is enabled, MANIC keeps the usual edge-based baseline correction but applies it to the selected deconvolved signal. Excluded components are removed before the baseline is estimated.

The exported number is the dense-curve area minus that edge baseline. Those two pieces are natural-abundance corrected separately. The curve is corrected on the dense time grid. The baseline ends are corrected on the isolated component at the real scan times, then the first and last in-window scans are used as the straight-line ends. Raw Values use the raw selected edges; Corrected Values use those same scan-sampled edges after correction. The ends are almost the same sampling, so the baseline barely moves.

## Independent per-channel fits

MANIC deconvolves one extracted-ion trace at a time. Each isotopologue, or each quantifier or qualifier ion, is an intensity-versus-time series. The fitter finds chromatographic components on that series only.

A mess on M+1 cannot change the M+0 area. Channels do not share an elution shape.

For a labeled compound the preferred centre for every channel is the compound retention time. Each channel then selects the in-window component nearest that time on its own trace.

`deconvolve_eic` fits one channel. A multi-channel matrix goes through `deconvolve_channel_matrix`, which calls `deconvolve_eic` once per row and returns a `ChannelDeconvolutionBundle`.

## Unlabelled quantifier and qualifier ions

Unlabelled mode uses this same per-channel fitter. Import defaults to level 4, matching labelled mode; the setting applies to every sample of that compound. Q and V are different EI fragments, so they are never given a shared elution shape.

Amount is the Q-ion area. V/Q identity ratios use the same area list. If any non-empty ion of that compound/sample failed to fit, every non-empty ion uses the raw in-window scans. Empty ions stay at area 0.

Observed RT and the detail mass spectrum stay on the raw Q apex inside the window. Areas may be modelled; the apex is not switched to the fitted centre.

Imported expected V/Q ratios are almost always measured on raw-window areas. Enabling deconvolution can move observed ratios even when every non-empty ion fitted. Remeasure expected ratios and tolerances on standards with the same setting.

## Consistency Across Raw, Corrected, and Abundance Results

For a labeled compound, each channel's **selected chromatographic component** feeds every export sheet. When deconvolution is warranted, MANIC deconvolves each raw isotopologue channel independently and then:

- integrates the selected component to produce the **Raw Values**, and
- applies natural isotope correction to that *same* selected component (not to the full unresolved trace) before integrating it for the **Corrected Values** (and therefore the **Isotope Ratios**, **% Label Incorporation**, and **Abundances** that derive from them).

In the time-based (non-legacy) path, the selected component is integrated by the same routine for both sheets, so raw and corrected areas differ only by the isotope correction. Consequently, enabling or disabling deconvolution for a compound moves its raw, corrected, and abundance values together.

Because a single deconvolution pass produces both areas, enabling deconvolution does not double the fitting work at export. Together with caching and the fit-skipping checks described below, this keeps the bulk-export cost manageable.

## Failed ions put the whole envelope on scans

Natural-abundance correction inverts a matrix across the isotopologue envelope. Raw and Corrected therefore have to be the same kind of measurement on every ion of that compound in that sample. A curve area on M+0 beside a scan trapezoid on M+1 is not a paired MID.

For each compound/sample:

- If **every non-empty** ion has a model, plots draw the dense curve and Raw and Corrected both integrate it. Empty ions contribute area 0.
- If **any** ion of a labelled compound has real intensity and failed to fit (noise-gated, too few points, numerical failure, or poor reconstruction), plots show the raw scan traces and Raw and Corrected both integrate those same raw in-window scans for every non-empty ion of that pair, including ions that did fit. Empty rows stay zero. No fitted overlay is drawn. Natural-abundance correction then runs on that envelope.
- An ion is **empty** when it has no finite positive signal inside the integration window, or when a successful fit found peaks but none of their centres sit inside the nominal loffset/roffset boundaries. Signal elsewhere in the chromatogram does not make that ion active. Weak positive signal inside the window is not empty. If its fit fails, MANIC keeps its raw scans.
- Unlabelled tiles draw a curve for each ion that fitted. Export still uses the raw window unless every non-empty Q/V ion fitted, so V/Q is never a model area divided by a scan trapezoid.

The next sample of the same compound can still use model areas if every non-empty ion there fitted.

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

Levels `1`-`4` detect candidate components only at local maxima (resolved overlaps). Levels `5`-`7` additionally run **shoulder detection**: a shoulder rides on a peak's flank without forming its own local maximum, so it is invisible to maximum-based detection, but it shows up as a region of strong downward curvature (a peak in the negative second derivative). These shoulder positions become extra seed candidates, gated by the per-level `shoulder_curvature_fraction`. They are only *seeds*: the BIC component-count test and the post-fit quality net still decide whether a split is kept, and the EMG model (available at these levels) lets genuine tailing be explained as a single component rather than over-split. A genuinely unresolved shoulder is an ill-posed split, so it may still be (correctly) declined in favour of a single skewed-peak model.

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

Deconvolution is more expensive than raw integration because it may fit several candidate component counts and peak shapes on each channel. MANIC limits the cost by:

- fitting only inside a bounded retention-time context around the target peak
- capping candidate components by resolution level
- using cheaper models at lower levels
- reserving EMG for higher-resolution settings
- rejecting tiny components that do not explain enough signal
- falling back to simpler results if fitting fails

For typical isotopologue counts and integration windows, the cost remains modest. The highest levels are intended for cases where resolving difficult coelution outweighs processing speed.

Repeated work is also avoided by caching: identical fits (same window data, level, and fit type) are computed once and reused, so opening plots, recalculating ratios, and exporting do not refit the same trace multiple times.

At export, the per-window curve fit is CPU-bound Python code driving the optimizer, which the interpreter lock prevents threads from running in parallel. For a sufficiently large export MANIC therefore fans the per-sample/per-compound fits out to worker **processes** for true multicore scaling, falling back to a single thread pool for small jobs (where process startup is not worth it) and if a worker pool cannot be created. Each worker process keeps its own fit cache rather than sharing the interactive one; because distinct samples produce distinct windows, cross-sample cache reuse during export is minor, so this trade is favourable. Results are identical regardless of which path runs.

## Behaviour on Messy or Unfittable Traces

Deconvolution is designed to degrade gracefully and never block integration. Two checks run **before** the expensive fit (so the fit is skipped entirely in the common cases), and a quality net runs **after** it:

- **Deconvolution off, too few points, or an empty integration window:** the raw trace is used unchanged.
- **A resolved single peak:** MANIC fits a one-component model so that channel uses the same measurement as any sibling isotopologue or sample that needed a split. The selected curve is the fitted peak, not the raw samples.
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
- **A fit succeeds but does not reproduce the data (the fit-quality net):** after fitting, MANIC retains the model (`_fit_reproduces_window`) only if it reconstructs the integration window adequately (relative residual at or below `FIT_QUALITY_MAX_REL_RESIDUAL`). Neighbours in the wider fit context can still be modelled so they can be subtracted, but leftover intensity outside loffset/roffset does not veto a fit that matches the target peak. Extra candidate seeds (shoulders or leftover maxima) do not discard a one-component model that already matches. If the reconstruction is poor, MANIC discards the model and integrates the **raw trace**.
- **Unexpected numerical failure during fitting:** any error is caught and treated as "no usable model", routing to the same raw-trace fallback rather than propagating. This protects both interactive plotting and bulk export.

In summary, when deconvolution is on, every fittable channel is offered a peak model. A channel uses the raw trace when that window cannot be fit: off, too few points, too messy, no usable model, or a poor reconstruction. If any **non-empty** channel of a labelled compound/sample falls back, plots and export use the raw in-window scans for every non-empty channel of that pair (see [Failed ions put the whole envelope on scans](#failed-ions-put-the-whole-envelope-on-scans)). Empty channels stay zero and do not force that fallback. MANIC does not blank the plot or abort an export.

## Natural Abundance Correction preview

**Settings → Preview Natural Abundance Correction** changes only what the UI draws and what the Label Incorporation bars integrate. Export still fits the raw traces and then corrects that same selected component. If a compound has no correction formula or labelled atoms, preview keeps the raw fitted display and raw bars.

Preview on:

1. Fit the raw traces. The yes/no overlay decision stays on that raw fit.
2. If the compound supports correction, apply natural-abundance correction to that same measurement (the selected stack if overlays are on, otherwise the raw matrix with empty rows kept at zero).
3. When overlays are on, draw the corrected selected traces over a faint raw EIC. The raw context does not enter correction or integration. Otherwise, draw the corrected raw matrix.
4. When both layers are present, scale the y-axis to include both.

The toolbar bars and the tiles use the same raw fit. They do not re-fit stored `eic_corrected` traces. Preview draws corrected selected values at the acquisition scan times. Time-based bars and export integrate a denser evaluation of the same fitted model.

If the detailed-view display pipeline fails after the canvas was cleared, the dialog draws the raw EIC. The info strip reports an error only if that fallback also fails.

## Scientific Background

The method combines ideas from three common areas of chromatographic data processing:

- **Peak-shape fitting:** Gaussian, bi-Gaussian, and EMG functions are widely used to model chromatographic peaks, especially asymmetric tailing peaks.
- **Model selection:** BIC-style penalties are used to avoid unnecessary components or overly flexible peak shapes.
- **Single-channel peak fitting:** each isotopologue or diagnostic ion is fit on its own EIC. MANIC does not force those channels to share one elution shape.

Relevant literature:

- Foley, J. P. and Dorsey, J. G. (1984). *A review of the exponentially modified Gaussian (EMG) function: evaluation and subsequent calculation of universal data*. Journal of Chromatographic Science, 22, 40-46.
- Di Marco, V. B. and Bombi, G. G. (2001). *Mathematical functions for the representation of chromatographic peaks*. Journal of Chromatography A, 931, 1-30.
- Stein, S. E. (1999). *An integrated method for spectrum extraction and compound identification from gas chromatography/mass spectrometry data*. Journal of the American Society for Mass Spectrometry, 10, 770-781.
- Tautenhahn, R., Bottcher, C. and Neumann, S. (2008). *Highly sensitive feature detection for high resolution LC/MS*. BMC Bioinformatics, 9, 504.
- Yu, T. and Peng, H. (2010). *Quantification and deconvolution of asymmetric LC-MS peaks using the bi-Gaussian mixture model and statistical model selection*. BMC Bioinformatics, 11, 559.
- Kalambet, Y., Kozmin, Y., Mikhailova, K., Nagaev, I. and Tikhonov, P. (2011). *Reconstruction of chromatographic peaks using the exponentially modified Gaussian function*. Journal of Chemometrics, 25, 352-356.
- Wei, X., Shi, X., Kim, S., Patrick, J. S., Binkley, J., Kong, M., McClain, C. and Zhang, X. (2014). *Data dependent peak model based spectrum deconvolution for analysis of high resolution LC-MS data*. Analytical Chemistry, 86, 2156-2165.
