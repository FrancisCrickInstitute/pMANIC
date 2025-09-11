# MANIC

MANIC is a mass spectrometry data analysis application designed for processing and quantifying isotopically-labeled compounds from GC-MS or LC-MS data in CDF format.

## User Guide

### Overview

MANIC processes chromatographic mass spectrometry data to extract, integrate, and quantify compounds and their isotopologues. The application reads CDF files containing raw mass spectrometry data and uses compound definitions to extract specific ion chromatograms for analysis.

### Main Interface Components

#### 1. Left Toolbar
- **Status Indicators**: Shows loading status for raw data (CDF files) and compound definitions
  - Red: Not loaded
  - Green: Loaded successfully
- **Internal Standard Indicator**: Displays the selected internal standard compound
  - Red: No standard selected
  - Green: Standard selected (shows compound name)
- **Sample List**: Displays all loaded samples with multi-selection capability
- **Compound List**: Shows all defined compounds for analysis
- **Integration Parameters**: Displays and allows editing of:
  - Retention Time (RT): Expected elution time in minutes
  - Left Offset: Integration window start offset from RT (minutes)
  - Right Offset: Integration window end offset from RT (minutes)
  - TR Window: Retention time extraction window (±minutes from RT)
- **Label Incorporation Chart**: Horizontal stacked bar chart showing isotopologue ratios
- **Total Abundance Chart**: Horizontal bar chart showing integrated peak areas

#### 2. Main Display Area
- Grid view of extracted ion chromatograms (EICs)
- Each plot shows intensity vs. time for selected compound(s) and sample(s)
- Vertical guide lines indicate integration boundaries
- Scientific notation scaling applied automatically for large values

### Workflow

#### Basic Analysis Workflow

1. **Load Compound Definitions** (File → Load Compounds/Parameter List)
   - Excel file containing compound parameters:
     - Compound name
     - Retention time (minutes)
     - Target m/z value
     - Integration window parameters
     - Number of labeled atoms (for isotopologue analysis)

2. **Load Raw Data** (File → Load Raw Data (CDF))
   - Select CDF files from GC-MS or LC-MS instruments
   - Data is processed and stored in an internal database
   - EICs are automatically extracted based on compound definitions

3. **Select Samples and Compounds**
   - Use the sample list to select which samples to display
   - Select a compound from the compound list to view its EICs
   - Plots update automatically based on selections

4. **Review and Adjust Integration**
   - Visual inspection of integration boundaries (blue dashed lines)
   - Modify integration parameters if needed
   - Apply changes to update calculations

### Calculations and Methods

#### Extracted Ion Chromatogram (EIC) Generation

For each compound, MANIC extracts ion chromatograms using:
- **Target m/z**: The base mass-to-charge ratio
- **Mass tolerance**: Default 0.2 Da (adjustable in Settings)
- **RT window**: Extraction window around expected retention time
- **Isotopologue extraction**: Automatically extracts M+0, M+1, M+2... based on number of labeled atoms

The extraction process:
1. Filters raw MS data for ions within mass tolerance of target m/z
2. Restricts to retention time window (RT ± TR window)
3. Generates time-intensity traces for each isotopologue

#### Peak Integration

Integration uses trapezoidal numerical integration within defined boundaries:
- **Integration window**: RT - left_offset to RT + right_offset
- **Method**: Trapezoidal rule (numpy.trapz)
- **Baseline**: Currently no baseline correction applied
- Areas are calculated separately for each isotopologue

#### Isotopologue Ratio Calculation

For compounds with isotopic labeling:
1. Each isotopologue (M+0, M+1, M+2, etc.) is integrated separately
2. Ratios are calculated as: isotopologue_area / total_area
3. Total area = sum of all isotopologue areas
4. Displayed as stacked bar chart (0-1 scale representing 0-100%)

#### Total Abundance Calculation

Total abundance represents the sum of all isotopologue peak areas:
- For unlabeled compounds: single peak area
- For labeled compounds: sum of M+0, M+1, M+2... areas
- Values displayed with scientific notation scaling for clarity

### Features

#### Context Menu Options

**Compound List**:
- Right-click → "Select as Internal Standard": Designates compound for normalization

**Graph Area**:
- Right-click → "Select All": Select all displayed plots
- Right-click → "Deselect All": Clear selection
- Right-click → "View Detailed...": Opens detailed view with EIC, TIC, and mass spectrum

#### Detailed View

Double-clicking a plot or using "View Detailed..." shows:
- **Top panel**: Full EIC with integration boundaries
- **Middle panel**: Total Ion Chromatogram (TIC) for reference
- **Bottom panel**: Mass spectrum at compound retention time

#### Mass Spectrum Display

The mass spectrum shows:
- All ions detected at the retention time (±0.1 min tolerance)
- X-axis automatically scales to data range
- Target m/z indicated with vertical guide line
- Stem plot visualization for clarity

#### Plot Selection and Multi-Sample Analysis

- Click plots to select (steel blue border indicates selection)
- Shift-click for range selection
- Selected plots update the integration parameters display
- Integration parameters can be applied to all selected plots simultaneously

### Data Management

#### Session Export/Import

Sessions preserve analytical methods without including raw data:

**Export Contains**:
- Compound definitions and parameters
- Integration boundary adjustments
- Session-specific overrides
- Human-readable changelog

**Export Does NOT Contain**:
- Raw CDF files
- Processed EIC data
- Sample data

This separation ensures:
- Reproducible analysis from raw data
- Transparent methodology sharing
- Independent verification capability

#### Database Structure

MANIC uses an SQLite database for data management:
- Stores extracted EICs for rapid display
- Maintains compound definitions and parameters
- Tracks session-specific integration overrides
- Enables fast compound and sample switching

### Settings

#### Mass Tolerance
- Accessible via Settings → Mass Tolerance
- Default: 0.2 Da
- Defines the m/z window for ion extraction
- Affects EIC generation (requires data regeneration after change)

### Technical Details

#### File Format Support
- **Input**: CDF (Common Data Format) from mass spectrometers
- **Compound definitions**: Excel (.xlsx) format
- **Session export**: JSON with markdown documentation

#### Performance Optimizations
- Batch processing of CDF files
- Database caching of extracted EICs
- Efficient numpy-based calculations
- Multi-threaded data extraction

## Developer Instructions (MacOS/Linux)

### Install Package/Project Manager

Download [uv](https://github.com/astral-sh/uv) (if not already downloaded):
```bash
# On macOS and Linux.
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Set up the virtual environment

1. Create the virtual environment (if not already created):
```bash
uv venv
```

2. Activate the virtual environment:
```bash
source .venv/bin/activate
```

3. Install the project dependencies:
```bash
uv sync
```

Add dependencies:
```bash
uv add package-name
```

Remove dependencies:
```bash
uv remove package-name
```

Run scripts:
```bash
uv run python your_script.py
```

### Run the project

There are two ways to run the project:

```bash
./run.sh
```

or

```bash
uv run python -m src.manic.main
```

### Update Old Data (Approximate)

Use File → Update Old Data… to rebuild a MANIC export from:

- A compounds list (Excel/CSV; same columns as the normal importer)
- A Raw Values workbook (Excel; identical to MANIC's Raw Values sheet)

This tool generates all five sheets (Raw, Corrected, Isotope Ratios, % Label, Abundances) without reading the database. It is designed for legacy or partial data scenarios and intentionally operated in an approximate mode:

- Correction from integrated areas: Corrected Values are computed from integrated isotopologue totals (the Raw Values columns), not from per-timepoint EICs. The normal export corrects each timepoint and then integrates. Because natural abundance correction applies non‑negativity and may fall back to constrained optimization for ill‑conditioned cases, “correcting the sum” is not mathematically identical to “sum of per‑timepoint corrections”. This can introduce small differences.
- Background ratios and MRRF: These are computed against the provided samples using the same calibrated formulas, but rely on the approximate corrected totals above. Internal standard amount and MM sample identification are drawn from the provided compounds and sample names.
- Abundances: Calculated with the same formula as the normal export, but based on approximate corrected totals and MRRF built from those totals. Differences may be amplified compared to the normal export.

When exact reproducibility is needed, use the standard Export Data flow (which uses per‑timepoint corrections from the database). Update Old Data is maintained separately (with an in‑memory data provider) to keep the main export path predictable and to make the legacy flow self‑contained.

### Run tests

Use the helper script:

```bash
./tests.sh
```

- Prefers `uv` if installed: runs `uv run pytest -q`
- Falls back to `.venv` or system Python: runs `python -m pytest -q`

The suite covers core math and calibration modules:
- Integration: peak area computation and windowing behavior
- Calibration: background ratios and MRRF calculations (using stubbed providers)

## Session Export/Import

MANIC implements a session-centric approach to analytical sharing that prioritizes scientific reproducibility and data integrity. The export/import functionality separates analytical methodology from processed data, ensuring transparent and verifiable workflows.

### Session Export

The "Export Session..." feature saves only analytical parameters and compound definitions to a lightweight JSON file and human-readable changelog:

- Compound definitions (retention times, mass-to-charge ratios, integration boundaries)
- Session-specific integration overrides
- Analysis methodology and parameters

**Importantly, processed EIC data and raw CDF files are not included in exports.** This design enforces scientific best practices by requiring users to maintain and share raw data independently.

### Export Structure

Each export creates a `manic_session_export` directory containing:
- **JSON file** (e.g., `manic_session.json`) - Machine-readable analytical parameters
- **changelog.md** - Human-readable summary of compounds and integration overrides

### Session Import and Data Regeneration Workflow

The import process follows a structured three-step workflow that ensures data integrity and analytical reproducibility:

#### Step 1: Load Compounds
Load compound definitions using **File → Load Compounds/Parameter List**
- Import compound definitions from Excel files or method exports
- Sets up the analytical framework for data processing
- Defines target compounds, retention times, and integration parameters

#### Step 2: Load Raw CDF Data
Load the corresponding raw data files using **File → Load Raw Data (CDF)**
- Imports and processes raw chromatographic data
- Generates EIC traces using the loaded compound definitions
- Creates sample records in the database

#### Step 3: Import Session Overrides (Optional)
Import session-specific integration adjustments using **File → Import Session...**
- Applies custom integration boundaries from exported session files
- Overrides default integration parameters where manual adjustments were made
- Only available after both compounds and raw data have been loaded
- Uses the JSON file from the exported session directory

This workflow provides several scientific advantages:

**Data Integrity**: Each user independently processes raw data using the shared methodology, eliminating the possibility of corrupted or modified processed data affecting results.

**Reproducibility**: Results can be independently verified by applying the exact analytical parameters to the original raw data, meeting gold-standard requirements for scientific reproducibility.

**Transparency**: The complete analytical pipeline is preserved and executed transparently, with no "black box" processed data that cannot be independently verified.

**Method Validation**: Reviewers and collaborators can validate both the analytical approach and its implementation by examining the session parameters and confirming results through independent processing.

**Future Compatibility**: Session files contain only parameter definitions, ensuring compatibility across software versions and preventing obsolescence of archived analytical workflows.

**Documentation**: The changelog.md file provides human-readable documentation of all compounds and integration adjustments, making it easy to understand and review the analytical approach without parsing JSON.
