# UI branch code-quality audit

Reviewed `origin/main...6ec219c` in `/Users/couttsj/Documents/_code/pythonMANIC`. HEAD was `6ec219c9b62e66819e3cae8ba1758fca0e5cd33e`. The diff contains 111 files, 12,725 added lines, and 3,485 removed lines. This is a one-user PySide6 desktop application.

The cleanup has 16 dead-code findings, 5 duplication groups, 9 needless-layer findings, and 10 comment groups. The test inventory covers all 56 touched test files, including 47 new files and 41 files named after review rounds. There are 204 individual verdicts: 120 keep, 65 merge into retained cases, and 19 delete. Estimated net reduction is about 1,700 lines, with a planning range of 1,400 to 2,000.

The 204 verdicts cover 200 added or edited test bodies and four bodies affected by changed shared fixtures or expected values. The other 69 test bodies in the touched files are outside this deletion recommendation. Four old test names were replaced by renamed versions; three obsolete pill tests were already deleted. Counts are function definitions, not expanded parameter cases.

This report changes no repository code. The untracked bench/HILLCLIMB.md was present before the review and is untouched. No processor, model, validation, sheet generator, IO, calculation, exported value, user capability, or visual style is proposed for removal or alteration.

## Dead code

Rows are in file order. The grep evidence is against the requested commit, across tracked code, tests, scripts, documentation, and configuration. A lone declaration is evidence of no caller; Qt virtual overrides and signal callbacks were checked separately. Pre-existing leftovers are identified rather than attributed to new branch code.

| ID | Evidence | Finding | Caller check | Cleanup |
| --- | --- | --- | --- | --- |
| D01 | [src/manic/resources/style.qss:55](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/resources/style.qss:55) | Unused `QWidget[role="card"]` rule. No widget assigns this role. | `git grep -n -F 'role="card"' 6ec219c -- .`<br>`src/manic/resources/style.qss:55:QWidget[role="card"] {`<br>`git grep -n -E 'setProperty.*card&#124;set_style_property.*card' 6ec219c -- src scripts tests` returns no matches. | Delete the five-line block. PlotTile paints its own card. |
| D02 | [src/manic/resources/style.qss:819](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/resources/style.qss:819)<br>[src/manic/ui/sidebar_widgets.py:137](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/sidebar_widgets.py:137) | Unused `todo` status presentation, including its stylesheet block and accent-ring branch. | `git grep -n -w todo 6ec219c -- src scripts tests` returns only sidebar_widgets.py:137 painter branch and style.qss:819 selector. The docstring also mentions Todo with a capital T. `git grep -n -F 'set_state(' 6ec219c -- src` shows only done, optional, blocked, or forwarding of those states. | Delete the selector and the unreachable todo choice. Keep done, optional, and blocked rendering. |
| D03 | [src/manic/ui/channel_chips.py:177](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/channel_chips.py:177) | Write-only `ChannelChipRow.trailing` field. The live constructor argument is consumed directly by the layout. | `git grep -n -F '.trailing' 6ec219c -- .`<br>`src/manic/ui/channel_chips.py:177:        self.trailing = trailing` | Delete only the assignment. Keep trailing-widget support. |
| D04 | [src/manic/ui/colors.py:82](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/colors.py:82)<br>[src/manic/ui/colors.py:13](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/colors.py:13) | Uncalled `peak_verdict_qcolor`. It existed before this branch and was left behind by the badge change. | `git grep -n -w 'peak_verdict_qcolor' 6ec219c -- .`<br>`src/manic/ui/colors.py:82:def peak_verdict_qcolor(verdict: PeakVerdict) -> QColor &#124; None:`<br>`PEAK_VERDICT_FILL` and `PeakVerdict` occur in colors.py only in its import, annotation, and this body. | Delete the five-line function and its now-unused import of those two names. Leave validation definitions unchanged. |
| D05 | [src/manic/ui/graphs.py:1218](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1218) | Uncalled `deselect_all_plots` alias, inherited from main. Live actions call clear_selection. | `git grep -n -w 'deselect_all_plots' 6ec219c -- .`<br>`src/manic/ui/graphs.py:1218:    def deselect_all_plots(self):` | Delete the three-line alias. |
| D06 | [src/manic/ui/left_toolbar.py:623](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/left_toolbar.py:623) | New, uncalled `Toolbar.is_compact` accessor. Internal code uses _compact and _set_compact. | `git grep -n -w 'is_compact' 6ec219c -- .`<br>`src/manic/ui/left_toolbar.py:623:    def is_compact(self) -> bool:` | Delete the two-line accessor. Keep responsive compact-mode behaviour. |
| D07 | [src/manic/ui/main_window.py:18](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/main_window.py:18)<br>[src/manic/ui/main_window.py:27](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/main_window.py:27) | Unused `QDialogButtonBox` and `QRadioButton` imports after extracting ExportOptionsDialog. | `git grep -n -w 'QDialogButtonBox' 6ec219c -- src/manic/ui/main_window.py`<br>`src/manic/ui/main_window.py:18:    QDialogButtonBox,`<br>`git grep -n -w 'QRadioButton' 6ec219c -- src/manic/ui/main_window.py`<br>`src/manic/ui/main_window.py:27:    QRadioButton,` | Delete the two import entries. The export options dialog retains its own live imports. |
| D08 | [src/manic/ui/matplotlib_plot_widget.py:129](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/matplotlib_plot_widget.py:129)<br>[src/manic/ui/matplotlib_plot_widget.py:11](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/matplotlib_plot_widget.py:11) | Uncalled `matplotlib_cleanup` context manager, inherited from main. | `git grep -n -w 'matplotlib_cleanup' 6ec219c -- .`<br>`src/manic/ui/matplotlib_plot_widget.py:130:def matplotlib_cleanup():`<br>`git grep -n -w contextmanager 6ec219c -- src/manic/ui/matplotlib_plot_widget.py` gives only lines 11 and 129. | Delete the decorator, function, and contextmanager import. Keep MatplotlibPlotWidget.cleanup and its pyplot import. |
| D09 | [src/manic/ui/matplotlib_plot_widget.py:550](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/matplotlib_plot_widget.py:550) | Uncalled `MatplotlibPlotWidget.add_text` annotation API, inherited from main. | `git grep -n -w 'add_text' 6ec219c -- .`<br>`src/manic/ui/matplotlib_plot_widget.py:550:    def add_text(` | Delete the 43-line method. Live peak labels, legends, and error text use other drawing paths. |
| D10 | [src/manic/ui/sidebar_widgets.py:204](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/sidebar_widgets.py:204) | New, uncalled `StatusRow.set_compact` mode. Toolbar._set_compact is a separate, live method. | `git grep -n -w 'set_compact' 6ec219c -- .`<br>`src/manic/ui/sidebar_widgets.py:204:    def set_compact(self, compact: bool) -> None:` | Delete these seven lines. Keep toolbar section switching. |
| D11 | [src/manic/ui/sidebar_widgets.py:274](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/sidebar_widgets.py:274) | New, uninstantiated `NoMatchHint` class. The working no-match state hides the list and updates its count. | `git grep -n -w 'NoMatchHint' 6ec219c -- .`<br>`src/manic/ui/sidebar_widgets.py:274:class NoMatchHint(QWidget):` | Delete the 16-line class. Keep FilterField and the current count/Escape recovery behaviour. |
| D12 | [src/manic/ui/sidebar_widgets.py:52](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/sidebar_widgets.py:52) | Unused lower bound in SUMMARY_CHART_HEIGHT = (200, 330). Only the upper limit is read. | `git grep -n -w 'SUMMARY_CHART_HEIGHT' 6ec219c -- .`<br>`src/manic/ui/isotopologue_ratio_widget.py:38:    SUMMARY_CHART_HEIGHT,`<br>`src/manic/ui/isotopologue_ratio_widget.py:125:        self.setMaximumHeight(SUMMARY_CHART_HEIGHT[1])`<br>`src/manic/ui/sidebar_widgets.py:52:SUMMARY_CHART_HEIGHT = (200, 330)`<br>`src/manic/ui/total_abundance_widget.py:26:    SUMMARY_CHART_HEIGHT,`<br>`src/manic/ui/total_abundance_widget.py:95:        self.setMaximumHeight(SUMMARY_CHART_HEIGHT[1])`<br>`tests/test_r6_sidebar_summary.py:9:from manic.ui.sidebar_widgets import NAME_ROW_PX, SUMMARY_CHART_HEIGHT`<br>`tests/test_r6_sidebar_summary.py:45:    widget.resize(264, SUMMARY_CHART_HEIGHT[1])`<br>`tests/test_r6_sidebar_summary.py:60:        assert widget.height() <= SUMMARY_CHART_HEIGHT[1]`<br>Every indexed consumer reads element 1. No caller reads 200 or unpacks the tuple. | Replace the tuple with one named maximum-height value of 330 and update its consumers. Keep the existing minimum/size-hint logic unchanged. |
| D13 | [src/manic/ui/theme.py:74](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/theme.py:74) | New, unused `RADIUS_SMALL` token. | `git grep -n -w 'RADIUS_SMALL' 6ec219c -- .`<br>`src/manic/ui/theme.py:74:RADIUS_SMALL = 6` | Delete this constant. Do not change any rendered radius. |
| D14 | [src/manic/ui/toast_notification.py:38](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/toast_notification.py:38) | Uncalled `ToastNotification.set_message`, inherited from main. Toasts receive their message at construction. | `git grep -n -w 'set_message' 6ec219c -- .`<br>`src/manic/ui/toast_notification.py:38:    def set_message(self, message: str) -> None:` | Delete the two-line setter. Keep dismissal and timeouts. |
| D15 | [src/manic/ui/total_abundance_widget.py:101](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/total_abundance_widget.py:101)<br>[src/manic/ui/total_abundance_widget.py:118](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/total_abundance_widget.py:118)<br>[src/manic/ui/total_abundance_widget.py:270](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/total_abundance_widget.py:270)<br>[src/manic/ui/total_abundance_widget.py:298](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/total_abundance_widget.py:298) | Write-only TotalAbundanceWidget fields `_current_eics`, `_scale_exp`, and `_scale_factor`. | `git grep -n -F 'self._current_eics' 6ec219c -- src/manic/ui/total_abundance_widget.py`<br>`src/manic/ui/total_abundance_widget.py:101:        self._current_eics: Optional[List[EIC]] = None`<br>`src/manic/ui/total_abundance_widget.py:118:        self._current_eics = eics`<br>`src/manic/ui/total_abundance_widget.py:298:        self._current_eics = None`<br>`git grep -n -F 'self._scale_exp' 6ec219c -- src/manic/ui/total_abundance_widget.py`<br>`src/manic/ui/total_abundance_widget.py:270:        self._scale_exp = scale_exp`<br>`git grep -n -F 'self._scale_factor' 6ec219c -- src/manic/ui/total_abundance_widget.py`<br>`src/manic/ui/total_abundance_widget.py:271:        self._scale_factor = scale_factor`<br>Whole-tree searches find no external reads of these widget fields. IsotopologueRatioWidget has a different, live _current_eics field. | Delete the five assignments. Keep all local values and calculations exactly as they are. |
| D16 | [tests/test_ui_formatting.py:17](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_ui_formatting.py:17)<br>[tests/test_ui_formatting.py:34](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_ui_formatting.py:34) | Unused test-module imports `QColor` and `QUALIFIER_STATUS_COLORS`. | `git grep -n -w 'QColor' 6ec219c -- tests/test_ui_formatting.py`<br>`tests/test_ui_formatting.py:17:from PySide6.QtGui import QColor`<br>`git grep -n -w 'QUALIFIER_STATUS_COLORS' 6ec219c -- tests/test_ui_formatting.py`<br>`tests/test_ui_formatting.py:34:    QUALIFIER_STATUS_COLORS,` | Delete these two import bindings. Neither name is loaded by the module or imported from it elsewhere. |

No unused signal was confirmed. The introduced signals have real emitters and receivers, including forwarding connections. Do not delete Qt event/layout overrides because a text search finds no direct Python call. Test-only getters are separated in N09 because they do have callers.

## Duplicated logic

| ID | Evidence | Duplication | Single home | Cleanup |
| --- | --- | --- | --- | --- |
| U01 | [src/manic/resources/style.qss:907](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/resources/style.qss:907)<br>[src/manic/ui/dialog_kit.py:54](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/dialog_kit.py:54)<br>[src/manic/ui/dialog_kit.py:245](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/dialog_kit.py:245) | The app sheet and sidebar_list both own sidebar backgrounds, borders, padding, and selected-item rules. | `src/manic/ui/dialog_kit.py::_SIDEBAR_STYLE` and sidebar_list. | Delete the three app-wide sidebar-list blocks after retaining the current effective item metrics in the existing local owner. An in-memory removal of these exact blocks was pixel-identical for a selected Settings list at 200x300, with the same three 183x32 item rectangles. Repeat the actual screen check during cleanup for both schemes and both dialogs. |
| U02 | [src/manic/ui/dialog_kit.py:172](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/dialog_kit.py:172)<br>[src/manic/ui/dialog_kit.py:180](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/dialog_kit.py:180)<br>[src/manic/ui/theme.py:185](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/theme.py:185) | set_invalid and set_variant repeat the dynamic-property, unpolish, and polish sequence already owned by set_style_property. | `src/manic/ui/theme.py::set_style_property` | Replace the calls with the existing helper and delete the duplicate wrappers. Preserve None-versus-False treatment on initial invalid properties. Do not add another styling utility. |
| U03 | [src/manic/ui/graphs.py:1474](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1474)<br>[src/manic/ui/graphs.py:1611](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1611) | New-chart and reused-chart paths repeat series creation, ranges, tR guides, and baseline drawing. Each path must stay in sync when UI drawing changes. | `src/manic/ui/graphs.py::GraphView._update_chart_data` | Let _build_plot create the chart/view/axes and hand drawing to the same population path used on reuse. Preserve every prepared-data input, factor, range, processor call, and series order. No science or scaling formula changes. |
| U04 | [src/manic/ui/plot_tile.py:120](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/plot_tile.py:120)<br>[src/manic/ui/sidebar_widgets.py:146](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/sidebar_widgets.py:146)<br>[src/manic/ui/start_panel.py:195](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/start_panel.py:195) | ElidingLabel and ElidedLabel duplicate full-text storage, setText, resizeEvent, and font-metric elision. _FolderLabel adds another copy of the calculation for middle elision. | `src/manic/ui/sidebar_widgets.py::ElidedLabel` | Reuse the existing label implementation, preserving right versus middle elision and each caller's tooltip policy. Keep the QLineEdit tooltip handler and painted ChannelChip separate; their control geometry and event handling differ. |
| U05 | [tests/test_peak_review_menu.py:13](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:13)<br>[tests/test_r3_charts_grid.py:82](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_grid.py:82)<br>[tests/test_r3_sidebar_review.py:10](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_review.py:10)<br>[tests/test_r5_charts_review.py:10](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_review.py:10)<br>[tests/test_r6_grid_review.py:10](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_grid_review.py:10)<br>[tests/test_r5_sidebar_layout.py:9](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_layout.py:9)<br>[tests/test_r6_sidebar_inspector.py:13](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_inspector.py:13)<br>[tests/test_r7_shell_sidebar.py:11](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_shell_sidebar.py:11)<br>[tests/test_r3_charts_detail.py:53](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_detail.py:53)<br>[tests/test_r5_charts_spectrum.py:6](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_spectrum.py:6)<br>[tests/test_r6_popups_detail.py:32](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_detail.py:32) | Five fake-chart classes, five isolated-QSettings fixtures, three nearly identical sidebar settling helpers, and three copies of the same spectrum fixture. | `tests/conftest.py` for function-scoped fixtures. Use existing real ClickableChartView instances where the behaviour needs Qt events. | Consolidate fixtures while moving tests. Restore QSettings defaults after each fixture instead of leaving global format/path changes behind. Remove the cross-test-module import at tests/test_r3_integrate_review_menus.py:5. Share data/setup, not expected results. |

These are repeated responsibilities, not a request for a generic chart/widget framework. Keep FlowLayout, RecoveryDialog, ThemedToolButton, CompactNavigationToolbar, and the distinct chart painters. They implement real layout, recovery, live recolouring, navigation, or differing drawing behaviour.

## Needless layers and one-value options

| ID | Evidence | Finding | Reference evidence | Cleanup |
| --- | --- | --- | --- | --- |
| N01 | [src/manic/ui/chart_header.py:15](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/chart_header.py:15)<br>[src/manic/ui/icon_button.py:11](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/icon_button.py:11)<br>[src/manic/ui/sidebar_widgets.py:114](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/sidebar_widgets.py:114) | Three icon helpers expose configuration with one observed value. | `expand_icon` is passed as a zero-argument factory at chart_header.py:47. `svg_icon` is called only by icon_button.py:36 with defaults text_secondary/20. Both `status_pixmap` callers at sidebar_widgets.py:202,214 omit size, using 14. | Make those fixed values local constants or locals. Keep each icon and its exact pixels. This does not justify merging the distinct check/ring/exclamation painters. |
| N02 | [src/manic/ui/chart_popup_dialog.py:100](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/chart_popup_dialog.py:100) | identity_key_html supports an identity=None mode that no caller uses, which adds optional counts and four conditional formatting paths. | `git grep -n -F 'identity_key_html(' 6ec219c -- src scripts tests` gives the definition, popup call at :585, and TargetedQcWidget call at :151. Both pass a real assessment. | Require the assessment and remove only the no-assessment branches. Keep the validated/failed/grey cell counts. |
| N03 | [src/manic/ui/chart_popup_dialog.py:712](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/chart_popup_dialog.py:712)<br>[src/manic/ui/chart_popup_dialog.py:717](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/chart_popup_dialog.py:717)<br>[src/manic/ui/chart_popup_dialog.py:770](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/chart_popup_dialog.py:770)<br>[src/manic/ui/chart_popup_dialog.py:781](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/chart_popup_dialog.py:781)<br>[src/manic/ui/chart_popup_dialog.py:798](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/chart_popup_dialog.py:798) | Signal-receiver introspection invents a second inert-popup mode and makes keyboard, mouse, hint, and focus handling branch on listener count. | Every application popup owner connects sample_activated before exec at isotopologue_ratio_widget.py:524, total_abundance_widget.py:333, and targeted_qc_widget.py:273. MainWindow connects all three owners at main_window.py:442. The only explicit inert-mode consumer is test_r5_charts_popups.py:83. | Keep one interactive popup mode and its existing empty-row guards. Delete receiver-count introspection, QMetaMethod, and the inert-mode test. All app row-activation capabilities remain. |
| N04 | [src/manic/ui/dialog_kit.py:150](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/dialog_kit.py:150)<br>[src/manic/ui/dialog_kit.py:160](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/dialog_kit.py:160)<br>[src/manic/ui/dialog_kit.py:166](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/dialog_kit.py:166)<br>[src/manic/ui/update_old_data_dialog.py:84](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/update_old_data_dialog.py:84) | form_layout carries a variable label width through a dynamic Qt property, even though every form uses 150. | `git grep -n -F 'form_layout(' 6ec219c -- src scripts tests` gives defaults in Add Compound/Settings and one explicit form_layout(150) in UpdateOldDataDialog. FORM_LABEL_WIDTH is 150. | Use FORM_LABEL_WIDTH directly in form_row. Remove the unused parameter, dynamic labelWidth property, integer coercion, and fallback. Preserve all widths. |
| N05 | [src/manic/ui/graphs.py:617](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:617)<br>[src/manic/ui/graphs.py:1600](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1600) | _build_plot_with_caption adds one indirection and ten lines to a single call of _get_container_from_pool. | `git grep -n -w _build_plot_with_caption 6ec219c -- .` gives call :617, a historical docstring mention :1354, and definition :1600. The method body only forwards all arguments. | Call _get_container_from_pool at :617 and delete the wrapper and historical reference. |
| N06 | [src/manic/ui/graphs.py:1372](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1372)<br>[src/manic/ui/graphs.py:1426](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1426)<br>[src/manic/ui/graphs.py:1451](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1451)<br>[src/manic/ui/graphs.py:1456](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1456)<br>[src/manic/ui/graphs.py:1470](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1470)<br>[src/manic/ui/graphs.py:1585](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1585) | Reusing a tile repeatedly disconnects and reconnects the same three bound slots, removes/reinstalls the same filters, and tracks _signal_connected. The outer try/finally only executes pass. | The connections at :1372 and :1452 target the same GraphView methods. They do not capture a particular sample; the current chart metadata supplies it. Filters are installed on the same retained container/view/viewport/caption. | Connect and install filters once when the tile is created. Keep them until tile destruction. Remove the warning-suppression/disconnect machinery, tracking flag, and empty finally. Verify one click/open emission after repeated pool reuse. Keep pooling and full destruction. |
| N07 | [src/manic/ui/isotopologue_ratio_widget.py:171](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/isotopologue_ratio_widget.py:171)<br>[src/manic/ui/isotopologue_ratio_widget.py:225](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/isotopologue_ratio_widget.py:225)<br>[src/manic/ui/total_abundance_widget.py:122](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/total_abundance_widget.py:122)<br>[src/manic/ui/total_abundance_widget.py:139](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/total_abundance_widget.py:139) | Two _order_like_graph_window helpers return their arguments unchanged after computing and discarding grid dimensions. | `git grep -n -w _order_like_graph_window 6ec219c -- .` gives only the two definitions and one caller in each widget. The bodies at isotopologue_ratio_widget.py:225-256 and total_abundance_widget.py:139-158 end with the original pair. | Delete both identity helpers and their calls. Keep the existing reversed copies and NumPy flips at the callers exactly as they are, so sample/value ordering stays unchanged. |
| N08 | [src/manic/ui/left_toolbar.py:781](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/left_toolbar.py:781)<br>[src/manic/ui/left_toolbar.py:848](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/left_toolbar.py:848) | fill_integration_window is a nine-line compatibility no-op still called on every compound selection. | `git grep -n -w fill_integration_window 6ec219c -- .` returns only call :781 and definition :848. The body is pass. Its own docstring says no longer used. | Delete the call and method. MainWindow.on_plot_button already populates the integration fields through the live path. Keep all session overrides. |
| N09 | [src/manic/ui/chart_popup_dialog.py:500](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/chart_popup_dialog.py:500)<br>[src/manic/ui/isotopologue_ratio_widget.py:329](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/isotopologue_ratio_widget.py:329)<br>[src/manic/ui/isotopologue_ratio_widget.py:370](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/isotopologue_ratio_widget.py:370)<br>[src/manic/ui/matplotlib_plot_widget.py:788](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/matplotlib_plot_widget.py:788)<br>[src/manic/ui/plot_tile.py:129](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/plot_tile.py:129)<br>[src/manic/ui/sidebar_widgets.py:218](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/sidebar_widgets.py:218)<br>[src/manic/ui/targeted_qc_widget.py:199](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/targeted_qc_widget.py:199)<br>[src/manic/ui/total_abundance_widget.py:220](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/total_abundance_widget.py:220) | A set of application getters exists only to restate Qt state for tests. dash_rows can even report underlying data instead of whether its dash is visibly drawn. | For value_label_texts, dash_rows, highlighted_bars, visible_peak_labels, fullText, value_text, and highlighted_rows, whole-tree grep finds declarations plus tests, with no application call sites. These are test-used, not dead code. row_names and tick_positions are live and excluded. | As the tests move, read visible labels, selected bars, actual artists, and item rectangles in shared test helpers; then delete the test-only forwarding methods. Keep legitimate production consumers such as full_text, row_names, tick_positions, badges/tint if later needed, and text_size. |

Keep the existing pooling-versus-destruction flag. Both paths are used. Keep legacy/time-based integration choices, corrected preview, labelled/unlabelled modes, and per-sample overrides. They change real user behaviour and are not speculative compatibility shims.

## Tests

Apply the rule "call the code as its users do and assert the exact result they see." A literal action payload, selected sample list, displayed error, cell mark, or visible geometry invariant is useful. A constructor constant, a production string used as its own oracle, or a private formatter result is not sufficient.

Keep means keep the behavioural contract. The row names any small entry-point/assertion correction needed when consolidating. In particular, click Add/Apply and menu actions rather than calling private slots or emitting the signal being tested. Merge means move only the distinct case into the named retained scenario and remove the redundant function/setup. It does not mean adding another test beside it. Delete applies to the test, never the capability.

### File inventory

| File | Branch change | Coverage in this audit | Verdicts |
| --- | --- | --- | --- |
| [tests/test_add_compound.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_add_compound.py:1) | modified | 5 reviewed of 20 | 2 keep, 3 merge, 0 delete; 15 unchanged bodies outside this cleanup |
| [tests/test_app_stylesheet.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_app_stylesheet.py:1) | modified | 2 reviewed of 2 | 2 keep, 0 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_deconvolution_indicator.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_deconvolution_indicator.py:1) | added | 1 reviewed of 1 | 0 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_documentation_viewer.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_documentation_viewer.py:1) | modified | 1 reviewed of 3 | 1 keep, 0 merge, 0 delete; 2 unchanged bodies outside this cleanup |
| [tests/test_focus_selected_samples.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_focus_selected_samples.py:1) | modified | 1 reviewed of 2 | 1 keep, 0 merge, 0 delete; 1 unchanged bodies outside this cleanup |
| [tests/test_main_window_shell.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_main_window_shell.py:1) | added | 4 reviewed of 4 | 3 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_peak_review_menu.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:1) | modified | 12 reviewed of 12 | 7 keep, 5 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_plot_grid_ui.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_plot_grid_ui.py:1) | added | 8 reviewed of 8 | 6 keep, 2 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_post_load_checklist.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_post_load_checklist.py:1) | modified | 4 reviewed of 10 | 4 keep, 0 merge, 0 delete; 6 unchanged bodies outside this cleanup |
| [tests/test_r3_charts_detail.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_detail.py:1) | added | 4 reviewed of 4 | 1 keep, 2 merge, 1 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r3_charts_grid.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_grid.py:1) | added | 6 reviewed of 6 | 3 keep, 3 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r3_charts_popups.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_popups.py:1) | added | 4 reviewed of 4 | 0 keep, 3 merge, 1 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r3_dialogs_add_compound.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_add_compound.py:1) | added | 7 reviewed of 7 | 7 keep, 0 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r3_dialogs_settings.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_settings.py:1) | added | 5 reviewed of 5 | 0 keep, 1 merge, 4 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r3_integrate_review_menus.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_integrate_review_menus.py:1) | added | 1 reviewed of 1 | 0 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r3_sidebar_charts.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_charts.py:1) | added | 1 reviewed of 1 | 1 keep, 0 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r3_sidebar_review.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_review.py:1) | added | 2 reviewed of 2 | 2 keep, 0 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r3_sidebar_state.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_state.py:1) | added | 7 reviewed of 7 | 6 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r5_charts_detail.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_detail.py:1) | added | 3 reviewed of 3 | 2 keep, 0 merge, 1 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r5_charts_identity.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_identity.py:1) | added | 6 reviewed of 6 | 5 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r5_charts_popups.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_popups.py:1) | added | 4 reviewed of 4 | 2 keep, 1 merge, 1 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r5_charts_review.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_review.py:1) | added | 3 reviewed of 3 | 0 keep, 3 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r5_charts_spectrum.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_spectrum.py:1) | added | 2 reviewed of 2 | 2 keep, 0 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r5_shell_checklist.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_shell_checklist.py:1) | added | 2 reviewed of 2 | 1 keep, 0 merge, 1 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r5_shell_contrast.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_shell_contrast.py:1) | added | 4 reviewed of 4 | 1 keep, 3 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r5_sidebar_empty.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_empty.py:1) | added | 1 reviewed of 1 | 1 keep, 0 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r5_sidebar_layout.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_layout.py:1) | added | 6 reviewed of 6 | 4 keep, 2 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r5_sidebar_menus.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_menus.py:1) | added | 3 reviewed of 3 | 1 keep, 1 merge, 1 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r5_sidebar_summary.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_summary.py:1) | added | 2 reviewed of 2 | 1 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r6_grid_review.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_grid_review.py:1) | added | 2 reviewed of 2 | 2 keep, 0 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r6_grid_tiles.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_grid_tiles.py:1) | added | 7 reviewed of 7 | 2 keep, 4 merge, 1 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r6_popups_detail.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_detail.py:1) | added | 3 reviewed of 3 | 1 keep, 1 merge, 1 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r6_popups_identity.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_identity.py:1) | added | 6 reviewed of 6 | 5 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r6_popups_keyboard_axis.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_keyboard_axis.py:1) | added | 6 reviewed of 6 | 4 keep, 1 merge, 1 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r6_sidebar_checklist.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_checklist.py:1) | added | 4 reviewed of 4 | 2 keep, 2 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r6_sidebar_inspector.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_inspector.py:1) | added | 5 reviewed of 5 | 4 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r6_sidebar_summary.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_summary.py:1) | added | 3 reviewed of 3 | 2 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r6_sidebar_window_scope.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_window_scope.py:1) | added | 1 reviewed of 1 | 1 keep, 0 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r7_charts_badges.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_badges.py:1) | added | 1 reviewed of 1 | 0 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r7_charts_density.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_density.py:1) | added | 2 reviewed of 2 | 0 keep, 2 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r7_charts_detail.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_detail.py:1) | added | 3 reviewed of 3 | 0 keep, 0 merge, 3 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r7_charts_documentation.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_documentation.py:1) | added | 3 reviewed of 3 | 2 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r7_charts_identity.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_identity.py:1) | added | 7 reviewed of 7 | 1 keep, 5 merge, 1 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r7_charts_summary.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_summary.py:1) | added | 4 reviewed of 4 | 4 keep, 0 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r7_charts_tooltips.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_tooltips.py:1) | added | 3 reviewed of 3 | 2 keep, 0 merge, 1 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r7_dialogs_copy.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_dialogs_copy.py:1) | added | 5 reviewed of 5 | 4 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r7_dialogs_settings.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_dialogs_settings.py:1) | added | 4 reviewed of 4 | 2 keep, 2 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r7_shell_menus.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_shell_menus.py:1) | added | 2 reviewed of 2 | 0 keep, 1 merge, 1 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r7_shell_sidebar.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_shell_sidebar.py:1) | added | 2 reviewed of 2 | 1 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_r7_shell_start.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_shell_start.py:1) | added | 2 reviewed of 2 | 2 keep, 0 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_recovery_dialog.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_recovery_dialog.py:1) | added | 2 reviewed of 2 | 2 keep, 0 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_sample_list_context_menu.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_sample_list_context_menu.py:1) | added | 1 reviewed of 1 | 0 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| [tests/test_settings_window.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_settings_window.py:1) | modified | 7 reviewed of 17 | 6 keep, 1 merge, 0 delete; 10 unchanged bodies outside this cleanup |
| [tests/test_sidebar.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_sidebar.py:1) | added | 5 reviewed of 5 | 4 keep, 1 merge, 0 delete; 0 unchanged bodies outside this cleanup |
| `tests/test_toolbar_pills.py` | deleted | 3 obsolete pill tests already removed | Keep deleted. |
| [tests/test_ui_formatting.py:1](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_ui_formatting.py:1) | modified | 3 reviewed of 38 | 1 keep, 2 merge, 0 delete; 35 unchanged bodies outside this cleanup |

### Individual verdicts

Each source link points to the function at the reviewed commit. Proposed destination paths are names for the cleanup, not claims that those files already exist.

#### tests/test_add_compound.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T001 | [tests/test_add_compound.py:266](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_add_compound.py:266)<br>`test_invalid_ok_keeps_dialog_open_and_flags_the_field` | merge | `tests/test_add_compound.py` | Fold open-dialog, focus, and error-clearing checks into `test_empty_labelled_submit_flags_every_required_field` and `test_editing_one_field_clears_only_its_own_error`. |
| T002 | [tests/test_add_compound.py:281](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_add_compound.py:281)<br>`test_required_spin_boxes_ask_for_a_blank_value_and_reject_a_typed_zero` | keep | `tests/test_add_compound.py` | Blank and typed zero are distinct user inputs with literal tR errors. Submit through the Add button. |
| T003 | [tests/test_add_compound.py:297](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_add_compound.py:297)<br>`test_duplicate_name_keeps_dialog_open` | merge | `tests/test_add_compound.py` | Add the duplicate-name case to `test_duplicate_name_is_reported_with_missing_fields`. Assert the complete displayed error. |
| T004 | [tests/test_add_compound.py:308](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_add_compound.py:308)<br>`test_zero_retention_time_rejected` | merge | `tests/test_add_compound.py` | Typed-zero tR is already exercised by `test_required_spin_boxes_ask_for_a_blank_value_and_reject_a_typed_zero`. |
| T005 | [tests/test_add_compound.py:317](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_add_compound.py:317)<br>`test_zero_mass0_rejected` | keep | `tests/test_add_compound.py` | A valid completed form with zero Mass0 must be rejected. Assert the complete displayed Mass0 error through Add. |

#### tests/test_app_stylesheet.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T006 | [tests/test_app_stylesheet.py:18](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_app_stylesheet.py:18)<br>`test_parentless_dialog_is_styled_once_stylesheet_is_app_wide` | keep | `tests/test_app_stylesheet.py` | Renders a parentless dialog before and after applying the stylesheet. Retain the actual sampled fill result and test both schemes. |
| T007 | [tests/test_app_stylesheet.py:34](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_app_stylesheet.py:34)<br>`test_logo_drops_its_white_background_and_inks_in_the_active_text_colour` | keep | `tests/test_app_stylesheet.py` | Samples actual logo pixels before and after a live scheme change, including transparent background and unchanged green artwork. |

#### tests/test_deconvolution_indicator.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T008 | [tests/test_deconvolution_indicator.py:7](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_deconvolution_indicator.py:7)<br>`test_status_bar_names_the_deconvolution_of_the_compound_shown_after_loading` | merge | `tests/test_main_window_shell.py` | Combine the loaded-compound status with `test_deconvolution_status_opens_its_settings_page`. Verify the current compound's displayed settings and click destination together. |

#### tests/test_documentation_viewer.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T009 | [tests/test_documentation_viewer.py:83](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_documentation_viewer.py:83)<br>`test_documentation_window_loads_first_file` | keep | `tests/test_documentation_viewer.py` | Opening Documentation discovers and orders real temporary documents and selects the literal first file. Drop the unrelated window-title spelling pin. |

#### tests/test_focus_selected_samples.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T010 | [tests/test_focus_selected_samples.py:47](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_focus_selected_samples.py:47)<br>`test_focus_selected_then_show_all` | keep | `tests/test_sidebar.py` | Shown sample names become exactly S1/S2, then S1/S2/S3 after Show All. Trigger the actual menu actions rather than emitting their signals. |

#### tests/test_main_window_shell.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T011 | [tests/test_main_window_shell.py:18](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_main_window_shell.py:18)<br>`test_title_start_panel_and_quiet_status_bar_before_data` | keep | `tests/test_main_window_shell.py` | Before loading, the actual workspace is the start panel and the status bar has no persistent data summary. |
| T012 | [tests/test_main_window_shell.py:35](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_main_window_shell.py:35)<br>`test_view_menu_mirrors_display_checkboxes` | keep | `tests/test_main_window_shell.py` | Triggering the View action changes the checkbox, checkbox changes reflect back, and a disabled peak-scale option stays off. |
| T013 | [tests/test_main_window_shell.py:56](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_main_window_shell.py:56)<br>`test_drop_accepts_only_what_can_be_loaded_now` | merge | `tests/test_main_window_shell.py` | Move the compound-list, unsupported-file, and gated-folder cases into `test_drop_zone_lights_only_for_a_drop_the_window_takes`. Send drag/drop events instead of calling _dropped_path. |
| T014 | [tests/test_main_window_shell.py:77](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_main_window_shell.py:77)<br>`test_drop_zone_lights_only_for_a_drop_the_window_takes` | keep | `tests/test_main_window_shell.py` | Real drag-enter and drag-leave events toggle the drop indicator. Absorb the accepted/refused path cases and assert accepted payloads. |

#### tests/test_peak_review_menu.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T015 | [tests/test_peak_review_menu.py:59](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:59)<br>`test_apply_peak_verdicts_styles_tiles` | keep | `tests/test_peak_review_menu.py` | Real verdict input yields the literal Below threshold, Marked bad, or empty badge set. Inspect visible badge labels rather than a parallel descriptor getter. |
| T016 | [tests/test_peak_review_menu.py:69](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:69)<br>`test_accept_enabled_only_on_failed_or_accepted_tiles` | keep | `tests/test_peak_review_menu.py` | Actual context-menu actions enable acceptance only for eligible peaks, with the passing and rejected controls as negative cases. |
| T017 | [tests/test_peak_review_menu.py:82](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:82)<br>`test_accept_emits_review_for_clicked_tile` | keep | `tests/test_peak_review_menu.py` | Triggering acceptance emits exactly Cmp, A, ACCEPTED. |
| T018 | [tests/test_peak_review_menu.py:90](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:90)<br>`test_clear_bad_mark_clears_the_review` | keep | `tests/test_peak_review_menu.py` | Triggering Clear Bad Mark emits exactly Cmp, B, None. This is a real clear command, not an absence-only assertion. |
| T019 | [tests/test_peak_review_menu.py:98](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:98)<br>`test_action_applies_to_every_selected_tile` | keep | `tests/test_peak_review_menu.py` | Triggering Mark Bad for A/C emits those exact names and REJECTED. |
| T020 | [tests/test_peak_review_menu.py:110](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:110)<br>`test_not_detected_tile_is_flat_grey_until_reviewed` | merge | `tests/test_plot_grid_ui.py` | Combine the review-overrides-grey-card case with `test_not_detected_tile_is_tinted_throughout_and_its_traces_faded`; preserve both visible badges after rejection. |
| T021 | [tests/test_peak_review_menu.py:128](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:128)<br>`test_group_accept_skips_passing_tiles` | merge | `tests/test_peak_review_menu.py` | The selected-group acceptance table in `test_group_accept_states_what_it_does` covers skipping passing peaks. Preserve this rejected-peak exclusion as another row there. |
| T022 | [tests/test_peak_review_menu.py:137](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:137)<br>`test_curve_fit_menu_emits_override_for_selected_tiles` | keep | `tests/test_peak_review_menu.py` | Triggering Gaussian for A/C emits exactly their names and gaussian. Keep the output assertion, not just the checked state. |
| T023 | [tests/test_peak_review_menu.py:153](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:153)<br>`test_show_only_selected_disabled_when_nothing_selected` | merge | `tests/test_peak_review_menu.py` | Fold the empty selection's disabled Show Only action into `test_review_menu_names_its_targets_and_acts_on_them`. |
| T024 | [tests/test_peak_review_menu.py:162](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:162)<br>`test_show_only_selected_uses_clicked_tile_when_not_in_selection` | keep | `tests/test_peak_review_menu.py` | A context menu on unselected B emits exactly B even while A is selected. |
| T025 | [tests/test_peak_review_menu.py:173](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:173)<br>`test_show_all_samples_menu_emits_request` | merge | `tests/test_sidebar.py` | Fold the Show All action's exact emitted request into `test_focus_selected_then_show_all`, then verify the resulting shown sample list. |
| T026 | [tests/test_peak_review_menu.py:183](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_peak_review_menu.py:183)<br>`test_curve_fit_menu_checks_common_override` | merge | `tests/test_peak_review_menu.py` | Combine the common EMG check with `test_curve_fit_menu_emits_override_for_selected_tiles`. Assert the resulting override as well as its initial menu indication. |

#### tests/test_plot_grid_ui.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T027 | [tests/test_plot_grid_ui.py:11](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_plot_grid_ui.py:11)<br>`test_grid_keeps_every_tile_on_screen_when_they_fit` | keep | `tests/test_plot_grid_ui.py` | The public grid-layout function returns the literal fit result, 5 columns with stretching rows. Keep this concrete layout contract. |
| T028 | [tests/test_plot_grid_ui.py:15](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_plot_grid_ui.py:15)<br>`test_grid_scrolls_with_readable_tiles_when_they_do_not_fit` | keep | `tests/test_plot_grid_ui.py` | The public grid-layout function returns the literal scroll result, 4 columns and 163-pixel rows. Keep the fit/overflow distinction. |
| T029 | [tests/test_plot_grid_ui.py:19](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_plot_grid_ui.py:19)<br>`test_grid_with_no_tiles_is_one_column` | merge | `tests/test_plot_grid_ui.py` | Add the empty-grid input to the kept fit-layout table. Avoid a separate test function and fixture setup. |
| T030 | [tests/test_plot_grid_ui.py:23](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_plot_grid_ui.py:23)<br>`test_nice_ticks_and_scale_text` | merge | `tests/test_chart_summaries.py` | Move tick-label and multiplier cases into `test_abundance_marks_the_selected_samples_and_ticks_on_round_numbers`. Assert the actual axis labels instead of two utility implementations. |
| T031 | [tests/test_plot_grid_ui.py:45](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_plot_grid_ui.py:45)<br>`test_select_all_and_escape` | keep | `tests/test_plot_grid_ui.py` | Ctrl+A emits exactly A/B/C/D and Escape clears a previously nonempty selection. |
| T032 | [tests/test_plot_grid_ui.py:53](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_plot_grid_ui.py:53)<br>`test_arrows_move_focus_and_space_toggles` | keep | `tests/test_plot_grid_ui.py` | Arrow and Space key events select the exact B/D sample sequence. |
| T033 | [tests/test_plot_grid_ui.py:67](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_plot_grid_ui.py:67)<br>`test_enter_and_double_click_open_detailed_view` | keep | `tests/test_plot_grid_ui.py` | Return opens the exact Cmp/B detailed view. Rename the test because its body never double-clicks. |
| T034 | [tests/test_plot_grid_ui.py:77](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_plot_grid_ui.py:77)<br>`test_double_click_opens_once_without_a_second_toggle` | keep | `tests/test_plot_grid_ui.py` | A real double-click emits one open for A. Keep the release-selection regression with an exact expected click sequence. |

#### tests/test_post_load_checklist.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T035 | [tests/test_post_load_checklist.py:52](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_post_load_checklist.py:52)<br>`test_unchanged_checklist_offers_one_continue` | keep | `tests/test_post_load_checklist.py` | Changing and reverting the standard changes the literal visible action set between Continue and Apply/Continue without changes. |
| T036 | [tests/test_post_load_checklist.py:69](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_post_load_checklist.py:69)<br>`test_dialog_table_sorts_problems_first_and_warns` | keep | `tests/test_post_load_checklist.py` | A concrete MM report sorts to None/Miss/Has and shows No pattern, No files matched, and 4 files: A, B, C. Keep semantic results, not only warning-fill constants. |
| T037 | [tests/test_post_load_checklist.py:95](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_post_load_checklist.py:95)<br>`test_apply_sets_internal_standard_on_toolbar` | keep | `tests/test_post_load_checklist.py` | Applying a Norvaline choice changes the actual toolbar standard to Norvaline. Click Apply instead of directly calling accept. |
| T038 | [tests/test_post_load_checklist.py:113](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_post_load_checklist.py:113)<br>`test_continue_without_changes_leaves_internal_standard_unchanged` | keep | `tests/test_post_load_checklist.py` | Continue without changes leaves the previously chosen Alanine intact despite a staged Norvaline choice. Click that actual button. |

#### tests/test_r3_charts_detail.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T039 | [tests/test_r3_charts_detail.py:15](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_detail.py:15)<br>`test_one_toolbar_pans_zooms_and_resets_all_three_charts` | keep | `tests/test_detailed_plot_dialog.py` | Pan/Zoom/Reset buttons affect all three live plots, with literal modes and reset bounds. |
| T040 | [tests/test_r3_charts_detail.py:37](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_detail.py:37)<br>`test_footer_separates_facts_with_dots` | delete | Remove test. | Only pins punctuation and phrasing of the footer after manually injecting widget internals. |
| T041 | [tests/test_r3_charts_detail.py:70](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_detail.py:70)<br>`test_spectrum_labels_never_share_a_column` | merge | `tests/test_detailed_plot_dialog.py` | Fold the crowded and zoomed peak-label cases into `test_spectrum_labels_own_ions_first_and_never_the_baseline`. Both use the same spectrum and zoom. |
| T042 | [tests/test_r3_charts_detail.py:83](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_detail.py:83)<br>`test_detail_axes_line_up_whatever_the_tick_labels` | merge | `tests/test_detailed_plot_dialog.py` | Keep the alignment invariant in the existing detailed-dialog interaction scenario; remove the arbitrary 64-pixel left-margin pin. |

#### tests/test_r3_charts_grid.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T043 | [tests/test_r3_charts_grid.py:16](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_grid.py:16)<br>`test_retention_time_text_matches_the_sidebar_rounding` | merge | `tests/test_plot_grid_ui.py` | Fold the formatting boundary inputs into `test_grid_header_names_the_compound_with_tr_and_count` and assert its actual summary label. |
| T044 | [tests/test_r3_charts_grid.py:63](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_grid.py:63)<br>`test_grid_header_names_the_compound_with_tr_and_count` | keep | `tests/test_plot_grid_ui.py` | Plotting, selecting S2, changing tR, and clearing produce literal compound and selection summaries. |
| T045 | [tests/test_r3_charts_grid.py:117](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_grid.py:117)<br>`test_review_commands_name_how_many_plots_they_change` | merge | `tests/test_peak_review_menu.py` | Move plural target counts into `test_group_accept_states_what_it_does` and `test_group_mark_bad_states_what_it_does`. Trigger the actions and check their exact recipients. |
| T046 | [tests/test_r3_charts_grid.py:127](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_grid.py:127)<br>`test_review_commands_stay_singular_for_one_plot` | merge | `tests/test_peak_review_menu.py` | Keep singular target naming alongside `test_accept_emits_review_for_clicked_tile`, which also checks the command's effect. |
| T047 | [tests/test_r3_charts_grid.py:136](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_grid.py:136)<br>`test_chip_row_wraps_before_truncating_a_chip` | keep | `tests/test_plot_grid_ui.py` | At a concrete narrow width the real chip row wraps to two rows and preserves each full chip. Replace the sizeHint-derived width oracle with actual visible text and containment. |
| T048 | [tests/test_r3_charts_grid.py:157](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_grid.py:157)<br>`test_badges_sit_below_the_caption_at_every_width` | keep | `tests/test_plot_grid_ui.py` | Real tile resizing keeps its literal sample caption and badge row below it. Keep visible rectangles; drop private layout-object identity. |

#### tests/test_r3_charts_popups.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T049 | [tests/test_r3_charts_popups.py:19](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_popups.py:19)<br>`test_bar_value_text_uses_one_precision` | merge | `tests/test_chart_popups.py` | The abundance popup already asserts 1.13, dash, less-than-0.01, and 0.91. Put remaining NaN/rounding cases in that rendered-row table. |
| T050 | [tests/test_r3_charts_popups.py:33](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_popups.py:33)<br>`test_abundance_popup_puts_each_value_beside_its_own_sample` | merge | `tests/test_chart_popups.py` | Combine these extra low/zero values with `test_both_popups_read_top_down_in_grid_order_with_values_paired`. Keep exact sample/value pairing. |
| T051 | [tests/test_r3_charts_popups.py:55](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_popups.py:55)<br>`test_hover_hint_only_where_values_are_not_printed` | delete | Remove test. | Only pins whether explanatory Hover copy is present. Hover and printed-value behaviours are tested elsewhere. |
| T052 | [tests/test_r3_charts_popups.py:91](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_charts_popups.py:91)<br>`test_identity_counts_name_their_units_and_grey_states` | merge | `tests/test_identity_chart.py` | Combine the literal qualifier-cell counts and visible marks with `test_every_identity_cell_carries_a_visible_state_mark`. Drop HTML-entity and prose-layout assertions. |

#### tests/test_r3_dialogs_add_compound.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T053 | [tests/test_r3_dialogs_add_compound.py:35](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_add_compound.py:35)<br>`test_empty_labelled_submit_flags_every_required_field` | keep | `tests/test_add_compound.py` | An empty labelled submission displays the exact required-field errors, marks those fields, and focuses the name. Click Add instead of _on_ok. |
| T054 | [tests/test_r3_dialogs_add_compound.py:50](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_add_compound.py:50)<br>`test_empty_unlabelled_submit_flags_every_required_field` | keep | `tests/test_add_compound.py` | An empty unlabelled submission marks the quantifier and first qualifier as well as name and tR. Click Add. |
| T055 | [tests/test_r3_dialogs_add_compound.py:70](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_add_compound.py:70)<br>`test_editing_one_field_clears_only_its_own_error` | keep | `tests/test_add_compound.py` | Editing one quantifier clears only its error while the other literal required errors remain. |
| T056 | [tests/test_r3_dialogs_add_compound.py:79](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_add_compound.py:79)<br>`test_duplicate_name_is_reported_with_missing_fields` | keep | `tests/test_add_compound.py` | A duplicate name and missing required fields are reported together. Absorb the completed duplicate-name case. |
| T057 | [tests/test_r3_dialogs_add_compound.py:93](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_add_compound.py:93)<br>`test_cross_field_ion_error_flags_the_ions_and_clears_on_edit` | keep | `tests/test_add_compound.py` | Equal Q/qualifier ions produce the exact visible distinct-ion error; correcting one ion clears it. |
| T058 | [tests/test_r3_dialogs_add_compound.py:109](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_add_compound.py:109)<br>`test_offsets_and_counts_start_blank_and_build_as_zero` | keep | `tests/test_add_compound.py` | Blank optional offsets and counts yield literal zero fields in the submitted record. Retain as a form-input contract and use Add to build it. |
| T059 | [tests/test_r3_dialogs_add_compound.py:141](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_add_compound.py:141)<br>`test_form_never_overlaps_and_scrolls_on_a_short_screen` | keep | `tests/test_add_compound.py` | Show and resize the real form in both modes; labels do not overlap, scrolling is available, and Add stays visible outside the scroll body. |

#### tests/test_r3_dialogs_settings.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T060 | [tests/test_r3_dialogs_settings.py:51](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_settings.py:51)<br>`test_short_fields_stay_narrow_and_left_aligned` | delete | Remove test. | Pins a 120-pixel cap and left-half positioning. Does not demonstrate unreadable or inaccessible controls. |
| T061 | [tests/test_r3_dialogs_settings.py:66](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_settings.py:66)<br>`test_footer_buttons_share_one_baseline` | delete | Remove test. | Pins a button baseline and equal height without exercising Save or Reset. |
| T062 | [tests/test_r3_dialogs_settings.py:73](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_settings.py:73)<br>`test_peak_validation_copy_names_the_badge_the_plots_show` | delete | Remove test. | Reads the badge text from the same production constant to compare copy. No literal independent expected behaviour. |
| T063 | [tests/test_r3_dialogs_settings.py:80](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_settings.py:80)<br>`test_no_settings_copy_points_at_the_removed_toolbar` | delete | Remove test. | Sweeps widget copy for the old word toolbar. Wording migration is not a lasting user contract. |
| T064 | [tests/test_r3_dialogs_settings.py:88](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_dialogs_settings.py:88)<br>`test_internal_standard_page_offers_the_standard_itself` | merge | `tests/test_settings_window.py` | The no-data Internal Standard state already exists in `test_labelled_settings_open_with_no_data`. |

#### tests/test_r3_integrate_review_menus.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T065 | [tests/test_r3_integrate_review_menus.py:36](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_integrate_review_menus.py:36)<br>`test_review_menu_and_context_menu_say_the_same_thing` | merge | `tests/test_peak_review_menu.py` | Fold menu equivalence into `test_review_menu_names_its_targets_and_acts_on_them`. Keep one literal action/payload oracle for both entry points. |

#### tests/test_r3_sidebar_charts.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T066 | [tests/test_r3_sidebar_charts.py:16](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_charts.py:16)<br>`test_mini_charts_pair_each_sample_with_its_own_values` | keep | `tests/test_chart_summaries.py` | Updating the charts with known sample data yields literal S1/S3 hover values and M+0/M+1/M+2 labels without changing caller order. |

#### tests/test_r3_sidebar_review.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T067 | [tests/test_r3_sidebar_review.py:41](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_review.py:41)<br>`test_review_menu_names_its_targets_and_acts_on_them` | keep | `tests/test_peak_review_menu.py` | The actual Review actions name and act on A/B or A alone. Absorb context-menu parity and the no-selection state. |
| T068 | [tests/test_r3_sidebar_review.py:77](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_review.py:77)<br>`test_deconvolution_status_opens_its_settings_page` | keep | `tests/test_main_window_shell.py` | Clicking the status control opens the actual Deconvolution page. Absorb the loaded compound's status text. |

#### tests/test_r3_sidebar_state.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T069 | [tests/test_r3_sidebar_state.py:38](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_state.py:38)<br>`test_summaries_and_view_menu_follow_compound_switch` | keep | `tests/test_sidebar.py` | Selecting Plain/Corrected changes the shown summary and menu state without writing back; the real action writes only the chosen setting. |
| T070 | [tests/test_r3_sidebar_state.py:69](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_state.py:69)<br>`test_scale_summary_and_menu_follow_a_forced_scale_change` | keep | `tests/test_sidebar.py` | The View action selects peak scale and switching to a plain compound visibly falls back to Own scale. |
| T071 | [tests/test_r3_sidebar_state.py:96](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_state.py:96)<br>`test_sample_checkboxes_keep_list_order_and_count_matches` | keep | `tests/test_sidebar.py` | Unchecking, rechecking, filtering, and Space produce exact shown-name lists and counts in stable list order. |
| T072 | [tests/test_r3_sidebar_state.py:128](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_state.py:128)<br>`test_filter_with_no_match_shows_the_count_and_escape_clears_it` | keep | `tests/test_sidebar.py` | Typing an unmatched filter hides the list and shows 0 of 2; Escape restores the list and count 2. |
| T073 | [tests/test_r3_sidebar_state.py:161](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_state.py:161)<br>`test_browse_keeps_six_rows_and_inspector_switches_sections` | merge | `tests/test_sidebar.py` | Replace this six-row/switcher snapshot with the more complete small/tall inspector cases in `test_laptop_lists_keep_four_compounds_and_three_samples_with_samples_open`. |
| T074 | [tests/test_r3_sidebar_state.py:171](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_state.py:171)<br>`test_dragged_split_is_remembered` | keep | `tests/test_sidebar.py` | A chosen splitter share is restored by a newly constructed toolbar. Simulate the splitter gesture instead of calling its slot. |
| T075 | [tests/test_r3_sidebar_state.py:190](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r3_sidebar_state.py:190)<br>`test_sections_collapse_and_remember` | keep | `tests/test_sidebar.py` | A header click collapses Summary and a newly constructed toolbar remembers that choice. Drop the unrelated Apply window copy assertion. |

#### tests/test_r5_charts_detail.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T076 | [tests/test_r5_charts_detail.py:22](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_detail.py:22)<br>`test_double_click_resets_only_that_chart` | keep | `tests/test_detailed_plot_dialog.py` | A real double-click resets the TIC while EIC/MS retain the exact zoomed range. |
| T077 | [tests/test_r5_charts_detail.py:36](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_detail.py:36)<br>`test_context_menu_resets_only_that_chart` | keep | `tests/test_detailed_plot_dialog.py` | Triggering Reset This Chart resets only MS; Zoom suppresses the competing context menu. |
| T078 | [tests/test_r5_charts_detail.py:53](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_detail.py:53)<br>`test_reset_all_names_its_scope` | delete | Remove test. | Only pins Reset all button text and tooltip wording. Reset behaviour is already exercised. |

#### tests/test_r5_charts_identity.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T079 | [tests/test_r5_charts_identity.py:64](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_identity.py:64)<br>`test_every_identity_cell_carries_a_visible_state_mark` | keep | `tests/test_identity_chart.py` | A real identity popup draws literal check, cross, and absent marks for the known samples. Absorb count cases and inspect displayed labels. |
| T080 | [tests/test_r5_charts_identity.py:78](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_identity.py:78)<br>`test_rebuilding_the_grid_replaces_its_marks` | keep | `tests/test_identity_chart.py` | Updating two rows to one replaces marks, then clear removes them. Keep exact visible mark results. |
| T081 | [tests/test_r5_charts_identity.py:90](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_identity.py:90)<br>`test_one_sample_is_a_slim_strip_not_a_slab` | merge | `tests/test_identity_chart.py` | Combine one-row sidebar/popup height and pinned-header geometry with `test_one_sample_leaves_no_band_below_it`. Drop expected values derived by identity_chart_height. |
| T082 | [tests/test_r5_charts_identity.py:139](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_identity.py:139)<br>`test_not_detected_tile_is_tinted_throughout_and_its_traces_faded` | keep | `tests/test_plot_grid_ui.py` | Real detected and missing samples produce the literal Not detected badge and distinct trace opacity. Absorb the reviewed-card case without changing any data. |
| T083 | [tests/test_r5_charts_identity.py:154](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_identity.py:154)<br>`test_identity_popup_row_selects_the_sample_through_the_qc_widget` | keep | `tests/test_identity_chart.py` | Opening the actual QC popup and pressing keys emits exactly S2 through the owning widget and closes the dialog. |
| T084 | [tests/test_r5_charts_identity.py:174](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_identity.py:174)<br>`test_activated_sample_is_selected_focused_and_scrolled_to` | keep | `tests/test_plot_grid_ui.py` | Activating S23 selects and focuses that exact sample and brings its tile inside the viewport. |

#### tests/test_r5_charts_popups.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T085 | [tests/test_r5_charts_popups.py:25](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_popups.py:25)<br>`test_both_popups_read_top_down_in_grid_order_with_values_paired` | keep | `tests/test_chart_popups.py` | Both popup types preserve literal sample order and value pairing. Absorb low, zero, tiny, and NaN value cases. |
| T086 | [tests/test_r5_charts_popups.py:47](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_popups.py:47)<br>`test_clicking_a_row_activates_its_sample_and_closes` | keep | `tests/test_chart_popups.py` | A mouse click on the second row emits exactly Bio_002 and accepts/closes the dialog. |
| T087 | [tests/test_r5_charts_popups.py:63](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_popups.py:63)<br>`test_arrow_keys_and_enter_activate_a_row` | merge | `tests/test_chart_popups.py` | The real-modal focus/navigation test `test_row_keys_work_from_the_focus_a_real_open_gives` covers this key path more realistically. Preserve the ratios case as a parameter. |
| T088 | [tests/test_r5_charts_popups.py:83](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_popups.py:83)<br>`test_rows_stay_inert_when_nothing_listens` | delete | Remove test. | The running app connects every abundance, ratio, and identity popup to sample activation. This standalone unconnected-widget mode only preserves receiver-introspection branching. |

#### tests/test_r5_charts_review.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T089 | [tests/test_r5_charts_review.py:48](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_review.py:48)<br>`test_accept_reaches_eligible_peaks_when_the_lead_passes` | merge | `tests/test_peak_review_menu.py` | The none-accepted row in `test_group_accept_states_what_it_does` covers the same Pass/Low1/Low2 target set. |
| T090 | [tests/test_r5_charts_review.py:63](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_review.py:63)<br>`test_accept_turns_into_clear_when_the_eligible_peaks_are_accepted` | merge | `tests/test_peak_review_menu.py` | The all-accepted row in `test_group_accept_states_what_it_does` covers the same clear-acceptance result. |
| T091 | [tests/test_r5_charts_review.py:78](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_review.py:78)<br>`test_accept_stays_disabled_when_nothing_selected_is_below_threshold` | merge | `tests/test_peak_review_menu.py` | Keep the all-passing disabled-acceptance case in `test_accept_enabled_only_on_failed_or_accepted_tiles`. |

#### tests/test_r5_charts_spectrum.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T092 | [tests/test_r5_charts_spectrum.py:23](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_spectrum.py:23)<br>`test_spectrum_labels_own_ions_first_and_never_the_baseline` | keep | `tests/test_detailed_plot_dialog.py` | The rendered spectrum shows literal own-ion labels, excludes baseline ions, and reveals the exact separate labels after zoom. |
| T093 | [tests/test_r5_charts_spectrum.py:38](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_charts_spectrum.py:38)<br>`test_live_scheme_switch_repaints_spectrum_label_boxes` | keep | `tests/test_detailed_plot_dialog.py` | Switching the scheme recolours already-created label boxes. Exercise apply_color_scheme and assert literal light/dark rendered colours, not notifier internals. |

#### tests/test_r5_shell_checklist.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T094 | [tests/test_r5_shell_checklist.py:17](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_shell_checklist.py:17)<br>`test_checklist_names_the_loaded_compound_list_and_opens_it` | keep | `tests/test_post_load_checklist.py` | The loaded compound-list name appears and both Open and Show Folder buttons send the exact file and directory URLs. |
| T095 | [tests/test_r5_shell_checklist.py:39](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_shell_checklist.py:39)<br>`test_checklist_teaches_the_reload_path_for_existing_compounds` | delete | Remove test. | Only pins reload-instruction prose and its sentence order. The kept Open and inline-help tests cover the actionable affordances. |

#### tests/test_r5_shell_contrast.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T096 | [tests/test_r5_shell_contrast.py:41](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_shell_contrast.py:41)<br>`test_small_text_token_pairs_reach_aa` | merge | `tests/test_app_stylesheet.py` | Retain accessibility thresholds against the real rendered widgets in `test_rendered_filled_buttons_keep_white_labels_at_aa_in_both_schemes`. The hand-maintained token-pair list does not prove those widget pairings exist. |
| T097 | [tests/test_r5_shell_contrast.py:52](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_shell_contrast.py:52)<br>`test_status_icon_marks_and_focus_rings_reach_three_to_one` | merge | `tests/test_app_stylesheet.py` | Check icon/focus contrast in the real rendered-state test rather than a second token-only table. |
| T098 | [tests/test_r5_shell_contrast.py:61](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_shell_contrast.py:61)<br>`test_token_values_are_unique_so_a_scheme_remap_is_unambiguous` | merge | `tests/test_app_stylesheet.py` | Keep the live recolouring regression in `test_logo_drops_its_white_background_and_inks_in_the_active_text_colour`. A global ban on duplicate hex values is an implementation constraint. |
| T099 | [tests/test_r5_shell_contrast.py:67](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_shell_contrast.py:67)<br>`test_rendered_filled_buttons_keep_white_labels_at_aa_in_both_schemes` | keep | `tests/test_app_stylesheet.py` | Samples actual filled buttons in both schemes and checks a literal 4.5 contrast threshold. Check the actual rendered label colour as well as the fill. |

#### tests/test_r5_sidebar_empty.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T100 | [tests/test_r5_sidebar_empty.py:17](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_empty.py:17)<br>`test_unchecking_every_sample_empties_the_workspace` | keep | `tests/test_sidebar.py` | Unchecking all shown samples displays the empty workspace and disables Apply; Show All restores the exact three-sample set. |

#### tests/test_r5_sidebar_layout.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T101 | [tests/test_r5_sidebar_layout.py:46](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_layout.py:46)<br>`test_peak_window_stays_whole_on_a_short_sidebar` | merge | `tests/test_sidebar.py` | Combine short-height and expanded/collapsed Samples cases with `test_peak_window_stays_whole_at_1024x768`. |
| T102 | [tests/test_r5_sidebar_layout.py:58](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_layout.py:58)<br>`test_closing_samples_gives_its_room_back_without_a_resize` | keep | `tests/test_sidebar.py` | Opening then closing Samples returns the splitter to the previous actual layout without a window resize. |
| T103 | [tests/test_r5_sidebar_layout.py:72](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_layout.py:72)<br>`test_a_short_filtered_list_leaves_its_room_to_samples` | keep | `tests/test_sidebar.py` | Filtering to the known six matching compounds gives visible room back to Samples. |
| T104 | [tests/test_r5_sidebar_layout.py:87](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_layout.py:87)<br>`test_dragged_split_is_kept_only_while_the_peak_window_fits` | merge | `tests/test_sidebar.py` | Add the too-small-inspector case to `test_dragged_split_is_remembered`. Keep the user's saved share separate from the actual safe layout. |
| T105 | [tests/test_r5_sidebar_layout.py:106](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_layout.py:106)<br>`test_summary_starts_collapsed_only_when_short_and_the_user_choice_wins` | keep | `tests/test_sidebar.py` | Short and tall windows have the correct initial Summary state and an explicit saved user choice overrides the default. |
| T106 | [tests/test_r5_sidebar_layout.py:127](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_layout.py:127)<br>`test_switching_compound_scrolls_the_inspector_back_to_the_top` | keep | `tests/test_sidebar.py` | After scrolling a long inspector, selecting another compound resets its actual scrollbar to zero. Drive selection normally. |

#### tests/test_r5_sidebar_menus.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T107 | [tests/test_r5_sidebar_menus.py:14](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_menus.py:14)<br>`test_baseline_correction_sits_with_the_peak_commands` | merge | `tests/test_sidebar.py` | The baseline action's location, shortcut, checked state, and persisted effect belong with `test_summaries_and_view_menu_follow_compound_switch`. |
| T108 | [tests/test_r5_sidebar_menus.py:32](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_menus.py:32)<br>`test_help_menu_and_settings_in_file` | delete | Remove test. | Only pins the menu title list and static action inventory. Functional Documentation, Settings, update, and About entry points can stay independently testable. |
| T109 | [tests/test_r5_sidebar_menus.py:59](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_menus.py:59)<br>`test_internal_standard_menu_checks_the_current_choice` | keep | `tests/test_sidebar.py` | Opening the standard menu reflects None then Glycine as the literal checked item. Trigger an item and assert the actual chosen standard. |

#### tests/test_r5_sidebar_summary.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T110 | [tests/test_r5_sidebar_summary.py:27](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_summary.py:27)<br>`test_abundance_marks_the_selected_samples_and_ticks_on_round_numbers` | keep | `tests/test_chart_summaries.py` | Known abundance data yields a literal 2-unit tick interval and selection S3, then clears it. Read real selected bars instead of highlighted_bars. |
| T111 | [tests/test_r5_sidebar_summary.py:42](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r5_sidebar_summary.py:42)<br>`test_label_incorporation_marks_only_the_selected_rows` | merge | `tests/test_chart_summaries.py` | Selection and clearing of ratio rows overlap `test_selecting_a_sample_scrolls_its_row_into_view` and `test_selection_leaves_other_bars_their_cohort_colours`. |

#### tests/test_r6_grid_review.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T112 | [tests/test_r6_grid_review.py:57](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_grid_review.py:57)<br>`test_group_accept_states_what_it_does` | keep | `tests/test_peak_review_menu.py` | The mixed/none/all accepted table asserts exact recipient names and review payload for each command. Trigger the menu actions instead of the internal toggle. |
| T113 | [tests/test_r6_grid_review.py:80](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_grid_review.py:80)<br>`test_group_mark_bad_states_what_it_does` | keep | `tests/test_peak_review_menu.py` | The mixed/none/all bad-mark table asserts exact target names and clear-versus-reject payload. Trigger the menu actions. |

#### tests/test_r6_grid_tiles.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T114 | [tests/test_r6_grid_tiles.py:54](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_grid_tiles.py:54)<br>`test_replotting_the_same_compound_keeps_selection_and_focus` | keep | `tests/test_plot_grid_ui.py` | Changing scale and replotting the same compound preserve literal S2/S4 selection and S4 focus without a spurious signal. |
| T115 | [tests/test_r6_grid_tiles.py:73](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_grid_tiles.py:73)<br>`test_replotting_drops_only_the_samples_no_longer_shown` | keep | `tests/test_plot_grid_ui.py` | Removing S4 keeps exactly S2 selected and emits that exact reduced selection. |
| T116 | [tests/test_r6_grid_tiles.py:86](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_grid_tiles.py:86)<br>`test_switching_compound_starts_with_no_selection` | merge | `tests/test_plot_grid_ui.py` | Add the switch-to-Leucine input to `test_replotting_the_same_compound_keeps_selection_and_focus`. Assert old selections clear only across compounds. |
| T117 | [tests/test_r6_grid_tiles.py:94](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_grid_tiles.py:94)<br>`test_context_menu_matches_the_review_menu_order` | merge | `tests/test_peak_review_menu.py` | Menu parity already belongs in `test_review_menu_names_its_targets_and_acts_on_them`. Drop separator/order pinning. |
| T118 | [tests/test_r6_grid_tiles.py:116](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_grid_tiles.py:116)<br>`test_density_sets_chart_text_size` | delete | Remove test. | Pins stylesheet substrings and font pixel constants. Density fit/scroll behaviour is covered separately. |
| T119 | [tests/test_r6_grid_tiles.py:136](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_grid_tiles.py:136)<br>`test_not_detected_badge_is_a_readable_pill_on_its_card` | merge | `tests/test_peak_review_menu.py` | Fold the neutral badge's rendered contrast into `test_apply_peak_verdicts_styles_tiles`. A _TONES dictionary check alone does not show a readable badge. |
| T120 | [tests/test_r6_grid_tiles.py:143](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_grid_tiles.py:143)<br>`test_scrolling_to_a_sample_survives_a_pending_resize` | merge | `tests/test_plot_grid_ui.py` | Add the delayed-resize event to `test_activated_sample_is_selected_focused_and_scrolled_to`. Preserve the timer race without a second 24-tile fixture. |

#### tests/test_r6_popups_detail.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T121 | [tests/test_r6_popups_detail.py:15](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_detail.py:15)<br>`test_detailed_legend_names_qualifier_states_in_words` | delete | Remove test. | Only calls the private _channel_label formatter after injecting identity internals; it never renders or opens the actual legend. |
| T122 | [tests/test_r6_popups_detail.py:51](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_detail.py:51)<br>`test_isotopologues_are_named_together_at_full_range_and_apart_when_zoomed` | keep | `tests/test_detailed_plot_dialog.py` | The rendered spectrum shows the literal M+0…M+3 cluster and exact separated ion labels when zoomed. Assert displayed artists and bracket visibility. |
| T123 | [tests/test_r6_popups_detail.py:73](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_detail.py:73)<br>`test_reset_gesture_is_in_the_tooltip_and_double_click_resets_while_panning` | merge | `tests/test_detailed_plot_dialog.py` | Parameterize pan and zoom states on `test_double_click_resets_only_that_chart`. Drop the repeated tooltip sentence assertion. |

#### tests/test_r6_popups_identity.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T124 | [tests/test_r6_popups_identity.py:50](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_identity.py:50)<br>`test_compound_with_no_expected_ratios_says_so_instead_of_a_grey_grid` | keep | `tests/test_identity_chart.py` | Unconfigured methods display a setup note while configured methods display the grid. Assert literal displayed instructions, not an imported production message constant. |
| T125 | [tests/test_r6_popups_identity.py:70](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_identity.py:70)<br>`test_absent_cells_are_outlines_and_assessed_grids_stay` | merge | `tests/test_identity_chart.py` | Combine the absent-cell outline case with `test_every_identity_cell_carries_a_visible_state_mark` and `test_targeted_qc_identity_chart_renders_grid_cells`. |
| T126 | [tests/test_r6_popups_identity.py:88](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_identity.py:88)<br>`test_sidebar_rows_keep_their_marks_and_names_and_scroll` | keep | `tests/test_identity_chart.py` | Thirty actual sample rows remain named/marked and can scroll. Drop dimension expectations calculated from imported row constants. |
| T127 | [tests/test_r6_popups_identity.py:108](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_identity.py:108)<br>`test_sidebar_highlights_the_selection_and_keeps_every_row` | keep | `tests/test_identity_chart.py` | Selecting S2 marks exactly that row, survives result replacement, and clear removes it without dropping the other names. |
| T128 | [tests/test_r6_popups_identity.py:124](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_identity.py:124)<br>`test_one_sample_leaves_no_band_below_it` | keep | `tests/test_identity_chart.py` | A one-sample chart occupies only its visible content, leaving room for the neighbouring widget. Absorb the popup strip/header case. |
| T129 | [tests/test_r6_popups_identity.py:142](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_identity.py:142)<br>`test_long_sidebar_names_shorten_to_fit_instead_of_running_off` | keep | `tests/test_identity_chart.py` | Long real sample labels visibly elide without losing uniqueness or the full hover/activation name. |

#### tests/test_r6_popups_keyboard_axis.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T130 | [tests/test_r6_popups_keyboard_axis.py:19](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_keyboard_axis.py:19)<br>`test_row_keys_work_from_the_focus_a_real_open_gives` | keep | `tests/test_chart_popups.py` | Drives keys on the widget that receives focus during real exec; End/Up/Return emits exactly Bio_029 and accepts. |
| T131 | [tests/test_r6_popups_keyboard_axis.py:54](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_keyboard_axis.py:54)<br>`test_return_first_shows_the_row_it_would_open` | keep | `tests/test_chart_popups.py` | The first Return marks Bio_001 without activating it; the next Return emits exactly Bio_001. |
| T132 | [tests/test_r6_popups_keyboard_axis.py:70](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_keyboard_axis.py:70)<br>`test_footer_names_the_keys` | delete | Remove test. | Only pins the footer instruction sentence; the keys themselves have interaction tests. |
| T133 | [tests/test_r6_popups_keyboard_axis.py:81](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_keyboard_axis.py:81)<br>`test_value_axis_and_unit_stay_in_view_at_the_bottom_of_a_long_list` | keep | `tests/test_chart_popups.py` | After scrolling to the last sample, the pinned axis and literal multiplier/tick strings remain aligned and visible. |
| T134 | [tests/test_r6_popups_keyboard_axis.py:113](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_keyboard_axis.py:113)<br>`test_ratio_rows_with_no_ratio_show_a_dash_and_say_why` | keep | `tests/test_chart_popups.py` | Concrete zero and NaN rows show dashes with literal explanatory notes while the supplied array remains unchanged. |
| T135 | [tests/test_r6_popups_keyboard_axis.py:136](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_popups_keyboard_axis.py:136)<br>`test_hovering_a_blank_ratio_row_shows_its_note` | merge | `tests/test_chart_popups.py` | Fold actual hover delivery into `test_ratio_rows_with_no_ratio_show_a_dash_and_say_why`. Assert the complete tooltip for Bio_002. |

#### tests/test_r6_sidebar_checklist.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T136 | [tests/test_r6_sidebar_checklist.py:34](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_checklist.py:34)<br>`test_checklist_text_never_collides_on_a_short_screen` | keep | `tests/test_post_load_checklist.py` | At the listed short screen sizes, the real dialog has no overlapping text and its buttons remain visible outside the scrolling body. |
| T137 | [tests/test_r6_sidebar_checklist.py:49](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_checklist.py:49)<br>`test_change_pattern_steps_open_inline_under_the_compound_list` | keep | `tests/test_post_load_checklist.py` | Clicking the help toggle reveals and hides the instructions and guide link under the loaded source file. Drop glyph and prose-prefix pins. |
| T138 | [tests/test_r6_sidebar_checklist.py:71](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_checklist.py:71)<br>`test_mm_table_keeps_four_rows_however_short_the_dialog` | merge | `tests/test_post_load_checklist.py` | Check visible table rows in `test_checklist_text_never_collides_on_a_short_screen` instead of a separate minimum-row fixture. |
| T139 | [tests/test_r6_sidebar_checklist.py:84](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_checklist.py:84)<br>`test_opening_the_steps_on_a_short_screen_scrolls_them_into_view` | merge | `tests/test_post_load_checklist.py` | Add the scrolled-short-dialog case to `test_change_pattern_steps_open_inline_under_the_compound_list`. |

#### tests/test_r6_sidebar_inspector.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T140 | [tests/test_r6_sidebar_inspector.py:50](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_inspector.py:50)<br>`test_laptop_lists_keep_four_compounds_and_three_samples_with_samples_open` | keep | `tests/test_sidebar.py` | The shown laptop sidebar retains at least four compound rows, three sample rows, and a usable section switcher. |
| T141 | [tests/test_r6_sidebar_inspector.py:61](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_inspector.py:61)<br>`test_peak_window_stays_whole_at_1024x768` | keep | `tests/test_sidebar.py` | At 1024x768, the actual peak control stays in the viewport whether Samples is open or closed. Absorb the shorter-height inputs. |
| T142 | [tests/test_r6_sidebar_inspector.py:70](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_inspector.py:70)<br>`test_switcher_reaches_display_and_summary_in_one_click` | keep | `tests/test_sidebar.py` | Clicking Display, Summary, and Peak window makes the exact relevant controls visible in the short sidebar. |
| T143 | [tests/test_r6_sidebar_inspector.py:96](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_inspector.py:96)<br>`test_tall_sidebar_shows_every_section_heading_and_no_switcher` | merge | `tests/test_sidebar.py` | Parameterize the tall-height state in `test_switcher_leaves_once_there_is_room_and_sections_keep_their_state`. |
| T144 | [tests/test_r6_sidebar_inspector.py:106](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_inspector.py:106)<br>`test_switcher_leaves_once_there_is_room_and_sections_keep_their_state` | keep | `tests/test_sidebar.py` | Resizing short to tall removes the switcher and restores the previously collapsed section state. |

#### tests/test_r6_sidebar_summary.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T145 | [tests/test_r6_sidebar_summary.py:53](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_summary.py:53)<br>`test_thirty_samples_are_named_on_readable_rows_that_scroll` | keep | `tests/test_chart_summaries.py` | Thirty concrete names remain on readable scrollable rows in both summary widgets. Assert actual visible names and row geometry, not imported size constants. |
| T146 | [tests/test_r6_sidebar_summary.py:67](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_summary.py:67)<br>`test_a_few_samples_fit_without_scrolling` | merge | `tests/test_chart_summaries.py` | Add the three-sample non-scrolling case to `test_thirty_samples_are_named_on_readable_rows_that_scroll`. |
| T147 | [tests/test_r6_sidebar_summary.py:77](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_summary.py:77)<br>`test_selecting_a_sample_scrolls_its_row_into_view` | keep | `tests/test_chart_summaries.py` | Selecting Bio_029 and Bio_000 scrolls the exact requested rows into view. Read rendered rows/selection rather than a testing getter. |

#### tests/test_r6_sidebar_window_scope.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T148 | [tests/test_r6_sidebar_window_scope.py:8](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r6_sidebar_window_scope.py:8)<br>`test_apply_window_states_that_it_re_extracts_every_shown_sample` | keep | `tests/test_integration_window.py` | Clicking Apply window emits exactly all three shown samples even when only S2 is selected; displayed scope states that difference. Keep every numeric request argument unchanged. |

#### tests/test_r7_charts_badges.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T149 | [tests/test_r7_charts_badges.py:10](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_badges.py:10)<br>`test_problem_badges_read_as_pills_on_their_tinted_card` | merge | `tests/test_peak_review_menu.py` | Fold danger and warning cases into `test_apply_peak_verdicts_styles_tiles`. Check rendered labels and contrast rather than _TONES and tile_tint. |

#### tests/test_r7_charts_density.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T150 | [tests/test_r7_charts_density.py:9](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_density.py:9)<br>`test_compact_fits_a_laptop_grid_that_comfortable_scrolls` | merge | `tests/test_plot_grid_ui.py` | Combine compact/comfortable inputs with the two literal fit/scroll grid-layout tests. Replace relative tuple comparisons with expected concrete outcomes. |
| T151 | [tests/test_r7_charts_density.py:18](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_density.py:18)<br>`test_compact_still_fits_at_the_small_laptop_size` | merge | `tests/test_plot_grid_ui.py` | Add the small-laptop eleven-sample input to the existing grid fit table. |

#### tests/test_r7_charts_detail.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T152 | [tests/test_r7_charts_detail.py:13](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_detail.py:13)<br>`test_detailed_text_is_at_least_ten_pixels` | delete | Remove test. | Reads constructor font constants back as a threshold. It does not demonstrate that labels actually fit or can be read. |
| T153 | [tests/test_r7_charts_detail.py:24](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_detail.py:24)<br>`test_the_chromatogram_gets_half_the_chart_height` | delete | Remove test. | Pins the initial splitter's 45-percent/half-height allocation. No documented user promise requires that exact proportion. |
| T154 | [tests/test_r7_charts_detail.py:36](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_detail.py:36)<br>`test_each_chart_keeps_room_for_its_title_and_axis_label` | delete | Remove test. | Only reads minimumHeight >= 140; a chart can satisfy it while its title/axis labels are still clipped. |

#### tests/test_r7_charts_documentation.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T155 | [tests/test_r7_charts_documentation.py:36](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_documentation.py:36)<br>`test_documentation_shows_a_loading_note_then_the_page` | keep | `tests/test_documentation_viewer.py` | Opening the viewer displays literal Loading text, then switches to the rendered page. Assert the temporary Quick Start page's actual content too. |
| T156 | [tests/test_r7_charts_documentation.py:45](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_documentation.py:45)<br>`test_a_failed_render_says_so_and_offers_a_retry` | keep | `tests/test_documentation_viewer.py` | A failed load offers the real retry button and retry reaches the rendered page. Inject loadFinished failure through its signal rather than calling the private slot. |
| T157 | [tests/test_r7_charts_documentation.py:55](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_documentation.py:55)<br>`test_short_page_titles_carry_no_repeat_tooltip` | merge | `tests/test_documentation_viewer.py` | Fold the short-title/no-tooltip case into `test_documentation_window_loads_first_file`. |

#### tests/test_r7_charts_identity.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T158 | [tests/test_r7_charts_identity.py:48](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_identity.py:48)<br>`test_missing_expected_ratio_points_to_the_compound_list_not_settings` | merge | `tests/test_identity_chart.py` | Move the missing-ratio input into `test_compound_with_no_expected_ratios_says_so_instead_of_a_grey_grid` and assert the actual displayed instruction. |
| T159 | [tests/test_r7_charts_identity.py:54](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_identity.py:54)<br>`test_missing_tolerance_alone_points_to_settings` | merge | `tests/test_identity_chart.py` | Move the missing-tolerance input into the same displayed-note table with a literal Settings destination. |
| T160 | [tests/test_r7_charts_identity.py:61](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_identity.py:61)<br>`test_one_missing_ratio_and_one_missing_tolerance_name_both_paths` | merge | `tests/test_identity_chart.py` | Move the combined-missing-fields input into the same displayed-note table, with a literal complete expected instruction. |
| T161 | [tests/test_r7_charts_identity.py:66](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_identity.py:66)<br>`test_a_checkable_qualifier_shows_the_grid_not_a_note` | delete | Remove test. | Confirmed false positive: this test passes when identity_unassessed_note always returns None. The configured-grid case belongs in the real popup test. |
| T162 | [tests/test_r7_charts_identity.py:70](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_identity.py:70)<br>`test_the_popup_chips_name_the_missing_tolerance` | merge | `tests/test_identity_chart.py` | Combine the missing-tolerance chip and popup note with `test_compound_with_no_expected_ratios_says_so_instead_of_a_grey_grid`. Do not compare to MISSING_TOLERANCE_STEP. |
| T163 | [tests/test_r7_charts_identity.py:79](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_identity.py:79)<br>`test_identity_scrolls_a_selected_row_below_the_fold_into_view` | keep | `tests/test_identity_chart.py` | Selecting Sample_25 moves its real marked row into the visible identity-chart viewport. |
| T164 | [tests/test_r7_charts_identity.py:98](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_identity.py:98)<br>`test_identity_shrinks_to_a_few_rows_in_a_short_sidebar_and_grows_with_room` | merge | `tests/test_identity_chart.py` | Add short/tall parent sizes to `test_sidebar_rows_keep_their_marks_and_names_and_scroll`. Drop arithmetic based on the same imported row-height constants. |

#### tests/test_r7_charts_summary.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T165 | [tests/test_r7_charts_summary.py:43](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_summary.py:43)<br>`test_value_axis_stays_in_view_while_rows_scroll` | keep | `tests/test_chart_summaries.py` | Scrolling actual summary rows leaves a nonempty pinned axis visible in the same coordinates. Assert literal tick strings for the supplied data. |
| T166 | [tests/test_r7_charts_summary.py:63](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_summary.py:63)<br>`test_two_summaries_share_a_short_sidebar_without_an_outer_scroll` | keep | `tests/test_chart_summaries.py` | Two real summary widgets fit together in a 360-pixel host while retaining usable inner rows. Use actual row visibility, not only minimumHeight totals. |
| T167 | [tests/test_r7_charts_summary.py:81](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_summary.py:81)<br>`test_selection_leaves_other_bars_their_cohort_colours` | keep | `tests/test_chart_summaries.py` | Selecting Bio_002 leaves the other actual ratio bars present and coloured, with one distinct selection marker. Inspect visible bars and literal selected sample. |
| T168 | [tests/test_r7_charts_summary.py:95](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_summary.py:95)<br>`test_a_sample_with_no_ratio_shows_a_dash_and_explains_on_hover` | keep | `tests/test_chart_summaries.py` | Hovering a real zero-ratio row shows the literal Bio_018 explanation and a dash. Inspect the drawn dash, not dash_rows/row_at return values. |

#### tests/test_r7_charts_tooltips.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T169 | [tests/test_r7_charts_tooltips.py:10](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_tooltips.py:10)<br>`test_caption_tooltip_appears_only_when_the_name_is_cut` | keep | `tests/test_plot_grid_ui.py` | A long real caption has no tooltip when it fits and the exact full-name tooltip when narrowed. |
| T170 | [tests/test_r7_charts_tooltips.py:27](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_tooltips.py:27)<br>`test_chip_tooltip_appears_only_when_the_label_is_cut` | keep | `tests/test_plot_grid_ui.py` | A real qualifier chip gains the exact full-label tooltip only when narrowed. |
| T171 | [tests/test_r7_charts_tooltips.py:41](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_charts_tooltips.py:41)<br>`test_badge_tooltips_add_only_what_the_badge_does_not_say` | delete | Remove test. | Only restates two production TileBadge tooltip constants and never creates or hovers a badge. |

#### tests/test_r7_dialogs_copy.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T172 | [tests/test_r7_dialogs_copy.py:16](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_dialogs_copy.py:16)<br>`test_checklist_tooltips_only_reveal_hidden_values` | keep | `tests/test_post_load_checklist.py` | A concrete report gives no redundant tooltip for short values and exact hidden filenames/pattern for truncated values. |
| T173 | [tests/test_r7_dialogs_copy.py:35](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_dialogs_copy.py:35)<br>`test_flagged_field_shows_its_error_instead_of_required` | merge | `tests/test_add_compound.py` | Fold placeholder/error transitions into `test_editing_one_field_clears_only_its_own_error`. Click Add and type into the field. |
| T174 | [tests/test_r7_dialogs_copy.py:52](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_dialogs_copy.py:52)<br>`test_export_asks_for_options_before_the_location` | keep | `tests/test_export_options.py` | The real export entry point opens options before the save picker, propagates the chosen option, and cancellation never opens the picker. Keep this UI ordering only. |
| T175 | [tests/test_r7_dialogs_copy.py:87](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_dialogs_copy.py:87)<br>`test_unlabelled_export_has_no_carbon_sheet_option` | keep | `tests/test_export_options.py` | The actual unlabelled export dialog offers no carbon-sheet control and returns False. Pair with a labelled case offering the control; do not change any exporter or value. |
| T176 | [tests/test_r7_dialogs_copy.py:102](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_dialogs_copy.py:102)<br>`test_path_tooltip_only_when_the_path_does_not_fit` | keep | `tests/test_process_external_data.py` | A real tooltip event shows the exact long selected path but no tooltip for /a.csv. |

#### tests/test_r7_dialogs_settings.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T177 | [tests/test_r7_dialogs_settings.py:44](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_dialogs_settings.py:44)<br>`test_a_selected_sample_with_an_override_has_one_fit_editor` | merge | `tests/test_settings_window.py` | The selected-override row/save assertions overlap `test_deconvolution_page_saves_per_sample_override_and_clear`. Retain its distinct mixed-existing-override setup as a table input. |
| T178 | [tests/test_r7_dialogs_settings.py:75](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_dialogs_settings.py:75)<br>`test_bulk_fit_follows_the_rows_the_user_selects` | keep | `tests/test_settings_window.py` | Selecting row S3 and clearing through the bulk fit command preserves the exact S1/S2 overrides after Save. Click the actual bulk-menu action. |
| T179 | [tests/test_r7_dialogs_settings.py:96](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_dialogs_settings.py:96)<br>`test_internal_standard_page_chooses_the_standard_and_its_reference_peak` | keep | `tests/test_settings_window.py` | Choosing Norvaline and M+2 then Save updates exactly that standard/reference; choosing None clears it. Exercise only settings wiring. |
| T180 | [tests/test_r7_dialogs_settings.py:125](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_dialogs_settings.py:125)<br>`test_unsaved_banner_lists_only_other_pages` | merge | `tests/test_settings_window.py` | `test_unsaved_pages_stay_marked_after_switching_away` already covers the other-page pending banner and links. |

#### tests/test_r7_shell_menus.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T181 | [tests/test_r7_shell_menus.py:13](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_shell_menus.py:13)<br>`test_show_all_samples_is_listed_once_in_the_menu_bar` | merge | `tests/test_sidebar.py` | Keep one Show All menu entry alongside `test_focus_selected_then_show_all` and its actual recovery result. Do not keep a standalone location/copy test. |
| T182 | [tests/test_r7_shell_menus.py:25](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_shell_menus.py:25)<br>`test_internal_standard_menu_ticks_with_the_app_checkmark_in_text_colour` | delete | Remove test. | Reads a temporary SVG file and compares its fill attribute with the current token. This pins the icon-generation implementation, not a visible checked menu result. |

#### tests/test_r7_shell_sidebar.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T183 | [tests/test_r7_shell_sidebar.py:34](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_shell_sidebar.py:34)<br>`test_section_summary_shows_only_while_the_section_is_closed` | merge | `tests/test_sidebar.py` | Fold visible closed-only summaries into `test_sections_collapse_and_remember` with literal Baseline/Own scale values. |
| T184 | [tests/test_r7_shell_sidebar.py:58](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_shell_sidebar.py:58)<br>`test_reset_and_apply_are_never_cut_on_a_short_sidebar` | keep | `tests/test_sidebar.py` | At both short heights, scrolling keeps the actual Reset and Apply controls wholly visible until their fields scroll away. Drop private _slot identity assertions. |

#### tests/test_r7_shell_start.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T185 | [tests/test_r7_shell_start.py:27](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_shell_start.py:27)<br>`test_clear_recent_empties_the_start_panel_at_once` | keep | `tests/test_start_panel.py` | Triggering Clear Recent removes the literal compounds.xlsx row immediately and hides Recent. |
| T186 | [tests/test_r7_shell_start.py:48](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_r7_shell_start.py:48)<br>`test_long_recent_folder_elides_in_the_middle_and_explains_on_hover` | keep | `tests/test_start_panel.py` | A real long recent path visibly preserves root/final folder and exposes the exact full path on hover; a short path has no redundant tooltip. |

#### tests/test_recovery_dialog.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T187 | [tests/test_recovery_dialog.py:6](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_recovery_dialog.py:6)<br>`test_compound_recovery_restores_selected_names` | keep | `tests/test_recovery_dialog.py` | Select Malate and click Restore; exactly Malate reaches restoration and the emitted event, and the dialog accepts. |
| T188 | [tests/test_recovery_dialog.py:32](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_recovery_dialog.py:32)<br>`test_sample_recovery_shows_empty_state` | keep | `tests/test_recovery_dialog.py` | No deleted samples yields literal No deleted samples and exactly one visible Close action. |

#### tests/test_sample_list_context_menu.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T189 | [tests/test_sample_list_context_menu.py:7](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_sample_list_context_menu.py:7)<br>`test_context_menu_names_the_highlighted_samples` | merge | `tests/test_sidebar.py` | Fold multi-row menu labels into `test_sample_checkboxes_keep_list_order_and_count_matches`, then trigger Hide/Show Only and assert exact shown names. Drop the direct private selection-helper assertion. |

#### tests/test_settings_window.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T190 | [tests/test_settings_window.py:67](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_settings_window.py:67)<br>`test_labelled_settings_open_with_no_data` | keep | `tests/test_settings_window.py` | Opening Settings with no data leaves global controls enabled and compound/standard controls disabled, with literal setup guidance. |
| T191 | [tests/test_settings_window.py:129](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_settings_window.py:129)<br>`test_qualifier_ratios_not_editable_without_a_selected_compound` | keep | `tests/test_settings_window.py` | Opening unlabelled Qualifier Ratios without a compound disables the actual inputs and shows literal guidance. Drop the duplicate editable tuple assertion. |
| T192 | [tests/test_settings_window.py:227](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_settings_window.py:227)<br>`test_unsaved_pages_stay_marked_after_switching_away` | keep | `tests/test_settings_window.py` | Staged Mass Tolerance and Peak Validation stay visibly marked across page switches, and Save/Reset affect only their own staged page. |
| T193 | [tests/test_settings_window.py:330](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_settings_window.py:330)<br>`test_internal_standard_without_label_atoms_disables_combo` | merge | `tests/test_settings_window.py` | Add a zero-label-atoms standard input to `test_internal_standard_page_chooses_the_standard_and_its_reference_peak`. |
| T194 | [tests/test_settings_window.py:372](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_settings_window.py:372)<br>`test_deconvolution_page_saves_per_sample_override_and_clear` | keep | `tests/test_settings_window.py` | Real table edits, Save, and Remove All produce exact per-sample override maps and replot counts. Absorb the mixed existing-override case; invoke menu actions instead of helper methods. |
| T195 | [tests/test_settings_window.py:435](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_settings_window.py:435)<br>`test_deconvolution_without_overrides_or_selection_shows_empty_state` | keep | `tests/test_settings_window.py` | With a real compound but no selection/overrides, the table and bulk controls disappear and the actual empty-state message is visible. |
| T196 | [tests/test_settings_window.py:454](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_settings_window.py:454)<br>`test_settings_window_opens_centred_on_a_visible_main_window` | keep | `tests/test_settings_window.py` | Showing Settings on a visible parent keeps it on screen and centred within tolerance. Retain geometry; no style changes. |

#### tests/test_sidebar.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T197 | [tests/test_sidebar.py:25](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_sidebar.py:25)<br>`test_internal_standard_row_is_optional_until_chosen` | keep | `tests/test_sidebar.py` | The actual standard row transitions None to Norvaline to None with the literal displayed values and optional/done states. Read the displayed QLabel, not value_text. |
| T198 | [tests/test_sidebar.py:41](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_sidebar.py:41)<br>`test_data_rows_report_load_state_without_counts_or_links` | keep | `tests/test_sidebar.py` | Actual load-status rows display Not loaded until the corresponding data is loaded, then show completion. Drop private _state-only assertions. |
| T199 | [tests/test_sidebar.py:57](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_sidebar.py:57)<br>`test_compound_filter_narrows_list_and_enter_picks_first_match` | keep | `tests/test_sidebar.py` | Typing gl and pressing Return chooses Glutamate; subsequent navigation yields the exact Glycine/Glutamate sequence. |
| T200 | [tests/test_sidebar.py:88](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_sidebar.py:88)<br>`test_sample_header_counts_shown_samples` | merge | `tests/test_sidebar.py` | `test_sample_checkboxes_keep_list_order_and_count_matches` already checks literal all/partial counts and real shown-name changes. |
| T201 | [tests/test_sidebar.py:100](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_sidebar.py:100)<br>`test_inspector_waits_for_raw_data` | keep | `tests/test_sidebar.py` | The actual inspector appears only after raw data becomes available, with a positive and negative state. |

#### tests/test_ui_formatting.py

| ID | Test | Verdict | Destination | Reason / retained contract |
| --- | --- | --- | --- | --- |
| T202 | [tests/test_ui_formatting.py:265](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_ui_formatting.py:265)<br>`test_targeted_qc_identity_chart_renders_grid_cells` | merge | `tests/test_identity_chart.py` | Combine the literal S1/S2 statuses, ordering, and absent outline with `test_every_identity_cell_carries_a_visible_state_mark`. Drop bar-set arrays and class-layout internals. |
| T203 | [tests/test_ui_formatting.py:373](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_ui_formatting.py:373)<br>`test_identity_chart_popup_shows_sample_names` | merge | `tests/test_identity_chart.py` | Combine popup sample names and qualifier headers into that same rendered identity case. Drop literal font, HTML structure, and child binding counts. |
| T204 | [tests/test_ui_formatting.py:1182](/Users/couttsj/Documents/_code/pythonMANIC/tests/test_ui_formatting.py:1182)<br>`test_detailed_eic_info_strip_reports_failure_when_plot_never_draws` | keep | `tests/test_detailed_plot_dialog.py` | A failed EIC draw displays the literal failure cause in the footer and plot. Preserve error presentation without changing drawing/calculation code. |

### Replaced and already deleted tests

| Old source | Old name | Disposition |
| --- | --- | --- |
| `tests/test_add_compound.py:267 at origin/main` | `test_invalid_ok_keeps_dialog_open_and_warns` | Renamed and rewritten as `test_invalid_ok_keeps_dialog_open_and_flags_the_field`. |
| `tests/test_peak_review_menu.py:78 at origin/main` | `test_toggling_checked_bad_clears_the_review` | Renamed and rewritten as `test_clear_bad_mark_clears_the_review`. |
| `tests/test_post_load_checklist.py:52 at origin/main` | `test_dialog_status_label_updates_when_combo_changes` | Renamed and rewritten as `test_unchanged_checklist_offers_one_continue`. |
| `tests/test_post_load_checklist.py:109 at origin/main` | `test_skip_leaves_internal_standard_unchanged` | Renamed as `test_continue_without_changes_leaves_internal_standard_unchanged`. |
| `tests/test_toolbar_pills.py:8 at origin/main` | `test_standard_pill_prefixes_the_name` | Keep deleted. Current standard-row behaviour is covered by `test_internal_standard_row_is_optional_until_chosen`. |
| `tests/test_toolbar_pills.py:23 at origin/main` | `test_compound_pill_is_blue_when_set_and_grey_when_empty` | Keep deleted. Old CompoundIndicator colour/copy constants no longer define the UI. |
| `tests/test_toolbar_pills.py:33 at origin/main` | `test_long_names_are_elided_to_the_pill_width_with_full_text_in_tooltip` | Keep deleted. Current caption/recent-path elision is covered by retained real-widget tests. |

## Comments

| ID | Evidence | Problem | Cleanup |
| --- | --- | --- | --- |
| C01 | [src/manic/ui/channel_chips.py:65](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/channel_chips.py:65) | The full label on hover only when the chip is too narrow narrates the setToolTip condition immediately below. | Delete the comment. Keep the hover behaviour. |
| C02 | [src/manic/ui/documentation_viewer.py:124](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/documentation_viewer.py:124)<br>[src/manic/ui/documentation_viewer.py:137](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/documentation_viewer.py:137) | The viewer advertises perfect GitHub rendering/GitHub-identical CSS and lists its features; the constructor docstring repeats its signature. | Replace with the actual responsibility in one sentence. The viewer has its own themed stylesheet, not an identity guarantee with GitHub. |
| C03 | [src/manic/ui/graphs.py:109](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:109)<br>[src/manic/ui/graphs.py:110](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:110)<br>[src/manic/ui/graphs.py:139](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:139)<br>[src/manic/ui/graphs.py:147](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:147) | Signal to emit when clicked/right-clicked and Handle mouse clicks/release restate names and signatures. | Delete narration. Keep the non-obvious double-click release suppression explanation at :133. |
| C04 | [src/manic/ui/graphs.py:1315](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1315)<br>[src/manic/ui/graphs.py:1349](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1349)<br>[src/manic/ui/graphs.py:1400](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1400)<br>[src/manic/ui/graphs.py:1474](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1474) | Long repeated Args/Returns prose explains that container creation creates containers and updating updates data; atomic/efficient claims add no invariant. | Keep a short ownership/lifetime explanation where needed. Drop duplicate parameter descriptions and unsupported atomicity/performance claims. |
| C05 | [src/manic/ui/graphs.py:1332](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1332)<br>[src/manic/ui/graphs.py:1334](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1334)<br>[src/manic/ui/graphs.py:1442](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1442)<br>[src/manic/ui/graphs.py:1471](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1471) | Stale comments say _update_container_data handles visibility and shows the container; its finally now says layout owns visibility and only passes. | Delete the false show/visibility claims. Document ownership once at the real layout placement if the code does not make it clear. |
| C06 | [src/manic/ui/graphs.py:1607](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:1607)<br>[src/manic/ui/plot_tile.py:198](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/plot_tile.py:198) | The caption-below docstring describes the old layout. PlotTile adds the caption header and badges before the chart. | It disappears with N05. Do not count its lines again in comment savings. |
| C07 | [src/manic/ui/graphs.py:2160](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:2160)<br>[src/manic/ui/graphs.py:2162](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:2162)<br>[src/manic/ui/graphs.py:2165](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:2165)<br>[src/manic/ui/graphs.py:2170](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:2170)<br>[src/manic/ui/graphs.py:2174](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/graphs.py:2174) | Complete destruction mode, First clear, Remove and delete ALL widgets, and Clear the container pool repeat each following operation. | Delete these headings/narration. Retain the Qt layout-lifetime explanation at :2202 and the pooled reparenting/repolish rationale. |
| C08 | [src/manic/ui/main_window.py:10](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/main_window.py:10)<br>[src/manic/ui/main_window.py:1462](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/main_window.py:1462) | Add this for opening URLs is an editing instruction left on an import. on_compound_selected documents selected_text although its argument is compound_selected. | Remove the editing note and stale redundant parameter prose. Keep the compound-selection behaviour. |
| C09 | [src/manic/ui/matplotlib_plot_widget.py:1](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/matplotlib_plot_widget.py:1)<br>[src/manic/ui/matplotlib_plot_widget.py:61](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/matplotlib_plot_widget.py:61)<br>[src/manic/ui/matplotlib_plot_widget.py:237](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/matplotlib_plot_widget.py:237) | High-performance/professional/optimized lists and rendering-parameter comments claim quality instead of explaining a constraint. | Trim promotional module/class prose and comments that restate assignments. Keep point-to-pixel conversion and label-box/theme explanations. |
| C10 | [src/manic/ui/total_abundance_widget.py:62](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/total_abundance_widget.py:62)<br>[src/manic/ui/total_abundance_widget.py:99](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/total_abundance_widget.py:99)<br>[src/manic/ui/total_abundance_widget.py:129](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/total_abundance_widget.py:129)<br>[src/manic/ui/total_abundance_widget.py:135](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/total_abundance_widget.py:135)<br>[src/manic/ui/isotopologue_ratio_widget.py:129](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/isotopologue_ratio_widget.py:129)<br>[src/manic/ui/isotopologue_ratio_widget.py:182](/Users/couttsj/Documents/_code/pythonMANIC/src/manic/ui/isotopologue_ratio_widget.py:182) | Create chart and chart view, Data storage, Flip array, and Update chart narrate the adjacent code. | Remove these narrating comments and repeated type/argument prose. Keep the reasons for reversed copies, selected-row bands, and pinned axes. |

No inline review-round or ticket annotation was confirmed in the scoped UI/script changes. The concrete round residue is the 41 test filenames and the cross-round import in test_r3_integrate_review_menus.py:5. The feature layout below removes that history from ownership. Do not delete useful explanations about Qt deferred deletion, WebEngine startup, headless scheme fallback, middle elision, pinned axes, or retaining caller array order. The changed science documentation is not part of this cleanup.

## Proposed test layout

The destination column above maps every retained case. The IDs below are an additional checklist of all 120 retained functions and the 65 cases folded into them. Move only the reviewed tests out of mixed existing files such as test_ui_formatting.py; leave its other regressions intact. Keep the existing source-test names until a rename improves what the test actually does, then remove all round prefixes.

| Destination | Kept functions | Kept test IDs | Cases merged here |
| --- | --- | --- | --- |
| `tests/test_add_compound.py` | 9 | T002, T005, T053, T054, T055, T056, T057, T058, T059 | T001, T003, T004, T173 |
| `tests/test_app_stylesheet.py` | 3 | T006, T007, T099 | T096, T097, T098 |
| `tests/test_chart_popups.py` | 6 | T085, T086, T130, T131, T133, T134 | T049, T050, T087, T135 |
| `tests/test_chart_summaries.py` | 8 | T066, T110, T145, T147, T165, T166, T167, T168 | T030, T111, T146 |
| `tests/test_detailed_plot_dialog.py` | 7 | T039, T076, T077, T092, T093, T122, T204 | T041, T042, T123 |
| `tests/test_documentation_viewer.py` | 3 | T009, T155, T156 | T157 |
| `tests/test_export_options.py` | 2 | T174, T175 | None |
| `tests/test_identity_chart.py` | 9 | T079, T080, T083, T124, T126, T127, T128, T129, T163 | T052, T081, T125, T158, T159, T160, T162, T164, T202, T203 |
| `tests/test_integration_window.py` | 1 | T148 | None |
| `tests/test_main_window_shell.py` | 4 | T011, T012, T014, T068 | T008, T013 |
| `tests/test_peak_review_menu.py` | 10 | T015, T016, T017, T018, T019, T022, T024, T067, T112, T113 | T021, T023, T026, T045, T046, T065, T089, T090, T091, T117, T119, T149 |
| `tests/test_plot_grid_ui.py` | 15 | T027, T028, T031, T032, T033, T034, T044, T047, T048, T082, T084, T114, T115, T169, T170 | T020, T029, T043, T116, T120, T150, T151 |
| `tests/test_post_load_checklist.py` | 8 | T035, T036, T037, T038, T094, T136, T137, T172 | T138, T139 |
| `tests/test_process_external_data.py` | 1 | T176 | None |
| `tests/test_recovery_dialog.py` | 2 | T187, T188 | None |
| `tests/test_settings_window.py` | 8 | T178, T179, T190, T191, T192, T194, T195, T196 | T064, T177, T180, T193 |
| `tests/test_sidebar.py` | 22 | T010, T069, T070, T071, T072, T074, T075, T100, T102, T103, T105, T106, T109, T140, T141, T142, T144, T184, T197, T198, T199, T201 | T025, T073, T101, T104, T107, T143, T181, T183, T189, T200 |
| `tests/test_start_panel.py` | 2 | T185, T186 | None |

Use one function-scoped settings fixture, one real grid fixture, one populated sidebar fixture, and one spectrum-data fixture where their inputs actually match. Put them in the existing tests/conftest.py. Do not create a parallel UI-test framework or import one test module from another. Keep expected literal results in the tests rather than deriving them from shared production constants.

The two grid-layout functions already assert exact public helper outputs. Keep those small boundary cases; merge the round-specific density vectors into the same table. Use the existing real-grid fixture for event, selection, scrolling, and rendered-card checks. There is no need for a second helper-only suite.

## Verification and limits

Inspected the branch diff, AST inventories, callers, runtime signal ownership, stylesheet assignments, and every test body listed above. An AST comparison against origin/main found all 200 directly added/changed functions. Dependency review added test_app_stylesheet.py:18, test_post_load_checklist.py:69, and test_peak_review_menu.py:153,173. Four renamed predecessors and the deleted pill file were checked against the base revision.

The following focused run passed 40 expanded cases with two existing Pydantic deprecation warnings. It ran offscreen, disabled bytecode/cache writes, and did not edit the code.

`env PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -p no:cacheprovider -q tests/test_r7_charts_identity.py tests/test_r7_charts_tooltips.py tests/test_r3_dialogs_settings.py tests/test_r3_charts_popups.py tests/test_r5_shell_contrast.py tests/test_recovery_dialog.py tests/test_plot_grid_ui.py`

For test_r7_charts_identity.py:66, a separate process replaced only the imported identity_unassessed_note reference with a lambda returning None, then called the test body. It still passed. This confirms T161 is a false-positive test rather than merely a suspected weak assertion. No source file was changed.

For U01, a separate offscreen Qt process created the real styled Settings sidebar, captured its pixels/item rectangles, removed just the three app-wide sidebar-list QSS blocks from the in-memory stylesheet, and captured it again. The pixel hashes and item rectangles matched. This checks that one concrete case; it does not claim cross-platform visual equivalence for a cleanup that has not been implemented.

The full scientific suite and the complete UI tour were not rerun. No cleanup was implemented, so this is a cited deletion/consolidation plan, not a claim that the proposed refactor is already verified. During cleanup, the real UI tour should retain all current states and image comparisons, including screenshots of short/tall windows and live scheme changes. The tour script itself earns its place; its comparison and headless/Qt timing accommodations have a stated purpose.

Minimize reader load led to removing forwarding/no-op layers and choosing existing owners. Test behavior, not implementation led to the per-test payload/output decisions. Prove it works required committed caller searches, the focused run, the no-op test probe, and a real rendered-style comparison. Work ran in this review agent as requested; no delegates.

## Estimated net lines removed

The source spans of the 19 delete verdicts contain 182 lines. The 65 merge verdicts contain 829 lines before decorators and shared setup. Those 829 lines are not all deletions: retain their distinct input cases and useful assertions inside the 120 kept scenarios.

| Work | Estimated net lines removed | Basis |
| --- | --- | --- |
| Dead code and fixed/no-op layers | 220 to 300 | Lone-declaration blocks, write-only fields/imports, two identity helpers, the no-op, and unused parameter branches. |
| Duplicate drawing/style/label paths and connection churn | 100 to 200 | After retaining one implementation and preserving current inputs and pixels. |
| Test deletion and consolidation | 1,000 to 1,300 | 182 directly deleted body lines, overlap within 829 merged body lines, plus repeated imports/fixtures across 41 round-named files. Allows room to drive existing cases through actual widgets. |
| Comment cleanup beyond already removed blocks | 80 to 140 | Repeated constructor/container Args/Returns prose and operation narration. Excludes comments already counted inside deleted functions. |
| Planning total | about 1,400 to 2,000; central estimate 1,700 | Estimate, not a measured patch. No dependency or user-capability removal. |

Apply the file-ordered dead-code table first, then consolidate repeated production paths with the matching retained interaction tests. Move tests into the feature files and fold the specified cases; do not add replacements alongside the old tests. Finish with comment removal and the existing UI tour. Preserve every science regression, input, calculation, and exported value.
