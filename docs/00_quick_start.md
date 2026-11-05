# Quick Start

1. In **Choose Analysis Mode**, click **Labelled** or **Unlabelled**. The mode is fixed for the session.
2. Choose **File → Load Compounds/Parameter List** and select your spreadsheet.
3. Choose **File → Load Raw Data (CDF)** and select the folder of ANDI/AIA NetCDF files.
4. In **Check your data setup**, confirm the internal standard and which MM files (standard mixture) matched. Click **Continue**, or **Apply** if you chose a different internal standard. If a pattern is wrong, the dialog names your compound list file, and **How do I change a pattern?** opens the steps to reload it.
5. Select a compound and review its sample plots. Click a plot to select it, or use the keys below. The **Review** menu in the menu bar holds every review command: **Inspect *sample*...**, the selection commands, **Accept Peak (Below Threshold)**, **Mark Peak as Bad** and **Curve Fit**. Right-clicking a plot opens the same commands.
6. Choose **File → Export Data...**. Pick **Time-based (recommended)** or **Legacy (MATLAB-compatible unit spacing)**. In labelled mode, tick **Include % Carbons Labelled sheet** only if you want that sheet. Click **Choose Location…** and save the workbook.

## Review from the keyboard

Click a plot first so the grid has keyboard focus. A, B and N work anywhere in the window except a text field.

| Key | Action |
| --- | --- |
| Arrow keys | Move the focus to the next plot |
| Space | Select or deselect the focused plot |
| Return | Inspect the focused plot (same as double-click) |
| Esc | Deselect all plots |
| Ctrl+A (⌘A on macOS) | Select all plots |
| A | Accept a Below threshold peak, or clear the acceptance |
| B | Mark the peak as bad, or clear the mark |
| N and Shift+N | Select the next or previous plot that still needs review: it has a badge and is neither Accepted nor Marked bad |

With plots selected, the **Review** commands and the A and B keys act on the whole selection, and the menu names the count, for example **Mark 3 Peaks as Bad**.

Other shortcuts:

| Key | Action |
| --- | --- |
| Ctrl+[ and Ctrl+] (⌘[ and ⌘] on macOS) | Previous and next compound |
| Ctrl+F (⌘F on macOS) | Find a compound |
| Ctrl+Return (⌘Return on macOS) | **Apply** the Peak window, while one of its fields has focus |
| Ctrl+Shift+B (⌘⇧B on macOS) | Turn **Baseline Correction** on or off |
| Ctrl+Shift+Y (⌘⇧Y on macOS) | Turn **View → Shared Y-Scale** on or off |
| Ctrl+Shift+P (⌘⇧P on macOS) | Turn **View → Scale to Selected Peak** on or off |

For the labelled workflow, see [User Guide](01_user_guide.md).
For targeted profiling, see [Unlabelled Targeted Analysis](Unlabelled_Targeted_Analysis.md).
