# Mass Tolerance Settings

## Overview

Mass tolerance is a critical parameter that determines how MANIC matches theoretical masses to actual mass spectrometry peaks. Unlike conventional ±tolerance methods, MANIC uses an asymmetric offset-and-rounding approach designed to correct for systematic mass calibration drift in GC-MS data.

## MANIC's Mass Matching Method

MANIC uses a unique **offset + rounding** approach instead of traditional symmetric tolerance:

### The Algorithm
1. **Offset**: Subtract the tolerance value from all detected masses
2. **Round**: Round the offset masses to nearest integer
3. **Match**: Accept peaks where the rounded value equals the target mass

### Mathematical Implementation
```
offset_mass = detected_mass - tolerance_offset
rounded_mass = round(offset_mass)
match = (rounded_mass == target_integer_mass)
```

### Example with Mass 319 and 0.2 Da Tolerance

**MANIC's Method** (Asymmetric):
- **Detected mass 318.7**: 318.7 - 0.2 = 318.5 → rounds to 319 ✓ **Accepted**
- **Detected mass 319.0**: 319.0 - 0.2 = 318.8 → rounds to 319 ✓ **Accepted**  
- **Detected mass 319.5**: 319.5 - 0.2 = 319.3 → rounds to 319 ✓ **Accepted**
- **Detected mass 319.7**: 319.7 - 0.2 = 319.5 → rounds to 320 ✗ **Rejected**

**Effective acceptance range**: 318.7 to 319.5 (0.8 Da window, biased toward lower masses)

**Traditional ±0.2 Da Method** (Symmetric):
- **Detected mass 318.7**: Too low ✗ **Rejected**
- **Detected mass 318.8**: 319 ± 0.2 ✓ **Accepted** 
- **Detected mass 319.2**: 319 ± 0.2 ✓ **Accepted**
- **Detected mass 319.3**: Too high ✗ **Rejected**

**Effective acceptance range**: 318.8 to 319.2 (0.4 Da window, symmetric)

## Key Differences from Traditional Methods

### Window Size and Shape
- **MANIC**: Creates wider acceptance windows (up to ~0.8 Da for 0.2 Da tolerance)
- **Traditional**: Narrower symmetric windows (0.4 Da for ±0.2 Da tolerance)
- **Bias**: MANIC shifts acceptance toward lower m/z values

### Why MANIC Uses This Approach
**Purpose**: Corrects for systematic mass calibration drift in GC-MS instruments
- **GC-MS behavior**: Instruments often read higher masses for larger fragments
- **Calibration compensation**: The offset corrects for this instrumental bias
- **Unit mass assignment**: Rounding ensures clean integer mass matching

### Effects of Different Tolerance Values

**Too Large (e.g., 0.5 Da offset)**:
- **Wider windows**: Up to ~1.0 Da acceptance range
- **More false positives**: Background peaks may be included
- **Lower specificity**: Multiple compounds may match the same mass

**Too Small (e.g., 0.05 Da offset)**:
- **Narrower windows**: ~0.1 Da acceptance range  
- **Missing real peaks**: Instrument drift may exclude valid signals
- **Higher specificity**: But reduced sensitivity for target compounds

**Optimal Range**: Typically 0.1-0.3 Da for GC-MS systems
- Balances sensitivity and specificity
- Accounts for typical instrument mass accuracy
- Provides effective calibration correction

## Recommended Settings by Instrument Type

### GC-MS Systems (Primary MANIC Application)
**Examples**: Electron impact (EI), chemical ionization (CI)
- **Recommended offset**: 0.1 to 0.3 Da
- **Effective window**: ~0.2 to 0.6 Da (asymmetric)
- **Typical choice**: 0.2 Da (MANIC default)
- **Rationale**: Optimized for derivatized metabolomics with mass calibration correction

### High-Resolution MS (if using MANIC method)
**Examples**: Orbitrap, FT-ICR, Q-TOF  
- **Recommended offset**: 0.05 to 0.1 Da
- **Effective window**: ~0.1 to 0.2 Da (asymmetric)
- **Consideration**: May be overly restrictive due to excellent mass accuracy
- **Alternative**: Consider traditional ±tolerance methods for HR-MS

### Quadrupole Systems
**Examples**: Single quad, triple quad, ion trap
- **Recommended offset**: 0.2 to 0.4 Da
- **Effective window**: ~0.4 to 0.8 Da (asymmetric)  
- **Use case**: Targeted metabolomics where mass drift is expected

## Setting Mass Tolerance in MANIC

### Location
**Menu**: Settings → Mass Tolerance...

### Default Value
- **Default**: 0.2 Da (optimized for GC-MS systems with derivatization)
- **Range**: 0.01 to 1.0 Da (practical limits)
- **Interpretation**: This is the **offset value**, not a ±tolerance range

### When to Adjust
1. **Before importing data**: Tolerance affects peak matching during import
2. **Mass calibration drift**: If your instrument consistently reads high/low
3. **Poor peak detection**: If expected compounds aren't being found
4. **Different instrument types**: HR-MS may need smaller offsets (0.05-0.1 Da)
5. **Systematic bias observed**: Adjust based on standard compound behavior

### Impact on Data Processing
⚠️ **Critical**: Mass tolerance changes only affect **new data imports**
- **Existing data**: Unaffected by tolerance setting changes
- **Re-import required**: Must reload CDF files to apply new tolerance
- **Database storage**: Previous peak matches persist until data re-import
- **Session data**: Natural abundance corrections use existing peak matches

## Optimization Strategy

### Step 1: Understand Your Instrument's Mass Bias
- **Check specifications**: Review mass accuracy specifications in manual
- **Test with standards**: Analyze known compounds to identify systematic bias
- **Mass shift analysis**: Compare detected vs. theoretical masses for standards
- **Monitor over time**: Track mass drift and calibration stability

### Step 2: Start with Default and Adjust
- **Begin with 0.2 Da**: MANIC's default works for most GC-MS systems
- **Check detection rates**: Verify expected compounds are being found
- **Analyze missed peaks**: If compounds are missing, consider increasing offset
- **Monitor false positives**: If too many background peaks match, decrease offset

### Step 3: Validate the Offset Setting
- **Standard compounds**: Ensure known metabolites are correctly identified
- **Mass distribution**: Check that detected masses cluster appropriately
- **Retention time correlation**: Verify matches have expected chromatographic behavior  
- **Quantitative consistency**: Confirm concentration measurements are reasonable

## Troubleshooting

### Problem: "No peaks detected for my compounds"
**Possible causes:**
- Offset too small for instrument's mass bias
- Compound masses calculated incorrectly  
- Derivatization settings wrong in compound library
- Instrument reading significantly higher than expected

**Solutions:**
1. **Increase offset temporarily** (e.g., from 0.2 to 0.3 Da)
2. **Check compound formulas** and derivatization counts
3. **Analyze mass bias**: Compare detected vs. theoretical masses for standards
4. **Review raw data**: Check if peaks exist at expected retention times

### Problem: "Too many false positive matches"
**Possible causes:**
- Offset too large creating overly wide acceptance windows
- High background noise in mass spectra
- Multiple compounds with similar integer masses

**Solutions:**
1. **Decrease offset** (e.g., from 0.2 to 0.15 Da)
2. **Review compound library** for overlapping integer masses
3. **Improve sample preparation** to reduce background
4. **Check retention time windows** to reduce integration of noise

### Problem: "Inconsistent mass matching between runs"
**Possible causes:**
- Instrument mass calibration drifting over time
- Temperature effects on mass accuracy
- Ion source contamination affecting calibration

**Solutions:**
1. **Regular instrument calibration** and maintenance
2. **Monitor QC standards** for mass drift patterns
3. **Adjust offset based on drift** (increase if drift is toward higher masses)
4. **Use wider offset range** to accommodate expected drift (e.g., 0.25 Da instead of 0.2 Da)

## Advanced Considerations

### Why Offset-and-Round vs. Traditional Tolerance?
- **Systematic bias correction**: Addresses consistent instrument mass drift
- **Unit mass focus**: Ensures clean integer mass assignments for GC-MS
- **Wider effective windows**: Increased sensitivity while maintaining specificity
- **Historical precedent**: Based on original MATLAB MANIC algorithm design

### Integration with Natural Abundance Correction
- **Peak matching first**: Mass tolerance determines which peaks are included
- **Correction matrix**: Uses the matched peaks for isotope deconvolution
- **Quality impact**: Poor mass matching affects correction accuracy
- **Re-import effects**: Tolerance changes require both re-import and re-correction

### Instrument-Specific Considerations
- **GC-MS calibration drift**: Higher mass fragments often read systematically high
- **Ion source effects**: Temperature and contamination affect mass accuracy
- **Derivatization artifacts**: TBDMS and MeOX groups may shift apparent masses
- **Matrix effects**: Complex samples may affect mass measurement precision

## Technical Implementation

### Algorithm Location
- **File**: `src/manic/io/eic_importer.py` 
- **Function**: `_extract_eic_optimized()`
- **Method**: `offset_masses = detected_mass - tolerance_offset`

### Settings Storage
- **UI Location**: Settings → Mass Tolerance...
- **Default value**: 0.2 Da in main window initialization
- **Database**: Peak matches stored permanently until data re-import
- **Worker thread**: Passes tolerance value to import functions

## Best Practices

1. **Start with default**: 0.2 Da works for most GC-MS metabolomics applications
2. **Validate with standards**: Test with known compounds before processing samples
3. **Monitor detection rates**: Ensure expected metabolites are being found
4. **Document settings**: Record offset values used for each dataset
5. **Instrument-specific optimization**: Develop standard offsets for each MS system
6. **Regular validation**: Check mass matching quality with QC standards

---

*MANIC's offset-and-rounding mass tolerance method is specifically designed for GC-MS metabolomics, providing systematic mass calibration correction while ensuring robust peak identification.*