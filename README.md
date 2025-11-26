# MANIC

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Usage](#usage)
- [Data Processing](#data-processing)
- [Export Structure](#export-structure)
- [Advanced Features](#advanced-features)
- [Development](#development)
- [Changes from MANIC v3.3.0 and Below](#changes-from-manic-v330-and-below)
- [Technical Details](#technical-details)



## Documentation 

- [Getting Started](/docs/user_guide.md)
- [Data Interpretation](/docs/data_interpretation.md)

## Overview

MANIC processes isotopically-labeled mass spectrometry data through natural isotope abundance correction, peak integration, and metabolite quantification. The application reads CDF files from GC-MS and LC-MS instruments and generates Excel workbooks containing five analysis stages: Raw Values, Corrected Values, Isotope Ratios, % Label Incorporation, and Abundances.

## Installation

### Windows

1. Download `MANIC-Setup.exe` from the Releases page
2. Run the installer
3. Launch MANIC from the Start Menu or desktop shortcut

### macOS and Linux

```bash
# Clone repository
git clone https://github.com/yourusername/pythonMANIC.git
cd pythonMANIC

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv sync

# Run application
uv run python -m src.manic.main
```

## Usage

### Basic Workflow

1. **Load compound definitions**: File → Load Compounds/Parameter List
2. **Import CDF files**: File → Load Raw Data (CDF)
3. **Select internal standard**: Right-click compound → "Set as Internal Standard"
4. **Export results**: File → Export Data

### Input Files

#### Compound Definition File (Excel/CSV)

Required columns:
- `name`: Compound identifier
- `tr`: Retention time (minutes)
- `mass0`: Base m/z value
- `loffset`, `roffset`: Integration window offsets (minutes)
- `tr_window`: RT extraction window (±minutes)
- `labelatoms`: Number of labelable positions
- `formula`: Molecular formula
- `tbdms`, `meox`, `me`: Derivatization groups
- `amount_in_std_mix`: Concentration in standards
- `int_std_amount`: Internal standard amount
- `mmfiles`: Pattern to identify standard mixtures

## Data Processing

### Natural Isotope Abundance Correction

The correction solves the linear system **A × x = b** where:
- **A**: Correction matrix containing theoretical isotope patterns
- **b**: Measured isotopologue distribution
- **x**: True isotopologue distribution

The algorithm uses direct linear algebra for well-conditioned matrices (condition number < 10¹⁰) and constrained optimization (SLSQP) for ill-conditioned cases.

### Peak Integration

Two methods are available:

**Time-Based Integration (Default):**
```
Area = Σᵢ [(Iᵢ + Iᵢ₊₁)/2] × (tᵢ₊₁ - tᵢ)
```

**Legacy Unit-Spacing Integration:**
```
Area = Σᵢ [(Iᵢ + Iᵢ₊₁)/2]
```

Legacy mode produces values ~100× larger for compatibility with MATLAB MANIC v3.3.0.

### MRRF Calibration

Metabolite Response Ratio Factor calculation:
```
MRRF = (Signal_metabolite/Conc_metabolite) / (Signal_IS/Conc_IS)
```

Sample quantification:
```
Abundance = (Signal_sample × IS_amount) / (Signal_IS × MRRF)
```

### Mass Tolerance

MANIC uses an offset-and-round algorithm:
```python
offset_mass = detected_mass - tolerance_offset
rounded_mass = round(offset_mass)
match = (rounded_mass == target_integer_mass)
```

Default offset: 0.2 Da (configurable in Settings → Mass Tolerance)

## Export Structure

The Excel workbook contains five worksheets:

1. **Raw Values**: Integrated peak areas without correction
2. **Corrected Values**: Natural abundance-corrected peak areas
3. **Isotope Ratios**: Normalized isotopologue distributions (sum = 1.0)
4. **% Label Incorporation**: Background-corrected labeling percentage
5. **Abundances**: Absolute concentrations via MRRF calibration

## Advanced Features

### Session Management

- **Export Session**: Saves compound definitions and integration parameters (not raw data)
- **Import Session**: Applies saved parameters to new data

### Update Old Data

Reconstructs complete exports from:
- Compound definition file
- Previously exported Raw Values worksheet

This approximate mode applies natural abundance correction to integrated totals rather than per-timepoint data.

### Peak Validation

Compares m0 peak heights against internal standard signal. Default threshold: 5% of internal standard height. Invalid peaks are highlighted with red background.

## Development

### Environment Setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create environment
uv venv
source .venv/bin/activate

# Install dependencies
uv sync

# Run tests
./scripts/tests.sh
```

### Building Windows Executable

Using the convenience script:
```bat
scripts\build_windows.bat
```

Or manually:
```bat
# With uv
uv venv
uv sync
uv run pyinstaller MANIC.spec

# With pip
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller MANIC.spec

# Build installer (requires Inno Setup 6)
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\MANIC.iss
```

Output:
- Executable: `dist\MANIC\MANIC.exe`
- Installer: `dist\MANIC-Setup.exe`

## Changes from MANIC v3.3.0 and Below

### Integration Method
- **Previous**: Legacy unit-spacing as default
- **Current**: Time-based integration as default (legacy available in Settings)

### Natural Abundance Correction
- **Previous**: Correction after integration
- **Current**: Per-timepoint correction before integration with adaptive solver selection

### MRRF Calculation
- **Previous**: Sum-then-divide approach
- **Current**: Mean-based calculation

### Mass Tolerance
- **Previous**: Undocumented offset-and-round
- **Current**: Configurable offset with documented algorithm

## Technical Details

### Dependencies
- Core: NumPy, SciPy, Pandas
- Interface: PyQt6
- Data I/O: netCDF4, openpyxl
- Database: SQLite3

### File Formats
- Input: CDF, Excel (.xlsx), CSV
- Output: Excel (.xlsx), JSON (sessions)
- Internal: SQLite database (~/.manic_app/manic.db)

## Documentation

- [Getting Started](docs/getting_started.md)
- [Data Interpretation](docs/data_interpretation.md)
- [Integration Methods](docs/integration_methods.md)
- [Natural Isotope Correction](docs/natural_isotope_correction.md)
- [MRRF Calibration](docs/mrrf_calibration.md)
- [Mass Tolerance](docs/mass_tolerance.md)
- [Peak Validation](docs/peak_validation.md)
- [Update Old Data](docs/update_old_data.md)
