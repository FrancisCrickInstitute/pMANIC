# Mass Tolerance Settings

## Overview

Mass tolerance is a critical parameter that determines how precisely MANIC matches theoretical masses to actual mass spectrometry peaks. Proper tolerance settings ensure accurate peak identification while avoiding false matches.

## What is Mass Tolerance?

Mass tolerance defines the acceptable difference (in Daltons) between:
- **Theoretical mass**: Calculated exact mass of your compound + derivatization
- **Measured mass**: Actual m/z value detected by the mass spectrometer

### Example
If you're looking for glucose (exact mass 180.0634 Da) with a tolerance of ±0.1 Da:
- **Accept peaks between**: 179.9634 to 180.1634 Da
- **Reject peaks outside**: This range (even if chromatographically correct)

## How Tolerance Affects Analysis

### Too Loose (High Tolerance)
**Problems:**
- **False positives**: Wrong compounds matched to your targets
- **Interference**: Background peaks included in quantification
- **Poor specificity**: Multiple compounds matched to same peak

**Example**: Tolerance = ±1.0 Da
- Glucose (180.063 Da) might match fructose (180.063 Da) or other similar masses
- Background chemicals could be misidentified as metabolites

### Too Tight (Low Tolerance)  
**Problems:**
- **Missing peaks**: Real compound peaks rejected due to mass accuracy limits
- **Poor sensitivity**: Fewer peaks detected, lower signal
- **Instrument dependency**: May not work across different MS systems

**Example**: Tolerance = ±0.001 Da
- Requires exceptional mass accuracy (< 1 ppm error)
- May miss peaks due to instrument drift, calibration issues
- Could exclude real metabolite signals

### Optimal Tolerance
**Goal**: Maximum sensitivity while maintaining specificity
- **Instrument-dependent**: Based on your MS system's mass accuracy
- **Compound-dependent**: Higher mass compounds may need wider tolerance
- **Method-dependent**: Different for different analytical approaches

## Recommended Settings by Instrument Type

### High-Resolution Mass Spectrometers
**Examples**: Orbitrap, FT-ICR, Q-TOF
- **Typical tolerance**: ±0.005 to ±0.02 Da (2-10 ppm)
- **Mass accuracy**: < 5 ppm typical
- **Use case**: Confident compound identification, complex mixtures

### Quadrupole Mass Spectrometers  
**Examples**: Single quad, triple quad, ion trap
- **Typical tolerance**: ±0.1 to ±0.5 Da
- **Mass accuracy**: 50-100+ ppm typical  
- **Use case**: Targeted analysis, known compound lists

### GC-MS Systems
**Examples**: Electron impact (EI), chemical ionization (CI)
- **Typical tolerance**: ±0.1 to ±1.0 Da
- **Mass accuracy**: Moderate, depends on calibration
- **Use case**: Derivatized metabolomics, volatile compounds

## Setting Mass Tolerance in MANIC

### Location
**Menu**: Settings → Set Mass Tolerance

### Default Value
- **Default**: 0.1 Da (suitable for most GC-MS systems)
- **Range**: 0.001 to 10.0 Da (practical limits)

### When to Change
1. **Before importing data**: Tolerance affects peak matching during import
2. **New instrument**: Different MS systems require different tolerances  
3. **Poor peak matching**: If compounds aren't being detected properly
4. **After calibration**: Mass accuracy may improve after instrument tuning

### Impact on Data Processing
⚠️ **Important**: Mass tolerance changes only affect **new data imports**
- **Existing data**: Not affected by tolerance changes
- **Re-processing**: May need to re-import CDF files with new tolerance
- **Database**: Previous matches stored permanently until re-import

## Optimization Strategy

### Step 1: Know Your Instrument
- **Check specifications**: Look up mass accuracy in instrument manual
- **Test with standards**: Measure known compounds to assess actual accuracy
- **Monitor calibration**: Track mass accuracy over time

### Step 2: Start Conservative
- **Begin loose**: Start with wider tolerance (e.g., ±0.1 Da)
- **Check matches**: Verify compounds are being detected correctly
- **Gradually tighten**: Reduce tolerance while monitoring detection rates

### Step 3: Validate Results
- **Known standards**: Test with reference compounds
- **Peak quality**: Check that matched peaks have good peak shapes
- **Retention times**: Ensure matches have expected chromatographic behavior
- **Quantitative accuracy**: Verify concentration measurements are reasonable

## Troubleshooting

### Problem: "No peaks detected for my compounds"
**Possible causes:**
- Tolerance too tight for instrument accuracy
- Compound masses calculated incorrectly  
- Derivatization settings wrong in compound library

**Solutions:**
1. Increase mass tolerance temporarily
2. Check compound formulas and derivatization counts
3. Verify instrument calibration
4. Review raw chromatogram for expected retention times

### Problem: "Wrong compounds being matched"
**Possible causes:**
- Tolerance too loose allowing false matches
- Similar masses in compound library
- Background interference

**Solutions:**
1. Decrease mass tolerance
2. Review compound library for duplicate/similar masses
3. Improve chromatographic separation
4. Check for common background contaminants

### Problem: "Inconsistent results between runs"
**Possible causes:**
- Mass accuracy drifting over time
- Instrument calibration issues
- Temperature/pressure effects on mass accuracy

**Solutions:**
1. Regular instrument calibration
2. Use slightly wider tolerance to account for drift
3. Monitor quality control standards
4. Consider mass accuracy trends over time

## Advanced Considerations

### Mass Accuracy vs. Resolution
- **Mass accuracy**: How close measured mass is to true mass (ppm error)
- **Resolution**: Ability to distinguish between close masses (m/Δm)
- **Both matter**: Need good accuracy AND resolution for tight tolerances

### Isotope Pattern Considerations
- **Monoisotopic mass**: Most accurate for tolerance calculations
- **Isotope clusters**: May affect apparent mass measurement
- **Average vs. monoisotopic**: Ensure consistent mass calculation method

### Chemical Background
- **Solvent peaks**: Common solvents have known masses to avoid
- **Derivatization reagents**: TBDMS, MeOX artifacts have specific masses
- **Column bleed**: Stationary phase degradation creates background peaks

## Technical Implementation

### Code Location
- **File**: Settings menu in main window
- **Parameter**: Stored in application settings
- **Usage**: Applied during CDF file import and peak matching

### Database Storage
- **Peak matches**: Stored permanently until data re-import
- **Tolerance value**: Not stored with data (parameter only)
- **Re-processing**: Requires fresh data import with new tolerance

## Best Practices

1. **Document settings**: Record tolerance values used for each dataset
2. **Validate with standards**: Always test with known reference compounds
3. **Monitor over time**: Track mass accuracy performance regularly
4. **Conservative approach**: Start wider, then optimize based on results
5. **Instrument-specific**: Develop standard tolerances for each MS system
6. **Quality control**: Include mass accuracy checks in routine analysis

---

*Proper mass tolerance settings are fundamental to accurate peak identification and reliable quantification in mass spectrometry-based metabolomics.*