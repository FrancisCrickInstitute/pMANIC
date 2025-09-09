# Getting Started with MANIC

## Overview

MANIC (Mass Analyzer for Natural Isotope Correction) processes isotope-labeled mass spectrometry data through natural isotope correction and internal standard calibration. This guide covers the essential workflow for generating quantitative results.

## Quick Start

### 1. Load Your Data
1. **File → Load Compound List**: Load your compound library (Excel/CSV file)
2. **File → Load EIC Data**: Load your chromatographic data files
3. Wait for natural isotope corrections to complete

### 2. Select Internal Standard
1. In the left panel, find your internal standard compound
2. Right-click and select "Set as Internal Standard"
3. Verify the internal standard indicator shows your selection

### 3. Export Results
1. **File → Export Data**
2. Choose output location
3. Open the Excel file - your final results are in the **Abundances** sheet (last tab)

## Output Structure

MANIC generates an Excel file with 5 worksheets representing different processing stages. The **Abundances** sheet (final tab) contains your quantitative results.

*For detailed explanations of each worksheet and the underlying calculations, see the [Data Interpretation Guide](data_interpretation.md).*

## Troubleshooting

### "Abundances are all zero"
- **Check internal standard**: Is it selected and detected in your samples?
- **Check MM files**: Are they properly identified in your compound library?
- **Check concentrations**: Do you have AmountInStdMix and IntStdAmount values?

### "Corrected values are zero"
- **Check compound configuration**: Internal standards should have `labelatoms = 0`
- **Check formula**: Make sure molecular formulas are correct
- **Check derivatization**: Verify TBDMS, MeOX, and methylation counts

### "Raw data missing"
- **File format**: Make sure EIC files are in the expected format
- **Compound names**: Verify compound names match between library and data files
- **Integration**: Check that peaks were properly integrated

## File Formats

### Compound Library
Required columns:
- `name`: Compound identifier
- `tr`: Retention time
- `mass0`: Base mass
- `loffset`, `roffset`: Integration windows
- `labelatoms`: Number of labelable positions (0 for internal standards)
- `formula`: Molecular formula
- `AmountInStdMix`: Concentration in standard mixture
- `IntStdAmount`: Internal standard amount added to samples
- `MMFiles`: Pattern to identify standard mixture files

### EIC Data Files
- Chromatographic peak areas for each isotopologue
- File names should match patterns in compound library
- Standard mixture files should be identifiable by MMFiles patterns

## Best Practices

1. **Always use an internal standard** - Required for absolute quantification
2. **Include standard mixtures** - Needed for accurate calibration
3. **Check natural abundance correction** - Verify corrected values look reasonable  
4. **Validate with known samples** - Test with samples of known concentration
5. **Keep backups** - MANIC clears previous data when loading new files

## Additional Resources

- **[Data Interpretation Guide](data_interpretation.md)**: Scientific explanations of all output worksheets
- **[Export Calculations](export_calculations.md)**: Mathematical details and formulas
- **[Mass Tolerance Settings](mass_tolerance.md)**: Optimizing peak matching parameters
- **[Natural Isotope Correction](natural_isotope_correction.md)**: Technical correction details

## Support

For technical issues:
- Check console output for error messages
- Verify file formats match expected structure
- Ensure compound library contains all required columns
- Validate that standard mixture files are properly identified

---

*This workflow guide focuses on the essential steps for data processing. For scientific interpretation of results, consult the Data Interpretation Guide.*