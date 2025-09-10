# Peak Height Validation in MANIC

## Overview

Peak height validation is a critical quality control measure in quantitative metabolomics that ensures reliable quantification by identifying samples with insufficient signal intensity. MANIC implements an automated peak validation system specifically designed for isotope labeling experiments.

## Scientific Rationale

### Why Peak Height Validation Matters

In mass spectrometry-based metabolomics, **signal-to-noise ratio** directly impacts quantification accuracy. Peaks with insufficient height relative to baseline noise can lead to:

- **Inaccurate integration**: Poor peak definition makes precise area calculation difficult
- **Quantification errors**: Low-intensity peaks are more susceptible to interference and baseline drift  
- **Reduced reproducibility**: Small peaks show higher coefficient of variation between technical replicates
- **False biological conclusions**: Unreliable measurements can mask or create apparent metabolic differences

### The Internal Standard Approach

MANIC uses your selected **internal standard** as the reference point for validation because:

1. **Same sample matrix**: The internal standard experiences identical sample preparation, extraction efficiency, and ionization conditions
2. **Known concentration**: Internal standards are added at defined amounts, providing a consistent reference
3. **Instrument performance**: Internal standard intensity reflects current instrument sensitivity and performance
4. **Sample-specific validation**: Each sample is validated against its own internal standard, accounting for sample-to-sample variation

## Validation Criteria

### What Gets Validated

- **m0 peaks only**: The validation specifically targets unlabeled isotope peaks (m0)
- **Rationale**: m0 peaks typically have the highest intensity in isotope labeling experiments, making them the best candidates for reliable quantification
- **Exclusions**: Labeled isotopes (m1, m2, etc.) are not validated as they may naturally have lower intensities due to incomplete labeling

### The 5% Threshold (Default)

The default threshold of **5% of internal standard height** is based on:

- **Analytical chemistry best practices**: Generally accepted minimum for reliable peak integration
- **Signal-to-noise considerations**: Provides adequate margin above typical baseline noise
- **Metabolomics literature**: Consistent with quality filters used in published studies
- **Practical experience**: Balances data quality with sample retention

### Customizable Thresholds

You can adjust the threshold based on your specific requirements:

- **Higher thresholds (10-20%)**: For high-precision studies requiring maximum reliability
- **Lower thresholds (1-3%)**: For exploratory work or when sample material is limited
- **Method validation**: Different analytical methods may require different thresholds

## Implementation in MANIC

### Automatic Validation Process

1. **Reference calculation**: System measures internal standard peak height in each sample
2. **Threshold determination**: Multiplies internal standard height by your chosen ratio (default 0.05)
3. **Peak comparison**: Compares each m0 peak height against the sample-specific threshold
4. **Visual indication**: Samples below threshold receive light red background highlighting

### Visual Indicators

- **Valid peaks**: Normal appearance, white background
- **Invalid peaks**: Light red background with subtle border
- **No internal standard**: No validation performed (all peaks appear normal)

## Best Practices

### Setting Appropriate Thresholds

Consider these factors when adjusting the minimum peak height ratio:

1. **Sample type**: Complex biological matrices may require higher thresholds
2. **Instrument sensitivity**: Newer, more sensitive instruments may allow lower thresholds  
3. **Study objectives**: Exploratory vs. quantitative studies have different requirements
4. **Statistical power**: Balance between data quality and sample size

### Quality Control Workflow

1. **Initial assessment**: Plot representative samples to evaluate typical signal levels
2. **Threshold optimization**: Adjust ratio to achieve appropriate sample inclusion/exclusion
3. **Systematic review**: Examine flagged samples to understand causes of low signal
4. **Documentation**: Record threshold rationale in your analytical methods

### Interpreting Results

When samples are flagged as invalid:

- **Sample-specific issues**: Low extraction efficiency, matrix effects, or sample degradation
- **Instrument performance**: Reduced sensitivity or maintenance requirements
- **Method limitations**: Compound may be near detection limit for your analytical conditions
- **Biological reality**: Some samples may naturally have low metabolite concentrations

## Technical Details

### Calculation Method

```
Threshold = Internal_Standard_Height × Minimum_Ratio
Validation = (m0_Peak_Height ≥ Threshold)
```

### Performance Considerations

- **Real-time calculation**: Validation occurs during plot generation
- **Minimal overhead**: Optimized to maintain MANIC's performance
- **Memory efficient**: Uses existing EIC data without additional storage

### Integration with MANIC Workflow

The validation system integrates seamlessly with existing MANIC features:

- **Export documentation**: Validation thresholds recorded in changelog.md
- **Session persistence**: Settings maintained throughout analysis session
- **Plot refreshing**: Validation updates automatically when parameters change

## Limitations and Considerations

### Current Limitations

- **m0 detection**: System uses compound naming heuristics to identify m0 peaks
- **Single threshold**: One ratio applied to all compounds (compound-specific ratios not yet supported)
- **Peak height only**: Does not consider peak area, width, or shape quality

### Future Enhancements

Potential improvements being considered:

- **Compound-specific thresholds**: Different ratios for different metabolite classes
- **Signal-to-noise calculation**: Direct measurement of noise levels
- **Peak quality metrics**: Integration of peak shape and symmetry factors

## Conclusion

Peak height validation provides an automated, scientifically-sound approach to quality control in isotope labeling experiments. By leveraging your internal standard as a sample-specific reference, MANIC helps ensure that quantitative conclusions are based on reliable measurements.

The visual feedback system makes it easy to identify potentially problematic samples while maintaining the flexibility to adjust validation criteria based on your specific analytical requirements.

---

**Remember**: This validation is a quality control tool, not an absolute judgment. Always consider the biological and analytical context when interpreting flagged samples.