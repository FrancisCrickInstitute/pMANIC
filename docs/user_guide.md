# User Guide


## Step 1: Load Compound Definitions

**Objective**   
Initialise the analysis session by importing a library of target metabolites and their specific integration parameters.

**File Requirements**   
Prepare an Excel (`.xlsx`, `.xls`) or CSV (`.csv`) file containing the columns listed below.

*Note: Column headers are flexible. They are case-insensitive and ignore spaces or underscores (e.g., `Int Std Amount`, `int_std_amount`, and `IntStdAmount` are all treated as the same field).*

| Column | Description |
| :--- | :--- |
| `name` | Unique compound identifier |
| `tr` | Retention time (minutes) |
| `mass0` | Base m/z value |
| `loffset` | Left integration offset (minutes) from tR |
| `roffset` | Right integration offset (minutes) from tR |
| `labelatoms` | Number of positions capable of retaining label |
| `formula` | Molecular formula (e.g., C6H12O6) |
| `labeltype` | Element being labeled (e.g., C) |
| `tbdms` | Number of TBDMS derivatization groups |
| `meox` | Number of Methoxyamine derivatization groups |
| `me` | Number of Methylation groups |
| `amount_in_std_mix`| Concentration in standard mixture |
| `int_std_amount` | Amount of internal standard added to samples |
| `mmfiles` | Pattern to identify standard mixture files (supports wildcards like `*MM*`) |

> **Tip:** To see a working template, download the `example_compound_list.xls` file from the repository.

**Procedure**
1.  Navigate to **File → Load Compounds/Parameter List**.
2.  Select your prepared compound definition file from the file dialog.

**Verification**
Upon a successful import, the application provides immediate visual feedback:
* The **Compounds** status indicator in the top-left toolbar will turn **green**.
* The compound list widget (located below the status indicators) will populate with the names of all imported compounds.

*If any required columns are missing from your file, the import process will be cancelled and an alert will display the specific missing headers.*


## Step 2: Import Mass Spectrometry Data

**Objective**   
Import raw experimental data files for processing. The application will extract Extracted Ion Chromatograms (EIC) for every compound defined in Step 1 and apply natural abundance corrections.

**Prerequisites**   
* **Compound Definitions Loaded:** You must complete [Step 1](#step-1-load-compound-definitions) first. The application requires the compound library to know which masses to extract.
* **File Format:** Data must be in **NetCDF (`.CDF`)** format.
* **File Organization:** Ensure all CDF files for the experiment (samples and standards) are located in the same directory.

**Configuration Note**   
The import process uses the global **Mass Tolerance** setting (Default: 0.2 Da) to bin detected masses.
* To check or change this: Go to **Settings → Mass Tolerance...** *before* loading data.
* *Note: If you change the tolerance later, you will need to re-import the data.*

**Procedure**   
1.  Navigate to **File → Load Raw Data (CDF)**.
2.  In the dialog window, select the **Directory (Folder)** containing your CDF files.
    * *Note: You are selecting the folder itself, not individual files.*
3.  Click **Select Folder** to begin the import.

A progress bar will appear as the application:   
1.  Reads CDF files.
2.  Extracts ion chromatograms for each defined compound.
3.  Stores EIC data in the local database.
4.  Calculates and applies natural abundance corrections.

**Verification**   
Upon completion, verify the data loaded correctly:
* The **Raw Data** status indicator in the top-left toolbar will turn **green**.
* The **Samples** list widget (left sidebar) will populate with the filenames of your imported samples.
* Selecting a sample and a compound will display the chromatogram in the main view.


## Step 3: Configure Internal Standard

**Objective**   
Designate the reference compound used for normalization and quantification (MRRF calculation).

**Prerequisites**   
The selected compound must meet specific criteria in your compound definition file (from Step 1):
* **Unlabeled:** `labelatoms` should be `0`.
* **Sample Dose:** `int_std_amount` must be defined and `> 0`. This is the amount added to every experimental sample.
* **Calibration Amount:** `amount_in_std_mix` must be defined and `> 0`. This is the concentration present in the standard mixture (MM) files.
* **Universal Presence:** The compound must be detectable in all samples and standards.

> **Tip (Auto-Selection):** If your compound list includes "scyllo-inositol" and has a valid `int_std_amount`, MANIC attempts to select it automatically upon loading. Check the verification step below to see if this has already occurred.

**Procedure**   
1.  Locate the **Compounds** list widget in the left sidebar.
2.  **Right-click** on the name of your internal standard compound.
3.  Select **"Set as Internal Standard"** from the context menu.

**Verification**   
Confirm the selection was applied:
* The **Standard** status indicator (located below the data indicators) will turn **green**.
* The text inside the indicator will change to display the name of the selected compound (e.g., `-- scyllo-Inositol --`).

*Note: If you proceed to "Export Data" without a valid internal standard selected (or if the selected compound is missing the required amount fields), the export process will be aborted to prevent invalid quantification.*


## Step 4: Review Integration

**Objective**   
Visually verify that the integration window captures the correct peak for every sample and adjust parameters where necessary. This ensures quantitative accuracy by excluding noise and adjacent peaks while capturing the full metabolite signal.

**The Main Graph View**   
Upon selecting a compound, MANIC displays a grid of mini-plots, one for each active sample.
* **Black Solid Line:** The expected Retention Time (`tR`).
* **Blue Dashed Lines:** The integration boundaries (`tR - loffset` and `tR + roffset`).
* **Background Color:**
    * **White:** Good peak (area is above threshold).
    * **Red:** Weak peak (area is < 5% of internal standard).
    * **Green:** Currently selected for editing.

**Procedure**

#### 1. Visual Inspection
Scan the grid of plots. Look for:
* **Peak Centering:** Is the peak centered on the black line? If retention times have shifted, you may need to adjust the `tR`.
* **Peak Coverage:** Do the blue dashed lines fully bracket the peak without cutting off "tails" or including neighboring noise?
* **Validation:** Pay attention to plots with **red backgrounds**. These indicate potential issues (low signal or missed peaks) that require manual review.

#### 2. Detailed Inspection (Optional)
For ambiguous peaks, inspecting the raw data more closely might be helpful:
1.  **Right-click** on any specific plot in the grid.
2.  Select **View Detailed...**.
3.  A window will open showing three synchronized views:
    * **Extracted Ion Chromatogram (EIC):** Zoomable view of the peak.
    * **Total Ion Chromatogram (TIC):** To see global elution context.
    * **Mass Spectrum:** The actual mass spectrum at compound retention time.
4.  Use the toolbar to **Zoom (🔍)** or **Pan (✋)**.

#### 3. Selecting Samples to Adjust
You can adjust integration parameters for all samples at once or for specific outliers.
* **Edit All:** Click "Deselect All" (or click empty space). The Integration Window will show "Selected Plots: All". Changes will apply globally.
* **Edit Specific Samples:** Click on individual plots to select them (they will turn green). You can also drag a box to select multiple. The Integration Window will show "Selected Plots: X samples". Changes apply *only* to the selection.

#### 4. Adjusting Boundaries (Integration Window)
Locate the **Integration Window** panel (middle-left).
* **Left Offset / Right Offset:** Controls the width of the window. Increase these to capture wider peaks; decrease to exclude adjacent peaks.
* **tR (Retention Time):** Shifts the center of the window. Use this to align the window with shifted peaks.

*Note: If multiple samples are selected with different values, the fields will display a range (e.g., `0.2 - 0.4`). Typing a new value will overwrite all selected samples with that single value.*

#### 5. Applying Changes
1.  Enter your new values in the text fields.
2.  Click **Apply** (or press Enter).
3.  The plots will refresh immediately to show the new boundaries.

> **Auto-Regeneration Feature:** If you widen the boundaries beyond the data MANIC originally extracted from the CDF file, the software will automatically re-read the raw file to fetch the missing data. A progress bar will appear during this process.

#### 6. Troubleshooting: Fixing Cut-off Peaks
Sometimes a peak may shift so far that part of it is completely missing from the plot (cut off by the edge of the extracted data). You cannot integrate what isn't there.

To fix this, you must widen the underlying data extraction window:
1.  Locate the **tR Window** field in the Integration Window panel.
2.  Increase the value (e.g., from `0.2` to `0.4` or `0.5`).
3.  Click **Update tR Window**.

A progress bar will appear as MANIC re-scans the raw CDF files to extract a wider slice of time around the target peak.

> **Important Note:** This update applies to **all samples** for the currently selected compound to ensure consistent data extraction. It does *not* affect other compounds in your library.

#### 7. Resetting Overrides
If you make a mistake or want to revert to the original library definitions:
1.  Select the target plots.
2.  Click the **Reset** button in the Integration Window.
3.  This removes all session-specific overrides for those samples.


## Step 5: Export Results

**Objective**   
Generate the final analytical report. This process calculates all results, applies MRRF calibration, and produces two files: a comprehensive Excel workbook and a detailed session changelog.

**Prerequisites**   
* **Internal Standard:** You must have a valid internal standard selected (see [Step 3](#step-3-configure-internal-standard)). The export option will be disabled otherwise.
* **Data Validity:** Ensure all required metadata (especially `int_std_amount` and `amount_in_std_mix`) is present in your compound definitions.

**Procedure**   

1.  Navigate to **File → Export Data...**.
2.  In the file dialog, choose a name and location for your output file (e.g., `experiment_results.xlsx`) and click **Save**.
3.  **Select Integration Method:** A dialog will appear asking you to choose a mode:
    * **Time-based (Recommended):** Calculates peak areas using actual time units (intensity × minutes). This is the scientifically accurate default.
    * **Legacy (MATLAB-compatible):** Uses unit-spacing integration (sum of intensities). Use this *only* if you need to match numerical values from the legacy MATLAB tool (values will be ~100× larger).
4.  Click **OK** to begin processing.

> **Note on Processing:** MANIC will perform a final check to ensure natural isotope corrections have been applied. If not, a progress bar will appear as it calculates these corrections for all labeled compounds to ensure data integrity.

**Output Files**   
The export generates two files in your selected directory:
1.  **Data File (`.xlsx`):** The multi-sheet workbook containing your results.
2.  **Changelog (`changelog_YYYYMMDD_HHMM.md`):** A text file documenting the exact parameters used for this analysis, including software version, date, and a table of all session-specific integration overrides. This serves as an audit trail for reproducibility.

**Workbook Structure**   
The Excel file contains five worksheets representing successive stages of analysis:

| Worksheet | Description |
| :--- | :--- |
| **1. Raw Values** | Direct instrument signals (uncorrected peak areas). Useful for quality control and verifying raw signal strength. |
| **2. Corrected Values** | Peak areas after mathematical deconvolution to remove natural isotope abundance. This is the "clean" signal representing true experimental labeling. |
| **3. Isotope Ratios** | Normalized distributions where all isotopologues for a compound sum to 1.0. Used for comparing labeling patterns independent of concentration. |
| **4. % Label Incorporation** | The percentage of the metabolite pool that has incorporated the experimental label. Includes background correction derived from standard (MM) files. |
| **5. Abundances** | Absolute metabolite amounts (in nmol). Calculated using the internal standard and MRRF calibration. |

**Validation & Errors**   
* **Invalid Peaks:** Cells corresponding to peaks that failed the minimum area validation (red plots) will be highlighted with a **light red background** in the Excel file.
* **Abundance Errors:** If the internal standard is missing required calibration fields (`int_std_amount` or `amount_in_std_mix`), the export will stop with an error message to prevent the generation of incorrect quantitative data.


## 6. Session Management

MANIC allows you to save the "state" of your analysis—including all compound definitions, integration boundaries, and manual overrides—without duplicating the large raw data files.

### Export Session
**File → Export Session...**
* **Function:** Creates a `.json` file containing your analytical method and a human-readable changelog.
* **What is saved:** Compound library, retention times, and all integration offsets (global and sample-specific).
* **What is NOT saved:** The raw mass spectrometry data (CDF content).
* **Use Case:** Archiving your analysis method or sharing it with a colleague who has the same raw files.

### Import Session
**File → Import Session...**
* **Function:** Applies saved integration parameters to the currently loaded data.
* **Workflow:**
    1.  Load your Compound List (Step 1).
    2.  Load your Raw Data CDFs (Step 2).
    3.  **Import Session** to apply the saved boundaries and overrides.

---

## 7. Advanced Visualization

### Detailed Sample View
Right-click any plot in the main grid and select **View Detailed...** to open the inspection window. This view is essential for verifying peak purity and identity.

* **Extracted Ion Chromatogram (EIC):** The specific trace for the target compound, showing the integration window boundaries.
* **Total Ion Chromatogram (TIC):** The global chromatogram for the sample, useful for checking if a peak shifted relative to major markers.
* **Mass Spectrum:** The actual mass spectrum at the peak's retention time. Use this to confirm the spectral fingerprint matches your metabolite.

### Expanded Summary Plots
The left toolbar contains two summary charts: **Label Incorporation** and **Total Abundance**.
* **Action:** **Double-click** either chart to open it in a large, interactive popup window.
* **Feature:** The expanded view reveals the specific sample names on the axes, which are hidden in the compact toolbar view to save space.

---

## 8. Settings & Configuration

These settings control the global behavior of the application. Changing them usually requires re-processing your data.

### Mass Tolerance
**Settings → Mass Tolerance...**
* **Default:** `0.2 Da`
* **Function:** Defines the binning width for extracting ion chromatograms. MANIC uses an asymmetric "offset-and-round" algorithm to correct for mass calibration drift.
* **Impact:** Changing this requires re-importing your raw data (Step 2).
* **Deep Dive:** 📖 [Read the Mass Tolerance Technical Doc](docs/mass_tolerance.md)

### Legacy Integration Mode
**Settings → Legacy Integration Mode**
* **Off (Default):** Uses **Time-Based Integration**. Areas are calculated as $Intensity \times Time$. This is the scientifically accurate method for modern reporting.
* **On:** Uses **Unit-Spacing Integration**. Areas are simple sums of intensity. This produces values ~100× larger and is intended *only* for reproducing historical data from MATLAB GVISO/MANIC v3.3.0.
* **Deep Dive:** 📖 [Compare Integration Methods](docs/integration_methods.md)

### Minimum Peak Area
**Settings → Minimum Peak Area...**
* **Default:** `0.05` (5%)
* **Function:** Sets the validation threshold. Peaks with a total area less than 5% of the Internal Standard's area are flagged with a **red background**.
* **Deep Dive:** 📖 [Understanding Peak Validation](docs/peak_validation.md)

### Natural Abundance Correction
**Settings → Natural Abundance Correction** (Toggle)
* **Function:** Controls the visualization mode of the main chromatogram plots.
    * **On (Checked):** Displays the **Corrected EIC**. This shows the signal *after* the mathematical removal of natural heavy isotopes. Use this to see the "pure" labeling signal.
    * **Off (Unchecked):** Displays the **Raw EIC**. This shows the total signal extracted from the file before any correction.
* **Usage:** Toggle this off and on to visually verify that the correction algorithm is working correctly (e.g., ensuring it hasn't over-corrected a peak into the negative range).
* **Note:** This setting only affects the *display*; it does **not** turn off the background calculation.
* **Deep Dive:** 📖 [Natural Isotope Correction Algorithm](docs/natural_isotope_correction.md)

---

## Appendix: Migration from version 3

For users upgrading from the MATLAB version of MANIC (v3.3.0), please note the following critical changes in data handling.

| Feature | v3.3.0 (Legacy) | v4.0.0 (Python) |
| :--- | :--- | :--- |
| **Integration** | Unit-spacing (large values) | Time-based (physically meaningful). *Legacy mode available.* |
| **NA Correction** | Applied *after* integration | Applied *before* integration (per timepoint) for higher accuracy. |
| **MRRF** | Sum-based calculation | Mean-based calculation (more robust to sample count variations). |
| **Validation** | Manual visual check | Automatic red/white quality indicators. |

* **Correction Math:** 📖 [Natural Isotope Correction Algorithm](docs/natural_isotope_correction.md)


