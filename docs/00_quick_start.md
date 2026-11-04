# Quick Start

MANIC asks you to pick a mode when a session starts. The choice is fixed for that session.

1. In **Choose Analysis Mode**, click **Labelled isotope-tracing analysis** or **Unlabelled targeted analysis**.
2. Choose **File → Load Compounds/Parameter List** and select your spreadsheet.
3. Choose **File → Load Raw Data (CDF)** and select the folder of ANDI/AIA NetCDF files.
4. In **Check your data setup**, confirm the internal standard and which MM files (standard mixture) matched. Click **Apply** or **Continue without changes**. If a pattern is wrong, the dialog names your compound list file and lists the steps to reload it.
5. Select a compound and review its sample plots. Click a plot to select it, or use the keys below. The **Review** menu in the menu bar holds every review command: **Inspect *sample*...**, the selection commands, **Accept Peak (Below Threshold)**, **Mark Peak as Bad** and **Curve Fit**. Right-clicking a plot opens the same commands.
6. Choose **File → Export Data...**. In **Export Options**, pick **Time-based (recommended)** or **Legacy (MATLAB-compatible unit spacing)**. In labelled mode, tick **Include % Carbons Labelled sheet** only if you want that sheet.

## Review from the keyboard

Click a plot first so the grid has keyboard focus.

| Key | Action |
| --- | --- |
| Arrow keys | Move the focus to the next plot |
| Space | Select or deselect the focused plot |
| Return | Inspect the focused plot (same as double-click) |
| Esc | Deselect all plots |
| Ctrl+A (⌘A on macOS) | Select all plots |
| Ctrl+[ and Ctrl+] (⌘[ and ⌘] on macOS) | Previous and next compound |
| Ctrl+F (⌘F on macOS) | Find a compound |

With plots selected, the **Review** commands act on the whole selection and name the count, for example **Mark 3 Peaks as Bad**.

For the labelled workflow, see [User Guide](01_user_guide.md).
For targeted profiling, see [Unlabelled Targeted Analysis](Unlabelled_Targeted_Analysis.md).
