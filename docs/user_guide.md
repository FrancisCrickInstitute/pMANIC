# User Guide

## Workflow

### Step 1: Load Compound Definitions

File → Load Compounds/Parameter List

Required Excel/CSV columns (header variants accepted; spaces/underscores ignored):
- `name`: Compound identifier
- `tr`: Retention time (minutes)
- `mass0`: Base m/z value
- `loffset`: Left integration offset (minutes)
- `roffset`: Right integration offset (minutes)
- `labelatoms`: Number of labelable positions
- `formula`: Molecular formula
- `labeltype`: Labeled element (e.g., C)
- `tbdms`: TBDMS groups
- `meox`: Methoxyamine groups
- `me`: Methyl groups
- `amount_in_std_mix`: Concentration in standards
- `int_std_amount`: Internal standard amount
- `mmfiles`: Standard mixture patterns (supports `*`, multiple separated by comma/semicolon)

If any required column is missing, the import is cancelled with an on-screen alert.

### Step 2: Import Mass Spectrometry Data

File → Load Raw Data (CDF)

The import process:
1. Reads CDF files
2. Extracts ion chromatograms for each compound
3. Stores EICs in database
4. Applies natural abundance correction (all compounds)

### Step 3: Configure Internal Standard

1. Right-click internal standard compound in left panel
2. Select "Set as Internal Standard"
3. Verify indicator shows selected compound

Requirements:
- Internal standard must have `labelatoms = 0`
- Must be present in all samples
- Requires `int_std_amount > 0` (per-sample dose)
- Requires `amount_in_std_mix > 0` (MM mix amount) for calibration/export

### Step 4: Review Integration

1. Select samples and compound
2. Check integration boundaries (blue dashed lines)
3. Adjust offsets if needed
4. Click "Apply" to update

Integration boundaries:
- Start: tr - loffset
- End: tr + roffset

### Step 5: Export Results

File → Export Data

Creates Excel workbook with five sheets:
- **Raw Values**: Uncorrected peak areas
- **Corrected Values**: Natural abundance-corrected
- **Isotope Ratios**: Normalized distributions
- **% Label Incorporation**: Background-corrected labeling
- **Abundances**: Absolute concentrations

> **Important:** The Abundances sheet now fails fast unless an internal standard is selected and both `int_std_amount` and `amount_in_std_mix` are present in the compound list.

## Visual Indicators

- **Peak validation**: m0 peaks below 5% of internal standard are highlighted in red
- **Integration boundaries**: Blue dashed lines show integration window
- **Selection**: Steel blue border indicates selected plots

## Advanced Features

### Session Management

**Export Session:** File → Export Session
- Saves compound definitions and integration parameters
- Does not include raw data

**Import Session:** File → Import Session
- Load compounds and raw data first
- Applies saved parameters

### Detailed View

Right-click any plot and click "view detailed" to see:
- Full chromatogram with integration boundaries
- Total ion chromatogram
- Mass spectrum at retention time

Double-click either of the left-toolbar summary plots to see and expanded view.

## Settings

### Mass Tolerance
Settings → Mass Tolerance
- Default: 0.2 Da
- Affects EIC extraction
- Requires data re-import after change

### Legacy Integration Mode
Settings → Legacy Integration Mode
- Off: Time-based integration (default)
- On: Unit-spacing integration (MATLAB compatible)

## Changes from MANIC v3.3.0 and Below

### Integration Method
- **Previous**: Unit-spacing produced values ~100× larger
- **Current**: Time-based integration (physically meaningful)

### Natural Abundance Correction
- **Previous**: Applied after integration
- **Current**: Per-timepoint correction before integration

### User Interface
- **Previous**: No visual quality indicators
- **Current**: Automatic peak validation with red highlighting
