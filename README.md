# MANIC

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
