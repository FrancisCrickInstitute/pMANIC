# User Guide

This guide is the labelled (isotope-tracing) workflow: M+0…M+n channels,
natural-abundance correction, and label-derived exports. For a one-page path, see
[Quick Start](00_quick_start.md). For targeted
profiling without stable-isotope tracing, start an **Unlabelled** session and
use [Unlabelled Targeted Analysis](Unlabelled_Targeted_Analysis.md).


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
| `mmfiles` | Pattern to identify MM files (standard mixture). Supports wildcards like `*MM*` |

> **Tip:** To see a working template, download the `example_compound_list.xls` file from the repository.

**Procedure**
1.  Navigate to **File → Load Compounds/Parameter List**.
2.  Select your prepared compound definition file from the file dialog.

**Verification**
Upon a successful import, the application provides immediate visual feedback:
* The **Compounds** status indicator in the top-left toolbar will turn **green**.
* The compound list widget (located below the status indicators) will populate with the names of all imported compounds.

*If any required columns are missing from your file, the import process will be cancelled and an alert will display the specific missing headers.*

**Add Compound**  
To add one compound without a spreadsheet, choose **File → Add Compound...** or right-click the compound list and choose **Add Compound...**. The form uses the same fields as a compound-list row for this session. After you click OK, the new name is selected in the list. If CDF samples are already loaded, MANIC extracts EICs for that compound by re-reading the original CDF files from the location they were first imported from. If those files have moved, the compound is still saved but has no chromatogram data; restore the files and widen an integration boundary to trigger re-extraction, or add compounds before importing raw data. A name that already exists, including a deleted compound, is rejected. Recover the deleted compound or choose a different name.

---

## Step 2: Import Mass Spectrometry Data

**Objective**   
Import raw experimental data files for processing. The application will extract Extracted Ion Chromatograms (EIC) for every compound defined in Step 1 and apply natural abundance corrections.

**Prerequisites**   
* **Compound Definitions Loaded:** You must complete [Step 1](#step-1-load-compound-definitions) first. The application requires the compound library to know which masses to extract.
* **File Format:** ANDI/AIA NetCDF (`.cdf` in any case). Each file must provide `scan_acquisition_time`, `mass_values`, `intensity_values`, `scan_index`, `point_count`, and `total_intensity`.
* **Conversion:** MANIC does not import vendor mass-spec files. Convert them to CDF in [OpenChrom](https://www.openchrom.net/) first.
* **File Organization:** Put every CDF for the experiment (samples and MM files (standard mixture)) in one folder. MANIC scans that folder for `*.cdf` in any case.

**Configuration Note**   
The import process uses the global **Mass Tolerance** setting (Default: 0.2 Da) to bin detected masses.
* To check or change this: Go to **Settings → Mass Tolerance** before or after loading data.
* If CDFs are already loaded, changing the tolerance regenerates every EIC. You do not re-import the folder.

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

After the import finishes, MANIC opens a **Check your data setup** dialog. The dialog shows whether an internal standard is set. Weak peaks are flagged red only when one is. It also shows whether each compound's `mmfiles` pattern matches any loaded sample. Click **Apply** to keep the internal standard chosen in the dialog. Click **Skip** to leave the current selection unchanged. You can run the same check later from **MANIC ▸ Check Data Setup...**. On macOS that command lives under **Help**.

---

## Step 3: Configure Internal Standard

**Objective**   
Designate the reference compound used for normalization and quantification (MRRF calculation).

**Prerequisites**   
The selected compound must meet specific criteria in your compound definition file (from Step 1):
* **Unlabeled:** `labelatoms` should be `0`.
* **Sample Dose:** `int_std_amount` must be defined and `> 0`. This is the amount added to every experimental sample.
* **Calibration Amount:** `amount_in_std_mix` must be defined and `> 0`. This is the concentration present in the standard mixture (MM) files.
* **Universal Presence:** The compound must be detectable in all samples and standards.

**Procedure**   
1.  Locate the **Compounds** list widget in the left sidebar.
2.  **Right-click** on the name of your internal standard compound.
3.  Choose **Select as Internal Standard**.
4.  To remove a selection, right-click anywhere in the list and choose **Clear Internal Standard**.

**Verification** * **Standard Selected:** The `Int Std` pill turns **green** and shows the compound name.
* **No Standard:** The `Int Std` pill turns **red** and shows `Int Std: none`.

The blue `Compound` pill beneath it always names the compound currently selected in the list.

---

## Step 4: Review Integration

**Objective**   
Visually verify that the integration window captures the correct peak for every sample and adjust parameters where necessary. This ensures quantitative accuracy by excluding noise and adjacent peaks while capturing the full metabolite signal.

**The Main Graph View**   
Upon selecting a compound, MANIC displays a grid of mini-plots, one for each active sample.
* **Black Solid Line:** The expected Retention Time (`tR`).
* **Blue Dashed Lines:** The integration boundaries (`tR - loffset` and `tR + roffset`).
* **Background Color:**
    * **White:** Good peak (area is above threshold).
    * **Red:** Weak peak (area is below 0.5% of the internal standard reference peak, unless you change **Settings → Peak Validation**).
    * **Green:** Currently selected for editing.

Tick **Shared y-scale** in the left toolbar to use one common intensity scale for all sample tiles. Untick it to let each tile autoscale to its own tallest peak.

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
* **Edit All:** Right-click a plot and choose **Deselect All**. The Integration Window will show "Selected Plots: All". Changes will apply globally.
* **Edit Specific Samples:** Click on individual plots to select them (they will turn green). You can also drag a box to select multiple. The Integration Window will show "Selected Plots: X samples". Changes apply *only* to the selection.
* **Show Only Selected Samples:** Right-click a selected plot and choose this command to hide every other sample. The remaining tiles stay selected. If you right-click a plot that is not selected, the command uses that plot alone.
* **Show All Samples:** Right-click and choose this command to show every sample again with no plots selected, the same as when you first load a compound.

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

The extract must cover the current left and right offsets plus the RT window buffer (0.1 min by default). If the typed tR Window sits inside those offsets, MANIC raises it to that minimum, updates the field, and continues.

A progress bar will appear as MANIC re-scans the raw CDF files to extract a wider slice of time around the target peak.

> **Important Note:** This update applies to **all samples** for the currently selected compound to ensure consistent data extraction. It does *not* affect other compounds in your library.

#### 7. Resetting Overrides
If you make a mistake or want to revert to the original library definitions:
1.  Select the target plots.
2.  Click the **Reset** button in the Integration Window.
3.  This removes all session-specific overrides for those samples.

---

## Step 4b: Managing Samples and Compounds

**Objective**   
Remove unwanted samples or compounds from your analysis without deleting the underlying data. This is useful for excluding failed injections, QC samples, or irrelevant metabolites from your final export.

### Deleting Items

You can delete samples or compounds directly from their respective list widgets.

**Procedure**
1.  Locate the **Samples** or **Compounds** list in the left sidebar.
2.  **For samples:** Select one or more items using `Ctrl` (Windows/Linux) or `Cmd` (Mac) + click.  
    **For compounds:** Select a single item (compounds use single-selection).
3.  **Right-click** on your selection.
4.  Select **"Delete Sample"** / **"Delete N Samples"** or **"Delete Compound"** from the context menu.
5.  Confirm the deletion in the dialog that appears.

**Important Notes**
*   You cannot delete *all* samples or *all* compounds. At least one must remain.
*   Deleted items are excluded from plots, calculations, and exports.
*   Deletion is reversible. See below.

### Recovering Deleted Items

Deleted items are not permanently removed. They are "soft deleted" and can be restored at any time during your session.

**Procedure**
1.  **Right-click** anywhere in the **Samples** or **Compounds** list.
2.  Select **"Recover Deleted Samples..."** or **"Recover Deleted Compounds..."**.
    *   *This option is grayed out if no items have been deleted.*
3.  In the recovery dialog, select the items you wish to restore (multi-select is supported).
4.  Click **"Restore Selected"**.

Restored items will immediately reappear in their respective lists and be included in subsequent analyses and exports.

### Deleted Items in Exports

When you export data, the changelog file will include a **"Deleted Items"** section listing any compounds or samples that were excluded. This provides a complete audit trail of what was, and was not, included in your final results.

---

## Step 5: Export Results

**Objective**   
Generate the final analytical report. This process calculates all results, applies MRRF calibration, and produces two files: a comprehensive Excel workbook and a detailed session changelog.

**Prerequisites**   
**Data Validity:** Ensure required metadata (especially `int_std_amount` and `amount_in_std_mix`) is present for calibrated compounds.
* **Note on Standards:** While an Internal Standard is recommended for "nmol" results, you may proceed without one to export raw **Peak Areas**.

**Procedure**   

1.  Navigate to **File → Export Data...**.
2.  In the file dialog, choose a name and location for your output file (e.g., `experiment_results.xlsx`) and click **Save**.
3.  In **Export Options**, choose the integration method for this workbook:
    * **Time-based (recommended):** Peak areas use actual time units (intensity × minutes). This is the default.
    * **Legacy (MATLAB-compatible unit spacing):** Unit-spacing integration (sum of intensities). Use this only if you need to match numerical values from the legacy MATLAB tool (values will be about 100× larger).
    In labelled mode the same dialog has **Include % Carbons Labelled sheet**, off by default. Click **OK** to begin processing.
4. If no internal standard is selected, a **warning dialog** will appear explaining that results will be exported as unnormalized "Peak Area". Click **Yes** to proceed. 

> **Note on Processing:** MANIC will perform a final check to ensure natural isotope corrections have been applied. If not, a progress bar will appear as it calculates these corrections for all labeled compounds to ensure data integrity.

**Output Files**   
The export generates two files in your selected directory:
1.  **Data File (`.xlsx`):** The multi-sheet workbook containing your results.
2.  **Changelog (`changelog_YYYYMMDD_HHMM.md`):** A text file documenting the exact parameters used for this analysis, including software version, date, any deleted items excluded from export, and a table of all session-specific integration overrides. This serves as an audit trail for reproducibility.

**Workbook Structure**   
The Excel file contains five worksheets by default. A sixth sheet is optional.

| Worksheet | Description |
| :--- | :--- |
| **1. Raw Values** | Direct instrument signals (uncorrected peak areas). Useful for quality control and verifying raw signal strength. |
| **2. Corrected Values** | Peak areas after mathematical removal of natural isotope abundance. This is the "clean" signal representing true experimental labeling. (If chromatographic deconvolution is enabled, this correction is applied to the same selected component used for Raw Values. If any ion with real intensity failed to fit, both sheets use the raw in-window scans for every non-empty ion. Empty ions stay at area 0 and do not force that fallback.) |
| **3. Isotope Ratio** | Normalized distributions where all isotopologues for a compound sum to 1.0. Used for comparing labeling patterns independent of concentration. |
| **4. % Label Incorporation** | The percentage of the metabolite pool that has incorporated the experimental label. Includes background correction derived from MM files (standard mixture). |
| **5. Abundances** | Absolute amounts (nmol), Relative ratios, or raw Peak Areas depending on standard selection. |
| **% Carbons Labelled** (optional) | Off by default. Tick **Include % Carbons Labelled sheet** in **Export Options** to add the weighted average enrichment of the total carbon pool. |

**Validation & Errors**   
* **Invalid Peaks:** Cells corresponding to peaks that failed the minimum area validation (red plots) will be highlighted with a **light red background** in the Excel file.
* **Abundance Errors:** If the internal standard is missing required calibration fields (`int_std_amount` or `amount_in_std_mix`), MANIC will prompt you to either **cancel** and fix the compound list, or **continue** in unnormalized **Peak Area** mode for that export.

---

## 6. Session Management

### Clear Session vs New Analysis Session

**File → Clear Session** removes compound data, raw data, and session settings. The window stays in the current analysis mode. Confirm **Clear Session**. When it finishes, **Session Cleared** appears.

**File → New Analysis Session...** opens **Choose Analysis Mode**. Click **Labelled isotope-tracing analysis** or **Unlabelled targeted analysis**. If you pick the mode you are already in, MANIC tells you to use **Clear Session** instead. If you pick the other mode and data is loaded, confirm **New Analysis Session**. MANIC then clears the database and opens a new window.

MANIC can save the state of your analysis, including compound definitions, integration boundaries, and manual overrides, without duplicating the large raw data files.

### Export Session
**File → Export Session...**
* **Function:** Creates a `.json` file containing your analytical method and a human-readable changelog.
* **What is saved:** Compound library, retention times, all integration offsets (global and sample-specific), each compound's processing settings (baseline correction and deconvolution level, fit type, and noise gate), the selected internal standard, and the labelled internal-standard reference peak (M+N).
* **What is NOT saved:** The raw mass spectrometry data (CDF content).
* **Use Case:** Archiving your analysis method or sharing it with a colleague who has the same raw files.

### Import Session
**File → Import Session...**
* **Function:** Applies saved integration parameters and per-compound processing settings to the currently loaded data.
* **Workflow:**
    1.  Load your Compound List (Step 1).
    2.  Load your Raw Data CDFs (Step 2).
    3.  **Import Session** to apply the saved boundaries, overrides, deconvolution/baseline settings, and internal standard.
* **Backward compatibility:** Older session files that predate the deconvolution settings or the internal-standard keys import without error. Compounds keep their current settings for any value the file does not contain. A file with no internal-standard key leaves the current toolbar selection unchanged.

---

## 7. Advanced Visualization

### Plot right-click menu
Right-click a plot for these commands. The strings match the menu.

* **Select All**
* **Deselect All**
* **Select Only This Sample**
* **Show Only Selected Samples**
* **Show All Samples**
* **View Detailed...**
* **Accept peak (below threshold)**
* **Mark peak as bad**
* **Curve fit** (submenu)

**Select Only This Sample**, **View Detailed...**, **Accept peak (below threshold)**, **Mark peak as bad**, and **Curve fit** need a plot under the pointer. **Show Only Selected Samples** needs at least one selected plot.

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

Open **Settings**, **Documentation**, **Check for Updates** and **About** from the **MANIC** menu (on macOS, About and Settings sit in the application menu and the other two under **Help**), or use the book and gear icons at the top right of the plot area.

**Shortcuts.** **Settings...** is Ctrl+, (Preferences on macOS). **Documentation** is F1 (HelpContents).

**Qualifier Ratios** is unlabelled-only. **Natural Abundance** and **Internal Standard** are labelled-only. The natural-abundance preview (**Preview natural-abundance-corrected data in plots**) is off by default.

These settings control the global behavior of the application.

### Mass Tolerance
**Settings → Mass Tolerance**
* **Default:** `0.2 Da`
* **Function:** Defines the binning width for extracting ion chromatograms. MANIC uses an asymmetric "offset-and-round" algorithm to correct for mass calibration drift.
* **Impact:** If CDFs are loaded, the change regenerates every EIC. You do not re-import the folder.
* **Deep Dive:** 📖 [Mass Tolerance](Reference_Mass_Tolerance.md)

### Integration
**Settings → Integration**
* Two radios: **Time-based (recommended)** (default) and **Legacy**.
* The choice changes on-screen peak areas only.
* Export asks again in **Export Options**. Those radios are **Time-based (recommended)** and **Legacy (MATLAB-compatible unit spacing)**.
* **Deep Dive:** 📖 [Compare Integration Methods](Reference_Integration_Methods.md)

### Minimum Peak Area
**Settings → Peak Validation**
* **Default:** `0.005` (0.5%)
* **Function:** Sets the validation threshold. Peaks with a total area less than 0.5% of the Internal Standard's area are flagged with a **red background**.
* **Deep Dive:** 📖 [Understanding Peak Validation](Reference_Peak_Validation.md)

### Baseline Correction
The **Baseline correction** checkbox is in the left toolbar, under the Integration Window.
* **On (Default):** Subtracts a linear baseline from each peak area. A dashed line will appear on plots showing the fitted baseline.
* **Off:** Uses the raw integrated area without baseline subtraction.
* **Scope:** This is a per-compound setting. Toggling it affects all samples for the selected compound.
* **Deep Dive:** 📖 [Baseline Correction Algorithm](Reference_Baseline_Correction.md)

### Y-axis scale
Two ticks sit under **Baseline correction**.
* **Shared y-scale:** one intensity scale for every sample tile.
* **Scale to selected peak:** each tile uses that sample's selected deconvolution component (the peak nearest tR). Other peaks in the extract may clip. This tick is labelled-only.
* The ticks cannot both be on. Both off is the default. Each tile then autoscales to the tallest intensity in its extract.

### Chromatographic Peak Deconvolution
**Settings → Deconvolution**
* **Default:** `Level 4`, `Auto` fit type
* **Function:** Fits chromatographic peak shapes around the expected retention time and selects the component nearest that time whose centre sits inside the dashed loffset/roffset window. This can separate overlapping peaks before area calculation.
* **Scope:** This is a **per-compound** setting. Open **Settings → Deconvolution** with a compound selected; the chosen resolution level and fit type are saved for that compound and used by every sample that does not have its own override. A sample can override the curve fit from the plot right-click menu or from the Per-sample curve fit section on the same settings page. An override is shown on that tile's caption. See [Per-sample curve fit](Reference_Chromatographic_Peak_Deconvolution.md#per-sample-curve-fit).
* **Tiles in view do not limit Save:** The compound setting still applies to every sample of that compound, including samples you are not plotting. A per-sample curve-fit override is the exception.
* **Resolution levels:** `Off` disables the feature. Levels `1` through `7` increase chromatographic resolution; higher levels allow narrower and weaker overlapping components to be considered (and cost more time). The default `Level 4` is tuned for aggressive splitting of resolved overlaps while staying fast; levels `5`-`7` additionally enable shoulder detection (separating components that ride on a flank without their own peak) for the hardest coelutions.
* **Fit type:** Choose how the elution shape is modelled:
    * `Auto` - compares the candidate shapes and picks the best by BIC (recommended default).
    * `Gaussian` - symmetric peaks only.
    * `Bi-Gaussian` - asymmetric peaks with separate left/right widths.
    * `EMG` - exponentially modified Gaussian for tailing peaks.
* **Each fittable ion is fitted on its own.** When the level is not `Off`, MANIC fits each channel independently. Overlaps are split and the in-window component nearest the expected retention time is kept. A well-resolved single peak becomes a one-component model so that ion uses the same measurement as any sibling that needed a split. Set the level to `Off` to always integrate the raw trace.
* **Noise gate:** Controls how aggressively MANIC skips fitting on messy/noise-only peaks. When a window is skipped it simply shows and integrates the plain raw trace instead of drawing a meaningless fitted curve - which also keeps exports fast, since noise-only traces are otherwise the slowest to (pointlessly) fit. This is a per-compound setting with four presets:
    * `Balanced` - skip noise and weak peaks buried in heavy noise (recommended default).
    * `Lenient` - skip only near-pure noise.
    * `Aggressive` - only fit clearly smooth peaks.
    * `Off` - always attempt a fit (the old behaviour).
* **Apply to all compounds:** The page has an **"Apply to all compounds"** checkbox. Tick it to copy the chosen resolution, fit type, and noise gate to *every* compound at once (after a confirmation prompt). This is the quickest way to, for example, turn deconvolution **off everywhere** (select `Off`, tick the box, confirm) or roll one configuration out across your whole method. Note that this overwrites each compound's existing per-compound settings.
* **Affects raw, corrected, and abundance results:** When every non-empty ion of a compound in a sample fitted, the *same* selected component is used for the Raw Values, the natural-abundance Corrected Values, and the Abundances. Turning deconvolution on or off for a compound therefore moves all of its result sheets together (not just the raw areas).
* **One noisy failed ion puts the whole envelope on scans:** If any isotopologue with real intensity cannot be fitted, plots show the raw scan traces and export integrates those same raw in-window scans for every non-empty ion of that pair on both Raw and Corrected. An ion with no positive signal inside the dashed boundaries is empty, not a failed fit. Signal elsewhere in the chromatogram does not change that. A successful fit with no peak centre inside the boundaries is also empty. Empty ions stay at area 0. Weak positive ions use their raw scans if fitting fails.
* **Status indicator:** The bottom status bar (left side) shows the current compound's setting, e.g. `Deconvolution: On · Level 4 · Auto · Gate Balanced (compound_name)`, or `Deconvolution: Off`.
* **Logging:** The per-compound resolution, fit type, and noise gate are recorded in the export changelog so processed results are reproducible.
* **Deep Dive:** 📖 [Chromatographic Peak Deconvolution](Reference_Chromatographic_Peak_Deconvolution.md)

### Natural Abundance Correction
**Settings → Natural Abundance**
* Checkbox: **Preview natural-abundance-corrected data in plots**. Off by default.
* **Function:** Controls what the main chromatogram plots and the Label Incorporation bars show.
    * Ticked: Fits the **raw** traces, then draws natural-abundance correction of that same measurement at the acquisition scan times. If the compound has no correction formula or labelled atoms, the plot keeps the raw fitted view. A sample with a fitted curve keeps that curve in either case. Heights can change after correction. When deconvolution selects a fitted component, the faint raw EIC remains visible for context, including neighbour peaks outside that component. Those neighbours do not enter correction or integration.
    * Unticked: Draws the raw EIC. If deconvolution fitted, the faint raw trace stays under the curve.
* **Usage:** Toggle this to check how correction redistributes the isotopologue signals.
* **Note:** This setting only affects the *display* and the on-screen bars. Export still writes both Raw and Corrected sheets from the raw fit, then correction of that selected component. Time-based export uses a denser evaluation of the fit for a more accurate area.
* **Deep Dive:** 📖 [Natural Isotope Correction Algorithm](Reference_Natural_Isotope_Correction.md)

---

## 9. Special Workflow: Process External Data

**File → Process External Data...**

**Objective**
Re-process results from the legacy MANIC tool (v3.3.0) or a previous MANIC export. The rebuild uses the current natural abundance correction and MRRF algorithms.

**Use Case**
Use this feature when you possess the exported "Raw Values" (integrated peak areas) from an old experiment but **do not** have the original raw CDF files (or do not wish to re-integrate them).

**Prerequisites**
1.  **Old Results File:** An Excel or CSV file containing a sheet/table of uncorrected peak areas (Raw Values).
2.  **Compound List:** A valid compound definition file (see Step 1) that matches the metabolites in your old results. This is required to provide the molecular formulas and atom counts needed for the new correction math.

**Procedure**
1.  Choose **File → Process External Data...**.
2.  In **Process External Data**, set **Compounds File:** with **Browse…**.
3.  Set **Raw Values Workbook:** with **Browse…**.
4.  Optionally choose a value for **Internal Standard (optional):**.
5.  Click **OK**.
6.  In **Save Rebuilt Export**, choose the output workbook and save.

**How It Works**
MANIC reads the raw areas from the workbook, pairs them with the compound list, and writes five sheets: **Raw Values**, **Corrected Values**, **Isotope Ratio**, **% Label Incorporation**, and **Abundances**.

> **⚠️ Scientific Limitation: Approximate Mode**
> Because the original raw data (CDF) is missing, MANIC cannot perform the standard "per-timepoint" correction. Instead, it applies a mathematical approximation to the **total integrated area**.
> * **Result:** The "Corrected Values" may differ slightly from a full re-analysis of raw CDFs.
> * **Restriction:** You cannot adjust integration boundaries or view chromatograms in this mode.

**Full Explanation:** 📖 [Process External Data](Workflow_Process_External_Data.md)

---

## Appendix: Migration from version 3

For users upgrading from the MATLAB version of MANIC (v3.3.0), please note the following critical changes in data handling.

| Feature | v3.3.0 (Legacy) | v4.0.0 (Python) |
| :--- | :--- | :--- |
| **Integration** | Unit-spacing (large values) | Time-based (physically meaningful). *Legacy mode available.* |
| **NA Correction** | Applied *after* integration | Applied *before* integration (per timepoint) for higher accuracy. |
| **MRRF** | Sum-based calculation | Mean-based calculation (more robust to sample count variations). |
| **Validation** | Manual visual check | Automatic red/white quality indicators. |

* **Correction Math:** 📖 [Natural Isotope Correction Algorithm](Reference_Natural_Isotope_Correction.md)

## Glossary

**Internal standard.** The compound chosen with **Select as Internal Standard**. The **Int Std** pill turns green and shows that name. With no selection the pill is red and shows **Int Std: none**.

**MM files (standard mixture).** Sample files that match the compound-list `mmfiles` pattern. MANIC uses them for MRRF and background correction.

**Corrected (natural-abundance).** Peak areas after removal of naturally occurring heavy isotopes. This is not the same as **Baseline-corrected**, which subtracts a linear baseline from the chromatogram before area is taken.

**nmol, Relative, Peak Area.** Units on the **Abundances** sheet. nmol when an internal standard and `amount_in_std_mix` are set. Relative when an internal standard is set but `amount_in_std_mix` is missing or 0. Peak Area when no internal standard is selected.

**Red tile.** The peak total area is below the peak-validation threshold (default 0.5% of the internal standard reference peak).
