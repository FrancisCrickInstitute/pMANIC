# Data Interpretation Guide

## Overview

MANIC exports processed isotopologue data across five worksheets, each representing a specific stage in the analytical pipeline. This guide explains what each dataset represents, when to use it, and how the values relate to your experimental measurements.

## Worksheet Descriptions

### Raw Values
**Scientific Definition**: Direct integration of chromatographic peak areas without mathematical correction.

**Data Content**: 
- Uncorrected peak areas for each isotopologue (M+0, M+1, M+2, ...)
- Units: Instrument-dependent (typically area under curve)
- Contains: Natural isotope abundance, instrumental noise, matrix effects

**Appropriate Use Cases**:
- Quality control: Verifying peak detection and integration
- Troubleshooting: Identifying integration or detection problems
- Method validation: Assessing instrumental precision and accuracy

**Limitations**: 
- Cannot distinguish experimental labeling from natural abundance
- Not suitable for quantitative biological interpretation

### Corrected Values
**Scientific Definition**: Peak areas after mathematical deconvolution to remove natural isotope abundance contributions.

**Data Content**:
- Isotopologue intensities corrected for natural abundance of ¹³C, ¹⁵N, ²H, etc.
- Units: Same as raw values (area under curve)
- Represents: True distribution of experimentally incorporated isotopes

**Mathematical Approach**:
The correction solves the linear system: **A × x = b**
- **A**: Correction matrix (theoretical natural abundance patterns)  
- **b**: Measured isotopologue distribution (raw values)
- **x**: True isotopologue distribution (corrected values)

**Appropriate Use Cases**:
- Foundation for all quantitative calculations
- Isotopologue pattern analysis
- Comparing labeling between different experimental conditions

**Limitations**:
- Mathematical artifacts may occur with low signal intensities
- Requires accurate molecular formula and derivatization parameters

### Isotope Ratios  
**Scientific Definition**: Normalized corrected values where the sum of all isotopologues equals 1.0.

**Data Content**:
- Fractional representation of isotopologue distribution
- Units: Dimensionless (0-1 scale)
- Mathematical relationship: Ratio[M+i] = Corrected[M+i] / Σ(All Corrected Values)

**Appropriate Use Cases**:
- Comparing labeling patterns independent of absolute abundance
- Metabolic flux analysis where relative labeling is important
- Quality assessment of isotope incorporation efficiency

**Limitations**:
- Loss of absolute concentration information
- Cannot assess total metabolite pool changes

### % Label Incorporation
**Scientific Definition**: Percentage of metabolite molecules containing experimental isotope label, corrected for natural abundance contamination.

**Detailed Calculation Process**:

1. **Identify Standard Mixture Files**: For each compound, locate MM (standard mixture) files using pattern matching from the compound's `mm_files` column.

2. **Calculate Background Ratio from Standards**:
   ```
   Background_Ratio = Mean(Sum_of_Labeled_Isotopologues_in_Standards / M+0_Signal_in_Standards)
   ```
   - This represents the natural abundance "contamination" of heavier isotopes
   - Uses only MM files which contain unlabeled metabolites
   - Accounts for natural ¹³C, ¹⁵N, ³⁴S contamination in M+1, M+2, etc.

3. **Apply Background Correction to All Samples**:
   ```
   Expected_Natural_Abundance = Background_Ratio × Sample_M+0_Signal
   Corrected_Labeled_Signal = Raw_Labeled_Signal - Expected_Natural_Abundance
   ```
   - Removes the portion of M+1, M+2, etc. that comes from natural isotopes
   - Applied to every sample using the mean background ratio

4. **Calculate % Label Incorporation**:
   ```
   % Label = (Corrected_Labeled_Signal / Total_Signal) × 100
   
   where:
   - Total_Signal = M+0_Signal + Corrected_Labeled_Signal  
   ```

**Complete Mathematical Formula**:
```
Background_Ratio = Mean(Labeled_in_Standards / M0_in_Standards)
Corrected_Labeled = Raw_Labeled - (Background_Ratio × Sample_M0)
% Label = (Corrected_Labeled / Total_Signal) × 100
```

**Worked Example**:
- MM standards show M+1/M+0 = 0.1 (10% natural abundance background)
- Sample has M+0 = 1000 units, Raw M+1 = 300 units
- Expected natural M+1 = 0.1 × 1000 = 100 units
- Corrected M+1 = 300 - 100 = 200 units (true experimental labeling)
- Total signal = 1000 + 200 = 1200 units
- % Label = (200 / 1200) × 100 = 16.7%

**Appropriate Use Cases**:
- Measuring metabolic pathway activity and flux
- Assessing substrate utilization efficiency  
- Time-course studies of isotope incorporation
- Comparing labeling between different experimental conditions

**Requirements**:
- Standard mixture (MM) files containing unlabeled metabolites for background correction
- Sufficient signal in both labeled and unlabeled isotopologues

### Abundances (Quantitative Results)
**Scientific Definition**: Absolute metabolite concentrations calculated using internal standard calibration and metabolite response ratio factors (MRRF).

**MRRF Calculation Process**:

**Step 1: Calculate MRRF Values** (one-time, using standard mixtures)
```
MRRF[metabolite] = (Signal_Metabolite_Standard / Concentration_Metabolite_Standard) / 
                   (Signal_Internal_Standard / Concentration_Internal_Standard)
```

Where:
- `Signal_Metabolite_Standard`: Mean total corrected signal for target metabolite in its specified MM files
- `Concentration_Metabolite_Standard`: Known concentration in standard mixture (AmountInStdMix)
- `Signal_Internal_Standard`: Mean total corrected signal of internal standard in its specified MM files  
- `Concentration_Internal_Standard`: Known concentration of internal standard in MM files

**MM File Selection**: Each compound uses its own MM file pattern (specified in compound database). Patterns support comma-separation and wildcards (e.g., "*MM_01*,*MM_02*").

**Step 2: Calculate Sample Concentrations**
```
Abundance[sample] = (Total_Corrected_Signal[sample] × Internal_Standard_Amount) / 
                    (Internal_Standard_Signal[sample] × MRRF[metabolite])
```

Where:
- `Total_Corrected_Signal[sample]`: Sum of all corrected isotopologues for the metabolite
- `Internal_Standard_Amount`: Amount of internal standard added to each sample (IntStdAmount)
- `Internal_Standard_Signal[sample]`: Total corrected signal of internal standard in sample (sum of all isotopologues)
- `MRRF[metabolite]`: Pre-calculated response ratio factor

**Scientific Rationale**:
MRRF correction accounts for differential ionization efficiency, extraction recovery, and derivatization yield between metabolites and the internal standard.

**Appropriate Use Cases**:
- Quantitative metabolomics studies
- Comparing absolute concentrations between samples
- Pharmacokinetic and metabolic rate calculations

**Requirements**:
- Internal standard present in all samples with detectable signal
- Standard mixture files with known metabolite concentrations
- Proper compound library configuration (AmountInStdMix, IntStdAmount, MMFiles)

**Units**: 
Determined by the units used in compound library:
- AmountInStdMix and IntStdAmount should use consistent units (ng, μg, nmol, μmol, etc.)
- Final abundance values will be in the same units as IntStdAmount

## Data Quality Considerations

### Signal-to-Noise Requirements
- **Raw Values**: Sufficient for peak detection (typically S/N > 3)
- **Corrected Values**: Higher requirement (S/N > 10) for reliable mathematical correction
- **Quantitative Analysis**: Highest requirement (S/N > 50) for accurate abundance measurements

### Internal Standard Performance
- Should be chemically similar to target metabolites
- Must be stable throughout sample processing
- Should not co-elute with endogenous metabolites
- Requires consistent recovery across all samples

### Standard Mixture Validation
- Must contain the same metabolites as experimental samples
- Concentrations should span the expected biological range
- Should be prepared using the same analytical method
- Requires fresh preparation to avoid degradation

## Common Interpretation Errors

### Misuse of Raw Values for Quantitative Conclusions
**Problem**: Using raw values to compare labeling between samples
**Solution**: Always use corrected values or % label incorporation for biological interpretation

### Ignoring MRRF Limitations  
**Problem**: Assuming all metabolites have equal response factors
**Solution**: Include diverse metabolites in standard mixtures to validate MRRF accuracy

### Inadequate Internal Standard Signal
**Problem**: Low or variable internal standard signal leading to unreliable abundances
**Solution**: Optimize internal standard concentration and verify consistent addition

### Background Contamination
**Problem**: Contamination in unlabeled standards affecting % label incorporation calculations
**Solution**: Use multiple independent standard preparations and monitor blank samples

## Statistical Considerations

### Replication Requirements
- **Biological replicates**: Minimum n=3 for preliminary studies, n=5-6 for publication
- **Technical replicates**: Generally not necessary if instrumental precision is established
- **Standard mixtures**: Multiple independent preparations recommended

### Data Transformation
- **Log transformation**: May be appropriate for abundance data spanning multiple orders of magnitude
- **Normalization**: Consider tissue weight, protein content, or cell number for biological context
- **Missing values**: Handle systematically (detection limit imputation vs. exclusion)

### Quality Control Metrics
- **Coefficient of variation**: Should be <20% for quantitative measurements
- **Recovery**: Internal standard recovery should be 70-130% across samples  
- **Linearity**: Standard curve R² > 0.99 for quantitative methods

---

*This guide provides the scientific foundation for interpreting MANIC-processed data. Proper understanding of each dataset's characteristics and limitations is essential for valid biological conclusions.*