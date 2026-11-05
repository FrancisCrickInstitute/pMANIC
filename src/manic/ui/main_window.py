import logging
import os
from pathlib import Path

import numpy as np

from PySide6.QtCore import QCoreApplication, QPoint, QSettings, Qt, QThread, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QDesktopServices,
    QIcon,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from manic.__version__ import APP_NAME
from manic.constants import (
    DEFAULT_MIN_PEAK_HEIGHT_RATIO,
    DEFAULT_RT_WINDOW,
    minimum_extract_rt_window,
)
from manic.io.compounds_import import (
    UnlabelledCompoundRecord,
    detect_compound_list_format,
    import_compound_excel,
    insert_compound,
    insert_unlabelled_compound,
    taken_compound_names,
)
from manic.io.data_exporter import DataExporter, validate_internal_standard_metadata
from manic.io.data_provider import DataProvider
from manic.io.list_compound_names import list_compound_names
from manic.io.sample_reader import list_active_samples
from manic.io.compound_reader import (
    list_compound_mm_files,
    read_compound,
    read_compound_with_session,
)
from manic.models.analysis import AnalysisContext, AnalysisMode, IonChannel, IonRole
from manic.models.mm_file_check import build_mm_file_report
from manic.models.session_export import (
    InternalStandardRestore,
    InternalStandardRestoreKind,
    clamp_reference_isotope,
    export_session_method,
    format_session_import_standard_note,
    get_method_info,
    import_session_overrides,
    read_session_internal_standard,
    resolve_session_internal_standard,
    validate_method_file,
)
from manic.processors.chromatographic_peak_deconvolution import (
    DEFAULT_DECONVOLUTION_LEVEL,
    normalize_fit_type,
    normalize_noise_gate,
    normalize_stringency,
)
from manic.processors.integration import calculate_peak_areas
from manic.models.database import clear_database, get_connection
from manic.models.peak_review import get_peak_reviews, set_peak_review
from manic.models.sample_fit_type import set_sample_fit_type
from manic.validation.peak_verdict import PeakReview, PeakVerdict
from manic.ui.documentation_viewer import DocumentationViewer
from manic.ui.graphs import GraphView
from manic.ui.left_toolbar import Toolbar
from manic.ui.post_load_checklist_dialog import PostLoadChecklistDialog
from manic.ui.export_options_dialog import ExportOptionsDialog
from manic.ui.settings_window import SettingsWindow
from manic.ui.standard_indicator_widget import lacking_amount
from manic.ui.start_panel import StartPanel
from manic.ui.theme import set_style_property
from manic.ui.toast_notification import show_status_toast
from manic.ui.window_placement import show_over_parent
from manic.ui.summary_panel import SUMMARY_MIN_WIDTH, SUMMARY_WIDTH, SummaryPanel
from manic.ui.total_abundance_widget import abundances_from_provider
from manic.utils.paths import docs_path, resource_path
from manic.utils.recent_files import RecentFiles
from manic.utils.workers import (
    CdfImportWorker,
    EicRegenerationWorker,
    ExportWorker,
    MassToleranceReloadWorker,
    UpdateCheckWorker,
)
from manic.utils.timer import measure_time

logger = logging.getLogger("manic_logger")


def _eics(count: int) -> str:
    return f"{count} EIC" if count == 1 else f"{count} EICs"

SIDEBAR_WIDTH = 296
SUMMARY_OPEN_SETTING = "view/summary_open"
SUMMARY_WIDTH_SETTING = "view/summary_width"
# Until the user opens or closes it, the Summary starts closed in a narrower window,
# so the grid keeps its columns.
SUMMARY_MIN_WINDOW_WIDTH = 1200
COMPOUND_LIST_SUFFIXES = {".csv", ".xls", ".xlsx"}


class MainWindow(QMainWindow):
    def __init__(self, analysis_context: AnalysisContext | None = None):
        super().__init__()
        self.analysis_context = analysis_context or AnalysisContext()
        self.analysis_mode = self.analysis_context.mode
        self.setWindowTitle(
            f"{APP_NAME} — {self.analysis_mode.display_name} analysis"
        )
        self.setAcceptDrops(True)
        self.setObjectName("mainWindow")

        # Flag to prevent cascading compound deletion events
        self._deleting_compound = False

        # Flag to prevent cascading sample deletion events
        self._deleting_samples = False


        # Set window icon
        self._set_window_icon()
        self.progress_bar = QProgressBar()

        # Menu actions
        self.load_cdf_action = None
        self.load_compound_action = None
        self.export_method_action = None
        self.export_data_action = None
        self.import_session_action = None
        self.clear_session_action = None
        self.about_action = None

        # State tracking for menu management

        # Mass tolerance setting (default 0.2 Da)
        self.mass_tolerance = 0.2

        # Minimum peak area ratio setting (fraction of internal std reference peak)
        self.min_peak_height_ratio = DEFAULT_MIN_PEAK_HEIGHT_RATIO

        # Labelled internal standard setting: which isotopologue peak (M+N) is used
        # as the internal standard "reference peak" across validation + abundance + MRRF.
        # Resets to 0 (M0) whenever internal standard changes.
        self.internal_standard_reference_isotope = 0

        # Integration method setting
        self.use_legacy_integration = False  # Time-based by default
        self.preview_nat_abundance = False
        self.settings_window = None
        self.documentation_window = None
        self._post_load_checklist = None
        self.compound_list_path: str | None = None
        self._update_worker = None
        self.compound_data_loaded = False
        self.cdf_data_loaded = False
        self._thread = None
        self._export_thread = None
        self._export_worker = None
        self._export_progress_dialog = None
        self._skip_close_guard = False
        self._recent_compounds = RecentFiles("compound_lists")
        self._recent_cdf = RecentFiles("cdf_folders")

        # Cached DataProvider for validation (reused to avoid repeated bulk loads)
        self._validation_provider = None

        self.setup_ui()

        # Connect toolbar signals (avoid duplicate connections; others are set in setup_ui)
        self.toolbar.internal_standard_selected.connect(
            self.on_internal_standard_selected
        )
        self.graph_view.settings_requested.connect(self.open_settings_window)
        self.graph_view.documentation_requested.connect(self.open_documentation_window)
        self.graph_view.guide_requested.connect(self.open_documentation_link)
        self.summary.targeted_qc.guide_requested.connect(self.open_documentation_link)
        self.toolbar.compounds_deleted.connect(self.on_compounds_deleted)
        self.toolbar.compounds_restored.connect(self.on_compounds_restored)
        self.toolbar.add_compound_requested.connect(self.show_add_compound_dialog)
        self.toolbar.samples_deleted.connect(self.on_samples_deleted)
        self.toolbar.samples_restored.connect(self.on_samples_restored)

        # Start update check in background
        self._check_for_updates()

    def _check_for_updates(self):
        """Start the background update checker unless one is already running."""
        if self._update_worker is not None and self._update_worker.isRunning():
            return
        self._update_worker = UpdateCheckWorker()
        self._update_worker.result.connect(self._on_update_check_finished)
        self._update_worker.start()

    def _on_update_check_finished(
        self, success: bool, has_update: bool, latest_version: str, url: str
    ):
        """Handle the result of the update check."""
        self._show_update_check_toast(success, has_update, latest_version)

        if has_update and self._confirm(
            "New Version Available",
            f"MANIC v{latest_version} is available.",
            "",
            "View Release Page",
        ):
            QDesktopServices.openUrl(QUrl(url))

    def _show_update_check_toast(
        self,
        success: bool,
        has_update: bool,
        latest_version: str,
    ) -> None:
        if not success:
            message = "Update check failed"
        elif has_update:
            message = f"Update available (v{latest_version})"
        else:
            message = "No updates available"

        show_status_toast(self.statusBar(), message)

    def setup_ui(self):
        """
        Set up the application UI.
        """

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        self.toolbar = Toolbar(self.analysis_mode)
        self.toolbar.setObjectName("toolbar")
        splitter.addWidget(self.toolbar)

        # The grid replaces the start panel once raw data is loaded.
        self.graph_view = GraphView()
        self.start_panel = StartPanel()
        self.workspace = QStackedWidget()
        self.workspace.setObjectName("workspace")
        self.no_samples_panel = self._build_no_samples_panel()
        self.workspace.addWidget(self.start_panel)
        self.workspace.addWidget(self.graph_view)
        self.workspace.addWidget(self.no_samples_panel)
        splitter.addWidget(self.workspace)
        self.summary = SummaryPanel(self.analysis_mode)
        splitter.addWidget(self.summary)
        self.summary.hide()
        # Decided when the grid first shows, from the window's width then.
        self._summary_settled = False

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        for index in range(3):
            splitter.setCollapsible(index, False)
        splitter.setSizes([SIDEBAR_WIDTH, 10_000, 0])
        splitter.splitterMoved.connect(self._remember_summary_width)
        self.splitter = splitter
        main_layout.addWidget(splitter)

        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        self._setup_status_bar()

        # Create menu bar
        menu_bar = QMenuBar()

        """ Create File Menu """

        # Initiate the file menu
        file_menu = menu_bar.addMenu("File")
        self.file_menu = file_menu
        # Windows draws menu tooltips only when asked; a disabled action's says what it needs.
        file_menu.setToolTipsVisible(True)

        # Create the actions/logic for loading compound list data
        self.load_compound_action = QAction("Load Compounds/Parameter List", self)
        self.load_compound_action.setShortcut(QKeySequence.Open)
        self.load_compound_action.triggered.connect(self.load_compound_list_data)
        # Add the load compound action/logic to the file menu
        file_menu.addAction(self.load_compound_action)

        self.add_compound_action = QAction("Add Compound...", self)
        self.add_compound_action.triggered.connect(self.show_add_compound_dialog)
        file_menu.addAction(self.add_compound_action)

        # Create the actions/logic for loading CDF files
        self.load_cdf_action = QAction("Load Raw Data (CDF)", self)
        self.load_cdf_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.load_cdf_action.triggered.connect(self.load_cdf_files)
        # Add the load CDF action/logic to the file menu
        file_menu.addAction(self.load_cdf_action)

        self.open_recent_menu = file_menu.addMenu("Open Recent")
        self.open_recent_menu.setToolTipsVisible(True)
        self.open_recent_menu.aboutToShow.connect(self._rebuild_open_recent_menu)
        self._rebuild_open_recent_menu()

        # Add a separator to the file menu
        file_menu.addSeparator()

        # Create method export/import actions
        self.export_method_action = QAction("Export Session...", self)
        self.export_method_action.triggered.connect(self.export_method)
        file_menu.addAction(self.export_method_action)

        self.import_session_action = QAction("Import Session...", self)
        self.import_session_action.setShortcut(QKeySequence("Ctrl+I"))
        self.import_session_action.triggered.connect(self.import_session)
        file_menu.addAction(self.import_session_action)

        self.new_session_action = QAction("New Analysis Session...", self)
        self.new_session_action.triggered.connect(self.new_analysis_session)
        file_menu.addAction(self.new_session_action)

        # Create the Clear Session action
        self.clear_session_action = QAction("Clear Session", self)
        self.clear_session_action.triggered.connect(self.clear_session)
        # Add the clear session action to the file menu
        file_menu.addAction(self.clear_session_action)

        # Add separator before export data
        file_menu.addSeparator()

        # Create export data action
        self.export_data_action = QAction("Export Data...", self)
        self.export_data_action.setShortcut(QKeySequence("Ctrl+E"))
        self.export_data_action.triggered.connect(self.export_data)
        file_menu.addAction(self.export_data_action)

        # Add separator and Update Old Data action
        file_menu.addSeparator()
        self.update_old_data_action = QAction("Process External Data...", self)
        self.update_old_data_action.triggered.connect(self.update_old_data)
        file_menu.addAction(self.update_old_data_action)

        file_menu.addSeparator()
        # Settings sits in File where Windows and Linux users look for it. Its role
        # moves it to the application menu on macOS, which relabels it Preferences.
        self.settings_action = QAction("Settings...", self)
        self.settings_action.setMenuRole(QAction.PreferencesRole)
        self.settings_action.setShortcuts(
            [QKeySequence.Preferences, QKeySequence("Ctrl+,")]
        )
        self.settings_action.triggered.connect(self.open_settings_window)
        file_menu.addAction(self.settings_action)

        self.quit_action = QAction("Quit", self)
        # QKeySequence.Quit has no Windows entry in Qt's standard-key table
        # (KB_X11 | KB_Gnome | KB_KDE | KB_Mac), so on its own it would leave
        # Windows with no shortcut at all. Pair it with the literal, as
        # Settings does for QKeySequence.Preferences. On macOS both resolve to
        # Cmd+Q and the duplicate is harmless.
        self.quit_action.setShortcuts([QKeySequence.Quit, QKeySequence("Ctrl+Q")])
        self.quit_action.setMenuRole(QAction.QuitRole)
        self.quit_action.triggered.connect(self.close)
        file_menu.addAction(self.quit_action)

        self._build_view_menu(menu_bar)
        self._build_review_menu(menu_bar)

        # About carries a role so a native macOS menubar moves it into the
        # application menu. Documentation and Check for Updates stay put; giving
        # them ApplicationSpecificRole made Qt list them twice.
        self.help_menu = help_menu = menu_bar.addMenu("Help")

        self.documentation_action = QAction("Documentation", self)
        self.documentation_action.setMenuRole(QAction.NoRole)
        self.documentation_action.setShortcut(QKeySequence.HelpContents)
        self.documentation_action.triggered.connect(self.open_documentation_window)
        help_menu.addAction(self.documentation_action)

        self.check_setup_action = QAction("Check Data Setup...", self)
        self.check_setup_action.setMenuRole(QAction.NoRole)
        self.check_setup_action.triggered.connect(self.show_post_load_checklist)
        help_menu.addAction(self.check_setup_action)

        self.check_updates_action = QAction("Check for Updates...", self)
        self.check_updates_action.setMenuRole(QAction.NoRole)
        self.check_updates_action.triggered.connect(self._check_for_updates)
        help_menu.addAction(self.check_updates_action)

        help_menu.addSeparator()
        self.about_action = QAction("About MANIC...", self)
        self.about_action.setMenuRole(QAction.AboutRole)
        self.about_action.triggered.connect(self.show_about)
        help_menu.addAction(self.about_action)

        # Set the menu bar to the QMainWindow
        self.setMenuBar(menu_bar)

        # Initialize menu states
        self._update_menu_states()

        # Initialize natural abundance correction state
        if self.analysis_mode is AnalysisMode.LABELLED:
            self.summary.isotopologue_ratios.set_use_corrected(False)  # Off by default
        self.update_deconvolution_indicator(None)

        # Connect the toolbar's custom signals to handler methods
        self.toolbar.samples_selected.connect(self.on_samples_selected)
        self.toolbar.compound_selected.connect(self.on_compound_selected)

        # Connect the graph view's selection signal
        self.graph_view.selection_changed.connect(self.on_plot_selection_changed)
        self.graph_view.peak_review_changed.connect(self.on_peak_review_changed)
        self.graph_view.sample_fit_type_changed.connect(
            self.on_sample_fit_type_changed
        )
        self.graph_view.focus_selected_requested.connect(self.focus_on_samples)
        self.graph_view.show_all_samples_requested.connect(self.show_all_samples)

        # Connect the integration window's session data signals
        self.toolbar.integration.session_data_applied.connect(
            self.on_session_data_applied
        )
        self.toolbar.integration.session_data_restored.connect(
            self.on_session_data_restored
        )
        self.toolbar.integration.data_regeneration_requested.connect(
            self.on_data_regeneration_requested
        )
        self.toolbar.baseline_correction_changed.connect(
            self.on_baseline_correction_changed
        )
        self.toolbar.y_scale_policy_changed.connect(
            self.graph_view.set_y_scale_policy
        )
        self.graph_view.set_y_scale_policy(self.toolbar.y_scale_policy)

        # Clicking an Identity bar, or a row in a summary popup, highlights that sample's plot.
        for chart in (
            self.summary.targeted_qc,
            self.summary.total_abundance,
            self.summary.isotopologue_ratios,
        ):
            chart.sample_activated.connect(self._on_qc_sample_activated)

        self.start_panel.load_compounds_requested.connect(
            self.load_compound_action.trigger
        )
        self.start_panel.load_raw_data_requested.connect(self.load_cdf_action.trigger)
        self.start_panel.recent_compound_list_requested.connect(
            self._load_compound_list_from
        )
        self.start_panel.recent_raw_data_requested.connect(self._load_cdf_folder)
        self.start_panel.new_session_requested.connect(self.new_session_action.trigger)
        self.start_panel.documentation_requested.connect(
            self.open_documentation_window
        )
        self.installEventFilter(self.start_panel)
        self._refresh_shell()
        self.start_panel.primary_button.setFocus()

    def _build_view_menu(self, menu_bar: QMenuBar) -> None:
        view_menu = menu_bar.addMenu("View")
        self.view_menu = view_menu
        view_menu.setToolTipsVisible(True)
        # The grid header's density switch, for the keyboard.
        density = QActionGroup(view_menu)
        for key, text in (("compact", "Compact"), ("comfortable", "Comfortable")):
            action = density.addAction(text)
            action.setCheckable(True)
            action.setData(key)
            action.triggered.connect(lambda _checked=False, k=key: self.graph_view.set_density(k))
            view_menu.addAction(action)
        view_menu.aboutToShow.connect(
            lambda: next(
                a for a in density.actions() if a.data() == self.graph_view.density()
            ).setChecked(True)
        )
        view_menu.addSeparator()
        shortcuts = {"Shared Y-Scale": "Ctrl+Shift+Y", "Scale to Selected Peak": "Ctrl+Shift+P"}
        for action in self.toolbar.scale_actions():
            action.setShortcut(QKeySequence(shortcuts[action.text()]))
            view_menu.addAction(action)

        view_menu.addSeparator()
        self.find_compound_action = QAction("Find Compound", self)
        self.find_compound_action.setShortcut(QKeySequence.Find)
        self.find_compound_action.triggered.connect(self.toolbar.focus_compound_filter)
        view_menu.addAction(self.find_compound_action)

        self.previous_compound_action = QAction("Previous Compound", self)
        self.previous_compound_action.setShortcut(QKeySequence("Ctrl+["))
        self.previous_compound_action.triggered.connect(
            lambda: self.toolbar.step_compound(-1)
        )
        view_menu.addAction(self.previous_compound_action)

        self.next_compound_action = QAction("Next Compound", self)
        self.next_compound_action.setShortcut(QKeySequence("Ctrl+]"))
        self.next_compound_action.triggered.connect(
            lambda: self.toolbar.step_compound(1)
        )
        view_menu.addAction(self.next_compound_action)

        view_menu.addSeparator()
        self.show_samples_action = QAction("Sample List", self)
        self.show_samples_action.setCheckable(True)
        self.show_samples_action.setShortcut(QKeySequence("Ctrl+Shift+L"))
        self.show_samples_action.toggled.connect(
            self.toolbar.samples_section.set_expanded
        )
        self.toolbar.samples_section.toggled.connect(
            self.show_samples_action.setChecked
        )
        view_menu.addAction(self.show_samples_action)

        self.show_summary_action = QAction("Show Summary", self)
        self.show_summary_action.setCheckable(True)
        button = self.graph_view.summary_button
        self.show_summary_action.toggled.connect(button.setChecked)
        self.show_summary_action.toggled.connect(self._apply_summary)
        self.show_summary_action.triggered.connect(self._remember_summary_open)
        button.clicked.connect(self.show_summary_action.trigger)
        view_menu.addAction(self.show_summary_action)

        self.show_all_samples_action = QAction("Show All Samples", self)
        self.show_all_samples_action.triggered.connect(self.show_all_samples)  # listed in Review

    def _build_review_menu(self, menu_bar: QMenuBar) -> None:
        """The plot context menu's review commands, on the menu bar.

        They act from the graph view's review lead, and the graph view labels and
        enables them exactly as it does its context menu.
        """
        menu = menu_bar.addMenu("Review")
        self.review_menu = menu

        def grid_key(action: QAction, sequence) -> None:
            # The grid handles these keys itself; the menu only names them.
            action.setShortcut(QKeySequence(sequence))
            action.setShortcutContext(Qt.WidgetShortcut)
            # macOS hides shortcuts in a menu it opens outside the menu bar.
            action.setShortcutVisibleInContextMenu(True)

        def letter_key(action: QAction, key, on_key) -> None:
            # A bare letter that reaches the grid from anywhere in the window, so a
            # list never takes it as type-ahead; a text field claims it as typing.
            grid_key(action, key)
            QShortcut(QKeySequence(key), self).activated.connect(on_key)

        self.inspect_action = QAction("Inspect Sample...", self)
        grid_key(self.inspect_action, Qt.Key_Return)
        self.inspect_action.triggered.connect(
            lambda: self._with_review_lead(self.graph_view.inspect_plot)
        )
        menu.addAction(self.inspect_action)
        menu.addSeparator()

        self.select_all_plots_action = QAction("Select All Plots", self)
        grid_key(self.select_all_plots_action, QKeySequence.SelectAll)
        self.select_all_plots_action.triggered.connect(self.graph_view.select_all_plots)
        menu.addAction(self.select_all_plots_action)
        self.deselect_plots_action = QAction("Deselect All", self)
        grid_key(self.deselect_plots_action, Qt.Key_Escape)
        self.deselect_plots_action.triggered.connect(self.graph_view.clear_selection)
        menu.addAction(self.deselect_plots_action)
        self.show_only_selected_action = QAction("Show Only Selected Samples", self)
        self.show_only_selected_action.triggered.connect(
            lambda: self.graph_view.show_only_samples(self.graph_view.review_lead())
        )
        menu.addAction(self.show_only_selected_action)
        menu.addAction(self.show_all_samples_action)
        menu.addSeparator()

        # The review loop: reach the next flagged sample, then judge it.
        self.next_flagged_action = QAction("Next Flagged Sample", self)
        self.next_flagged_action.triggered.connect(lambda: self._focus_flagged(1))
        letter_key(self.next_flagged_action, Qt.Key_N, lambda: self._focus_flagged(1))
        menu.addAction(self.next_flagged_action)
        self.previous_flagged_action = QAction("Previous Flagged Sample", self)
        self.previous_flagged_action.triggered.connect(lambda: self._focus_flagged(-1))
        letter_key(
            self.previous_flagged_action, Qt.SHIFT | Qt.Key_N, lambda: self._focus_flagged(-1)
        )
        menu.addAction(self.previous_flagged_action)
        self.accept_peak_action = QAction("Accept Peak (Below Threshold)", self)
        self.accept_peak_action.triggered.connect(
            lambda: self._with_review_lead(
                lambda plot: self.graph_view.toggle_peak_review(plot, PeakReview.ACCEPTED)
            )
        )
        letter_key(
            self.accept_peak_action, Qt.Key_A, lambda: self._trigger_review(self.accept_peak_action)
        )
        menu.addAction(self.accept_peak_action)
        self.reject_peak_action = QAction("Mark Peak as Bad", self)
        self.reject_peak_action.triggered.connect(
            lambda: self._with_review_lead(
                lambda plot: self.graph_view.toggle_peak_review(plot, PeakReview.REJECTED)
            )
        )
        letter_key(
            self.reject_peak_action, Qt.Key_B, lambda: self._trigger_review(self.reject_peak_action)
        )
        menu.addAction(self.reject_peak_action)
        self.review_fit_menu = menu.addMenu("Curve Fit")
        menu.addSeparator()
        # The Peak window's baseline toggle, so it sits with the peak commands.
        baseline = self.toolbar.baseline_checkbox
        self.baseline_action = QAction("Baseline Correction", self)
        self.baseline_action.setCheckable(True)
        self.baseline_action.setChecked(baseline.isChecked())
        self.baseline_action.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self.baseline_action.setShortcutVisibleInContextMenu(True)
        self.baseline_action.triggered.connect(lambda checked: baseline.setChecked(checked))
        baseline.toggled.connect(self.baseline_action.setChecked)
        menu.addAction(self.baseline_action)

        menu.aboutToShow.connect(self._sync_review_menu)
        self.graph_view.selection_changed.connect(self._sync_review_menu)
        self._sync_review_menu()

    def _sync_review_menu(self, *_args) -> None:
        view = self.graph_view
        self.select_all_plots_action.setEnabled(view.has_plots())
        for action in (self.next_flagged_action, self.previous_flagged_action):
            action.setEnabled(view.has_flagged())
        self.deselect_plots_action.setEnabled(bool(view.get_selected_samples()))
        view.update_review_actions(
            view.review_lead(),
            inspect=self.inspect_action,
            show_only=self.show_only_selected_action,
            accept=self.accept_peak_action,
            reject=self.reject_peak_action,
            fit_menu=self.review_fit_menu,
        )

    def _focus_flagged(self, step: int) -> None:
        view = self.graph_view
        if not view.focus_flagged(step) and view.has_plots():
            show_status_toast(
                self.statusBar(), f"No flagged plots in {view.get_current_compound()}"
            )

    def _trigger_review(self, action: QAction) -> None:
        # Arrow keys move the review lead without a selection change, so refresh first.
        self._sync_review_menu()
        if action.isEnabled():
            action.trigger()

    def _with_review_lead(self, command) -> None:
        lead = self.graph_view.review_lead()
        if lead is not None:
            command(lead)
        self._sync_review_menu()

    def _setup_status_bar(self) -> None:
        bar = self.statusBar()
        bar.setSizeGripEnabled(False)
        self.deconvolution_indicator_label = QPushButton()
        self.deconvolution_indicator_label.setObjectName("statusDeconvolution")
        self.deconvolution_indicator_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deconvolution_indicator_label.setToolTip(
            "Peak deconvolution for this compound. Click to change it in Settings."
        )
        self.deconvolution_indicator_label.clicked.connect(
            lambda: self.open_settings_page("Deconvolution")
        )
        bar.addPermanentWidget(self.deconvolution_indicator_label)

    def _build_no_samples_panel(self) -> QWidget:
        """The workspace while every sample is unchecked in the sidebar."""
        panel = QWidget()
        panel.setObjectName("noSamplesPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)
        layout.addStretch(1)
        title = QLabel("No samples shown")
        title.setProperty("role", "title")
        detail = QLabel(
            "Every sample is unchecked in the Samples list.\n"
            "Check the ones to plot."
        )
        detail.setProperty("role", "secondary")
        detail.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.show_all_samples_button = QPushButton("Show all samples")
        self.show_all_samples_button.setProperty("variant", "primary")
        self.show_all_samples_button.clicked.connect(self.show_all_samples)
        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)
        layout.addWidget(detail, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(16)
        layout.addWidget(self.show_all_samples_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(2)
        return panel

    def _no_samples_shown(self) -> bool:
        return (
            self.cdf_data_loaded
            and self.toolbar.sample_list.real_count() > 0
            and not self.toolbar.get_selected_samples()
        )

    def _refresh_shell(self) -> None:
        """Workspace page and start panel from the loaded-data state."""
        if not hasattr(self, "start_panel"):
            return
        self.start_panel.refresh(
            self.compound_data_loaded,
            self.load_compound_action.isEnabled(),
            self.load_cdf_action.isEnabled(),
            self._recent_compounds.paths(),
            self._recent_cdf.paths(),
        )
        if not self.cdf_data_loaded:
            page = self.start_panel
        elif self._no_samples_shown():
            page = self.no_samples_panel
        else:
            page = self.graph_view
        self.workspace.setCurrentWidget(page)
        if page is self.graph_view and not self._summary_settled:
            self._summary_settled = True
            settings = QSettings()
            self.show_summary_action.setChecked(
                settings.value(SUMMARY_OPEN_SETTING, type=bool)
                if settings.contains(SUMMARY_OPEN_SETTING)
                else self.width() >= SUMMARY_MIN_WINDOW_WIDTH
            )
        self._apply_summary()
        # Loading selects the first compound without on_compound_selected, so name it here.
        self.update_deconvolution_indicator(
            self.selected_compound_name() if self.compound_data_loaded else None
        )

    def _apply_summary(self, *_args) -> None:
        """Show the Summary beside the grid while it is open, at the width last dragged to."""
        shown = (
            self.workspace.currentWidget() is self.graph_view
            and self.show_summary_action.isChecked()
        )
        if shown != self.summary.isHidden():
            return
        if not shown:
            self.summary.hide()
            return
        sidebar = self.splitter.sizes()[0]
        # The grid's and the panel's share once both show, with a handle each.
        free = self.splitter.width() - sidebar - 2 * self.splitter.handleWidth()
        saved = QSettings().value(SUMMARY_WIDTH_SETTING, SUMMARY_WIDTH, type=int)
        # Taken from the grid down to its two columns, never from the sidebar.
        width = max(min(saved, free - self.workspace.minimumSizeHint().width()), SUMMARY_MIN_WIDTH)
        self.summary.show()
        self.splitter.setSizes([sidebar, free - width, width])

    def _remember_summary_open(self, shown: bool) -> None:
        self._summary_settled = True
        QSettings().setValue(SUMMARY_OPEN_SETTING, shown)

    def _remember_summary_width(self, *_args) -> None:
        if not self.summary.isHidden():
            QSettings().setValue(SUMMARY_WIDTH_SETTING, self.splitter.sizes()[2])

    def dragEnterEvent(self, event):
        if self._dropped_path(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        path = self._dropped_path(event)
        if path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        if path.is_dir():
            self._load_cdf_folder(str(path))
        else:
            self._load_compound_list_from(str(path))

    def _dropped_path(self, event) -> Path | None:
        """The one local file or folder dropped, if loading it is allowed right now."""
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = Path(urls[0].toLocalFile())
        if path.is_dir():
            return path if self.load_cdf_action.isEnabled() else None
        if path.suffix.lower() in COMPOUND_LIST_SUFFIXES:
            return path if self.load_compound_action.isEnabled() else None
        return None

    def _get_logo_path(self) -> str:
        """Get the path to the MANIC logo."""
        # Try to find the logo relative to this file
        logo_path = resource_path("resources", "manic_logo.png")
        if os.path.exists(logo_path):
            return logo_path
        return ""

    def _set_window_icon(self):
        """Set the window icon to the MANIC logo."""
        logo_path = self._get_logo_path()
        if logo_path:
            self.setWindowIcon(QIcon(logo_path))

    def _create_message_box(
        self,
        msg_type: str,
        title: str,
        text: str,
        informative_text: str = "",
        parent=None,
    ) -> QMessageBox:
        """Create a message box with consistent styling and logo."""
        if parent is None:
            parent = self

        # Create a custom message box without standard icons
        msg_box = QMessageBox(parent=parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)

        # Set informative text if provided
        if informative_text:
            msg_box.setInformativeText(informative_text)

        # Set appropriate buttons based on message type
        if msg_type == "information":
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.setDefaultButton(QMessageBox.Ok)
        elif msg_type == "warning":
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.setDefaultButton(QMessageBox.Ok)
        elif msg_type == "critical":
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.setDefaultButton(QMessageBox.Ok)
        elif msg_type == "question":
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.Yes)

        return msg_box

    def _confirm(
        self, title: str, text: str, informative_text: str, verb: str, parent=None
    ) -> bool:
        """Ask before acting: the button names the action, and Return cancels."""
        box = self._create_message_box("question", title, text, informative_text, parent)
        box.setStandardButtons(QMessageBox.Cancel)
        act = box.addButton(verb, QMessageBox.AcceptRole)
        box.setDefaultButton(QMessageBox.Cancel)
        box.exec()
        return box.clickedButton() is act

    def _show_message(
        self, msg_type: str, title: str, text: str, informative_text: str = ""
    ) -> None:
        """Create and show an information/warning/critical message box."""
        self._create_message_box(msg_type, title, text, informative_text).exec()

    def _running_background_thread(self) -> str | None:
        for thread_attr in (
            "_thread",
            "_regen_thread",
            "_mass_tol_thread",
            "_export_thread",
        ):
            thread = getattr(self, thread_attr, None)
            if thread is None:
                continue
            try:
                running = thread.isRunning()
            except RuntimeError:
                setattr(self, thread_attr, None)
                continue
            if running:
                return thread_attr
        return None

    def _background_work_running(self, before: str) -> bool:
        """Import/reload workers still hold the database; refuse to wipe it under them."""
        if self._running_background_thread() is None:
            return False
        self._show_message(
            "information",
            "Operation in progress",
            f"Wait for the current import or reload to finish before {before}.",
        )
        return True

    def _update_menu_states(self):
        """Update menu item enabled/disabled states based on current data state."""
        export_running = self._running_background_thread() == "_export_thread"

        # Load Compound Data: enabled only if not yet loaded
        self.load_compound_action.setEnabled(
            not self.compound_data_loaded and not export_running
        )

        # Load CDF Data: enabled only if compound data loaded but CDF not loaded
        self.load_cdf_action.setEnabled(
            self.compound_data_loaded
            and not self.cdf_data_loaded
            and not export_running
        )

        # Export Session: enabled if compound data loaded
        self.export_method_action.setEnabled(self.compound_data_loaded)

        # Export Data: enabled only if compound data, CDF data loaded
        self.export_data_action.setEnabled(
            self.compound_data_loaded
            and self.cdf_data_loaded
            and not export_running
        )

        self.check_setup_action.setEnabled(
            self.compound_data_loaded and self.cdf_data_loaded
        )

        # Import Session: enabled only if both compound and CDF data loaded
        can_import = self.compound_data_loaded and self.cdf_data_loaded
        self.import_session_action.setEnabled(can_import)
        self.import_session_action.setToolTip(
            "" if can_import else "Load the session's compound list and raw data first"
        )

        # Clear Session: enabled if any data loaded
        self.clear_session_action.setEnabled(
            (self.compound_data_loaded or self.cdf_data_loaded)
            and not export_running
        )
        self.new_session_action.setEnabled(not export_running)

        if self.settings_window is not None:
            self.settings_window.refresh()
        self._refresh_shell()

    # reusable progress dialog
    def _build_progress_dialog(self, title: str) -> QProgressDialog:
        dlg = QProgressDialog(title, None, 0, 100, self)
        dlg.setWindowTitle("Please wait")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setMinimumDuration(0)  # Show immediately
        dlg.setCancelButton(None)  # Remove cancel button for simplicity

        # Set the logo
        logo_path = self._get_logo_path()
        if logo_path:
            dlg.setWindowIcon(QIcon(logo_path))

        return dlg

    def new_analysis_session(
        self,
        _checked: bool = False,
        *,
        preset_mode: AnalysisMode | None = None,
    ) -> None:
        """Start a fresh session, optionally switching analysis mode.

        The session is the unit of scientific consistency: compounds and
        results from one mode must never be interpreted with the other mode's
        workflow, so switching mode means starting a new session. The
        database is cleared and the window is rebuilt exactly as at startup.

        ``QAction.triggered`` supplies a checked-state boolean even for a
        non-checkable action. Keep that signal argument separate from the
        optional mode selected by compound-list format detection.
        """
        if self._background_work_running("starting a new session"):
            return

        if self.compound_data_loaded or self.cdf_data_loaded:
            if not self._confirm(
                "New Analysis Session",
                "Starting a new session will clear all loaded data.",
                "Compound data, raw data, and results in this session will be "
                "removed. Export anything you want to keep first.",
                "Start New Session",
            ):
                return

        if preset_mode is not None:
            mode = AnalysisMode.coerce(preset_mode)
        else:
            from manic.ui.analysis_mode_dialog import choose_analysis_mode

            mode = choose_analysis_mode(self)
            if mode is None:
                return
            if mode is self.analysis_mode:
                self._show_message(
                    "information",
                    "Already in this mode",
                    f"This session is already in {mode.display_name} mode. "
                    "Use 'Clear Session' to reset its data.",
                )
                return

        try:
            clear_database()
        except Exception as exc:
            self._show_message("critical", "Could not clear session", str(exc))
            return

        window = MainWindow(AnalysisContext(mode))
        # Parent-less widgets need a live Python reference or GC destroys them
        QApplication.instance()._manic_main_window = window
        window.showMaximized()
        # Already confirmed the session wipe; close must not ask again.
        self._skip_close_guard = True
        self.close()
        logger.info(f"New analysis session started in {mode.display_name} mode")

    def closeEvent(self, event):
        if self._skip_close_guard:
            event.accept()
            return
        running = self._running_background_thread()
        if running is not None:
            if running == "_export_thread":
                quit_text = (
                    "An export is still running. Quitting now cancels the export."
                )
            else:
                quit_text = (
                    "An import or reload is still running. Quitting now leaves "
                    "the database partly written."
                )
            if not self._confirm("Quit MANIC?", quit_text, "", "Quit"):
                event.ignore()
                return
            if running == "_export_thread":
                if self._export_worker is not None:
                    self._export_worker.cancel()
                if self._export_thread is not None:
                    self._export_thread.wait()
        elif self.compound_data_loaded or self.cdf_data_loaded:
            if not self._confirm(
                "Quit MANIC?",
                "This session is not saved. Use File > Export Method... to keep the compound settings before quitting.",
                "",
                "Quit",
            ):
                event.ignore()
                return
        event.accept()

    def _rebuild_open_recent_menu(self) -> None:
        self.open_recent_menu.clear()
        compounds = self._recent_compounds.paths()
        folders = self._recent_cdf.paths()
        for path in compounds:
            action = QAction(Path(path).name, self)
            action.setToolTip(str(Path(path).parent))
            action.triggered.connect(
                lambda _checked=False, p=path: self._load_compound_list_from(p)
            )
            action.setEnabled(self.load_compound_action.isEnabled())
            self.open_recent_menu.addAction(action)
        self.open_recent_menu.addSeparator()
        for path in folders:
            action = QAction(Path(path).name, self)
            action.setToolTip(str(Path(path).parent))
            action.triggered.connect(
                lambda _checked=False, p=path: self._load_cdf_folder(p)
            )
            action.setEnabled(self.load_cdf_action.isEnabled())
            self.open_recent_menu.addAction(action)
        self.open_recent_menu.addSeparator()
        clear_action = QAction("Clear Recent", self)
        clear_action.triggered.connect(self._clear_recent_files)
        self.open_recent_menu.addAction(clear_action)
        self.open_recent_menu.setEnabled(bool(compounds or folders))

    def _clear_recent_files(self) -> None:
        self._recent_compounds.clear()
        self._recent_cdf.clear()
        self.open_recent_menu.setEnabled(False)
        self._refresh_shell()

    def load_compound_list_data(self: QMainWindow) -> None:
        """
        1. Prompt the user to select a compound list file.
        2. Call the load_compound_list controller function to load the compound list.

        """
        default_dir = str(Path.home() / "Documents")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Compound List",
            default_dir,
            "Excel/CSV Files (*.xls *.xlsx *.csv)",
        )
        if not file_path:
            return
        self._load_compound_list_from(file_path)

    def _load_compound_list_from(self, path: str) -> None:
        if not self.load_compound_action.isEnabled():
            return
        detected_mode = detect_compound_list_format(path)
        if detected_mode is not None and detected_mode is not self.analysis_mode:
            msg_box = self._create_message_box(
                "warning",
                "Compound list does not match this session",
                f"This looks like a {detected_mode.display_name} "
                f"compound list, but this session is in "
                f"{self.analysis_mode.display_name} mode.\n\n"
                f"Start a new {detected_mode.display_name} session and load it there?",
            )
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.Yes)
            if msg_box.exec() == QMessageBox.Yes:
                self.new_analysis_session(preset_mode=detected_mode)
            return

        self._recent_compounds.add(path)
        self.open_recent_menu.setEnabled(True)
        try:
            self.compounds_data_storage = import_compound_excel(
                path,
                analysis_mode=self.analysis_mode,
            )
            self.compound_list_path = path
            self.toolbar.update_label_colours(False, True)
            self.toolbar.update_compound_list(list_compound_names())

            # Update state and menu
            self.compound_data_loaded = True
            self._update_menu_states()

        except Exception as e:
            self._show_message("warning", "Error", str(e))

    def show_add_compound_dialog(self) -> None:
        from manic.ui.add_compound_dialog import AddCompoundDialog

        dialog = AddCompoundDialog(
            self, self.analysis_mode, taken_names=taken_compound_names()
        )
        if dialog.exec() != QDialog.Accepted:
            return
        record = dialog.record
        if record is None:
            return
        try:
            if isinstance(record, UnlabelledCompoundRecord):
                insert_unlabelled_compound(record)
            else:
                insert_compound(record)
        except ValueError as exc:
            self._show_message("warning", "Add Compound", str(exc))
            return
        self._after_compound_added(record.compound_name)

    def _after_compound_added(self, compound_name: str) -> None:
        first_compound = not self.compound_data_loaded
        self.toolbar.update_compound_list(
            list_compound_names(), selected_name=compound_name
        )
        if first_compound:
            self.compound_data_loaded = True
            self.toolbar.update_label_colours(False, True)
            self._update_menu_states()

        # DataProvider caches are per-instance and no long-lived instance
        # exists; only the validation provider outlives a compound change.
        if self._validation_provider is not None:
            self._validation_provider.invalidate_cache()

        if self.cdf_data_loaded:
            samples = list_active_samples()
            if not samples:
                return
            try:
                compound = read_compound(compound_name)
            except Exception as exc:
                self._show_message("warning", "Add Compound", str(exc))
                return
            required = minimum_extract_rt_window(compound.loffset, compound.roffset)
            tr_window = max(DEFAULT_RT_WINDOW, required)
            if compound.rt_tolerance is not None:
                tr_window = max(tr_window, float(compound.rt_tolerance))
            self.on_data_regeneration_requested(
                compound_name,
                tr_window,
                samples,
                compound.retention_time,
            )

    def load_cdf_files(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory Containing CDF Files"
        )
        if not directory:
            return
        self._load_cdf_folder(directory)

    def _load_cdf_folder(self, path: str):
        if not self.load_cdf_action.isEnabled():
            return
        self._recent_cdf.add(path)
        self.open_recent_menu.setEnabled(True)

        # build dialog & worker
        self.progress_dialog = self._build_progress_dialog("Importing CDF data…")
        self.progress_dialog.show()

        self._thread = QThread(self)  # background thread
        self._worker = CdfImportWorker(path, self.mass_tolerance)  # heavy lifting
        self._worker.moveToThread(self._thread)

        # progress updates
        self._worker.progress.connect(self._update_import_progress)
        # finish / fail
        self._worker.finished.connect(self._import_ok)
        self._worker.failed.connect(self._import_fail)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)

        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _update_import_progress(self, current: int, total: int):
        pct = int(current / total * 100)
        self.progress_dialog.setMaximum(100)
        self.progress_dialog.setValue(pct)
        self.progress_dialog.setLabelText("Importing…")
        QCoreApplication.processEvents()

    def _import_ok(self, rows: int):
        self.progress_dialog.close()

        # Non-blocking success notification (avoid modal popup)
        show_status_toast(self.statusBar(), f"Imported {rows} EICs")
        self.workspace.setCurrentWidget(self.graph_view)

        # set raw data indicator to green
        self.toolbar.update_label_colours(True, True)

        # get active samples
        active_samples = list_active_samples()

        # update samples list in toolbar
        # update to samples list in toolbar will trigger plotting
        self.toolbar.update_sample_list(active_samples)

        # Update state and menu
        self.cdf_data_loaded = True
        self._update_menu_states()
        self.show_post_load_checklist()

    def _import_fail(self, msg: str):
        self.progress_dialog.close()
        msg_box = self._create_message_box("critical", "Import failed", msg)
        msg_box.exec()

    def _peak_verdicts(self, compound_name: str, samples) -> dict[str, PeakVerdict]:
        reviews = get_peak_reviews()
        internal_standard = self.toolbar.get_internal_standard()
        if self._validation_provider is None:
            self._validation_provider = DataProvider(
                use_legacy_integration=self.use_legacy_integration,
            )
        verdicts = {}
        for sample in samples:
            try:
                verdicts[sample] = self._validation_provider.peak_verdict(
                    sample,
                    compound_name,
                    internal_standard,
                    self.min_peak_height_ratio,
                    internal_standard_isotope_index=self.internal_standard_reference_isotope,
                    reviews=reviews,
                )
            except Exception as e:
                logger.warning(
                    f"Peak verdict failed for {compound_name}/{sample}: {e}"
                )
                verdicts[sample] = PeakVerdict.PASS
        return verdicts

    def on_peak_review_changed(self, compound_name: str, sample_names: list, review):
        for sample_name in sample_names:
            set_peak_review(compound_name, sample_name, review)
        samples = self.graph_view.get_current_samples()
        self.graph_view.apply_peak_verdicts(self._peak_verdicts(compound_name, samples))

    def on_plot_button(self, compound_name, samples):
        # Validate inputs before plotting
        if not compound_name or compound_name.startswith("- No"):
            return  # Don't plot with placeholder compound

        if any(sample.startswith("- No") for sample in samples):
            return  # Don't plot with placeholder samples
        if not samples:
            self._show_no_samples(compound_name)
            return

        try:
            if samples:
                with measure_time("total_plotting_speed"):
                    validation_data = self._peak_verdicts(compound_name, samples)

                    provider, identity = self._identity_snapshot(compound_name, samples)
                    self.graph_view.plot_compound(
                        compound_name,
                        samples,
                        validation_data,
                        identity=identity,
                    )

                # A re-plot of the same compound keeps its selection (graph view).
                self.toolbar.integration.populate_fields_from_plots(
                    compound_name,
                    self.graph_view.get_selected_samples(),
                    samples,
                )

                self.toolbar.integration.populate_tr_window_field(compound_name)
                self._refresh_shell()

                self._refresh_mode_charts(
                    compound_name,
                    samples,
                    identity=identity,
                    provider=provider,
                )
        except LookupError as err:
            msg_box = self._create_message_box("warning", "Missing data", str(err))
            msg_box.exec()
        except Exception as e:
            logger.error(f"Error plotting: {e}")
            msg_box = self._create_message_box(
                "warning", "Error", f"Error plotting: {str(e)}"
            )
            msg_box.exec()

    def _show_no_samples(self, compound_name: str) -> None:
        """Nothing checked: no plots, no summaries, and nothing for the inspector to apply to."""
        self.graph_view.clear_all_plots()
        self.toolbar.integration.populate_fields_from_plots(compound_name, [], [])
        self.toolbar.integration.populate_tr_window_field(compound_name)
        self.summary.isotopologue_ratios._clear_chart()
        self.summary.total_abundance._clear_chart()
        self.summary.targeted_qc.clear()
        self._refresh_shell()

    def _get_current_eics(self):
        """Get EICs for the current compound and samples"""
        compound = self.graph_view.get_current_compound()
        samples = self.graph_view.get_current_samples()

        if not compound or not samples:
            return []

        try:
            from manic.processors.eic_processing import get_eics_for_compound

            return get_eics_for_compound(compound, samples)
        except Exception as e:
            logger.error(f"Error getting current EICs: {e}")
            return []

    def _calculate_total_abundances_fallback(self, compound_name: str, eics):
        """Compute total abundances directly from single-trace EICs.

        This is a fallback path so Total Abundance can still render when the
        isotopologue widget doesn't populate its cached abundance array.
        """
        if not eics or not compound_name:
            return None

        abundances = []
        for eic in eics:
            compound = read_compound_with_session(compound_name, eic.sample_name)
            baseline_correction = bool(getattr(compound, "baseline_correction", 0))

            intensity = np.asarray(eic.intensity, dtype=np.float64)
            channel_count = (
                intensity.shape[0] if intensity.ndim > 1 else compound.channel_count
            )
            isotope_areas = calculate_peak_areas(
                eic.time,
                intensity.ravel(),
                label_atoms=0,
                retention_time=compound.retention_time,
                loffset=compound.loffset,
                roffset=compound.roffset,
                channel_count=channel_count,
                baseline_correction=baseline_correction,
                chromatographic_peak_deconvolution_stringency=compound.deconvolution_level,
                chromatographic_peak_deconvolution_fit_type=compound.deconvolution_fit_type,
                chromatographic_peak_deconvolution_noise_gate=compound.deconvolution_noise_gate,
            )
            abundances.append(float(sum(isotope_areas)))

        return np.asarray(abundances, dtype=float)

    def _identity_snapshot(self, compound_name: str, sample_names: list[str]):
        if self.analysis_mode is not AnalysisMode.UNLABELLED:
            return None, None
        provider = DataProvider(use_legacy_integration=self.use_legacy_integration)
        return provider, self._assess_identities(provider, compound_name, sample_names)

    def _assess_identities(self, provider, compound_name, sample_names):
        if not compound_name or not sample_names:
            return None
        try:
            return provider.assess_unlabelled_identities(compound_name, sample_names)
        except (LookupError, ValueError):
            logger.warning(
                "Identity assessment unavailable for %r", compound_name, exc_info=True
            )
            return None

    def _refresh_mode_charts(
        self,
        compound_name: str,
        qc_samples: list[str] | None = None,
        *,
        skip_qc: bool = False,
        identity=None,
        provider=None,
    ) -> None:
        if self.analysis_mode is not AnalysisMode.LABELLED:
            if provider is None:
                provider = DataProvider(
                    use_legacy_integration=self.use_legacy_integration
                )
            if not skip_qc:
                samples = qc_samples or self.graph_view.get_current_samples()
                if identity is None:
                    identity = self._assess_identities(
                        provider, compound_name, samples
                    )
                self._update_targeted_qc(identity)
        self._update_total_abundance(compound_name, provider)

    def _update_total_abundance(
        self, compound_name: str, provider: DataProvider | None = None
    ) -> None:
        current_eics = self._get_current_eics()
        if self.analysis_mode is AnalysisMode.LABELLED:
            self.summary.isotopologue_ratios.update_ratios(
                compound_name, current_eics
            )
            abundances, eics = (
                self.summary.isotopologue_ratios.get_last_total_abundances()
            )
            if abundances is None:
                abundances = self._calculate_total_abundances_fallback(
                    compound_name, current_eics
                )
                eics = current_eics
        elif not current_eics:
            abundances, eics = None, current_eics
        else:
            eics = current_eics
            abundances = abundances_from_provider(
                provider,
                compound_name,
                [eic.sample_name for eic in eics],
            )

        if abundances is None:
            self.summary.total_abundance._clear_chart()
            return
        self.summary.total_abundance.update_abundance_from_data(
            compound_name, eics, abundances
        )
        selected = self.graph_view.get_selected_samples()
        self.summary.total_abundance.set_highlighted(selected)
        self.summary.isotopologue_ratios.set_highlighted(selected)
        self.summary.targeted_qc.set_highlighted(selected)

    def _update_targeted_qc(self, identity) -> None:
        if self.analysis_mode is not AnalysisMode.UNLABELLED:
            return
        if identity is None:
            self.summary.targeted_qc.clear()
            return
        self.summary.targeted_qc.update_results(identity)

    def _on_qc_sample_activated(self, sample_name: str) -> None:
        """Highlight the plot for a sample clicked on the Identity chart."""
        self.graph_view.select_sample(sample_name)

    def on_compound_selected(self, compound_selected):
        samples = self.toolbar.get_selected_samples()
        self.update_deconvolution_indicator(compound_selected)
        self.on_plot_button(compound_selected, samples)
        if self.settings_window is not None:
            self.settings_window.refresh()

    def on_compounds_deleted(self, compound_names: list):
        """
        Handle compound deletion - refresh UI and invalidate caches.
        Called when compounds are soft-deleted via the context menu.
        """
        if self._deleting_compound:
            return

        self._deleting_compound = True

        try:
            # Clear the graph view
            self.graph_view.clear_all_plots()

            # Force UI refresh
            QCoreApplication.processEvents()
            self.graph_view.update()
            self.graph_view.repaint()
            QCoreApplication.processEvents()

            # Refresh compound list
            active_compounds = list_compound_names()
            self.toolbar.update_compound_list(active_compounds)

            # Invalidate caches
            data_provider = DataProvider()
            data_provider.invalidate_cache()

            if self._validation_provider:
                self._validation_provider.invalidate_cache()

            logger.info(f"Deleted {len(compound_names)} compound(s)")

        except Exception as e:
            logger.error(f"Error during compound deletion: {e}")
        finally:
            self._deleting_compound = False

    def on_compounds_restored(self, compound_names: list):
        """
        Handle compound restoration - refresh UI and invalidate caches.
        Called when compounds are restored via the recovery dialog.
        """
        try:
            # Refresh compound list
            active_compounds = list_compound_names()
            self.toolbar.update_compound_list(active_compounds)

            # Invalidate caches
            data_provider = DataProvider()
            data_provider.invalidate_cache()

            if self._validation_provider:
                self._validation_provider.invalidate_cache()

            logger.info(f"Restored {len(compound_names)} compound(s)")

        except Exception as e:
            logger.error(f"Error during compound restoration: {e}")

    def on_samples_deleted(self, sample_names: list):
        """
        Handle sample deletion - refresh UI and invalidate caches.
        Called when samples are soft-deleted via the context menu.
        """
        if self._deleting_samples:
            return

        self._deleting_samples = True

        try:
            # Clear the graph view
            self.graph_view.clear_all_plots()

            # Force UI refresh
            QCoreApplication.processEvents()
            self.graph_view.update()
            self.graph_view.repaint()
            QCoreApplication.processEvents()

            # Refresh sample list
            active_samples = list_active_samples()
            self.toolbar.update_sample_list(active_samples)

            # Invalidate caches
            data_provider = DataProvider()
            data_provider.invalidate_cache()

            if self._validation_provider:
                self._validation_provider.invalidate_cache()

            logger.info(f"Deleted {len(sample_names)} sample(s)")

        except Exception as e:
            logger.error(f"Error during sample deletion: {e}")
        finally:
            self._deleting_samples = False

    def on_samples_restored(self, sample_names: list):
        """
        Handle sample restoration - refresh UI and invalidate caches.
        Called when samples are restored via the recovery dialog.
        """
        try:
            # Refresh sample list
            active_samples = list_active_samples()
            self.toolbar.update_sample_list(active_samples)

            # Invalidate caches
            data_provider = DataProvider()
            data_provider.invalidate_cache()

            if self._validation_provider:
                self._validation_provider.invalidate_cache()

            logger.info(f"Restored {len(sample_names)} sample(s)")

        except Exception as e:
            logger.error(f"Error during sample restoration: {e}")

    def on_samples_selected(self, samples_selected):
        compound = self.toolbar.get_selected_compound()
        self.on_plot_button(compound, samples_selected)

    def focus_on_samples(self, names: list[str]) -> None:
        self.toolbar.set_selected_samples(names)
        self.graph_view.select_samples(names)

    def show_all_samples(self) -> None:
        self.toolbar.select_all_samples()

    def on_internal_standard_selected(self, internal_standard):
        """
        Handle internal standard selection changes.
        Updates menu states when internal standard is selected/deselected.
        """
        # Reset labelled-IS reference peak to M0 whenever standard changes
        self.internal_standard_reference_isotope = 0

        # Invalidate validation cache since threshold may change
        if self._validation_provider is not None:
            self._validation_provider.invalidate_cache()

        compound = self.graph_view.get_current_compound()
        samples = self.graph_view.get_current_samples()
        if compound and samples:
            self.graph_view.apply_peak_verdicts(self._peak_verdicts(compound, samples))

        # Update menu states to enable/disable Export Data based on internal standard selection
        self._update_menu_states()
        if self.settings_window is not None:
            self.settings_window.refresh()

    def on_plot_selection_changed(self, selected_samples):
        """Handle when plots are selected/deselected"""
        # Update integration window based on plot selection
        current_compound = self.graph_view.get_current_compound()
        all_samples = self.graph_view.get_current_samples()

        if current_compound:
            self.toolbar.integration.populate_fields_from_plots(
                current_compound, selected_samples, all_samples
            )

            # Verdicts do not depend on the selection; the charts only re-highlight.
            self._refresh_mode_charts(current_compound, all_samples, skip_qc=True)

    def on_session_data_applied(self, compound_name: str, sample_names: list):
        logger.info(f"Session data applied for {compound_name}, refreshing plots")

        try:
            # Invalidate validation provider cache since integration boundaries changed
            if self._validation_provider is not None:
                self._validation_provider.invalidate_cache()

            current_samples = self.graph_view.get_current_samples()
            validation_data = self._peak_verdicts(compound_name, current_samples)

            _provider, identity = self._identity_snapshot(compound_name, current_samples)
            self.graph_view.refresh_plots_with_session_data(
                validation_data, identity=identity
            )

            # After refreshing plots, update the integration window to show the new values
            # Add a small delay to ensure the plot refresh is fully complete

            def update_integration_window():
                current_selected = self.graph_view.get_selected_samples()
                all_samples = self.graph_view.get_current_samples()

                if compound_name:
                    self.toolbar.integration.populate_fields_from_plots(
                        compound_name, current_selected, all_samples
                    )

            # Use a timer to delay the update slightly
            QTimer.singleShot(100, update_integration_window)

            def update_charts():
                self._refresh_mode_charts(compound_name)

            QTimer.singleShot(150, update_charts)

        except Exception as e:
            logger.error(f"Failed to refresh plots after session data update: {e}")
            # Show error to user but don't crash the application
            msg_box = self._create_message_box(
                "warning",
                "Refresh Failed",
                f"Failed to refresh plots with updated parameters: {str(e)}",
            )
            msg_box.exec()

    def on_session_data_restored(self, compound_name: str, sample_names: list):
        """Handle when session data is restored - refresh plots to show default parameters"""
        logger.info(f"Session data restored for {compound_name}, refreshing plots")

        try:
            current_samples = self.graph_view.get_current_samples()
            _provider, identity = self._identity_snapshot(compound_name, current_samples)
            self.graph_view.refresh_plots_with_session_data(identity=identity)

            # After refreshing plots, update the integration window to show the default values

            def update_integration_window():
                current_selected = self.graph_view.get_selected_samples()
                all_samples = self.graph_view.get_current_samples()

                if compound_name:
                    self.toolbar.integration.populate_fields_from_plots(
                        compound_name, current_selected, all_samples
                    )

            # Use a timer to delay the update slightly
            QTimer.singleShot(100, update_integration_window)

            def update_charts():
                self._refresh_mode_charts(compound_name)

            QTimer.singleShot(150, update_charts)

        except Exception as e:
            logger.error(f"Failed to refresh plots after session data restore: {e}")
            # Show error to user but don't crash the application
            msg_box = self._create_message_box(
                "warning",
                "Refresh Failed",
                f"Failed to refresh plots after restore: {str(e)}",
            )
            msg_box.exec()

    def on_baseline_correction_changed(self, compound_name: str, enabled: bool):
        """Handle when baseline correction checkbox is toggled - refresh plots to show/hide baseline lines"""
        logger.info(
            f"Baseline correction {'enabled' if enabled else 'disabled'} for {compound_name}, refreshing plots"
        )

        try:
            # Invalidate validation provider cache since peak areas may change
            if self._validation_provider is not None:
                self._validation_provider.invalidate_cache()

            current_samples = self.graph_view.get_current_samples()
            validation_data = self._peak_verdicts(compound_name, current_samples)

            _provider, identity = self._identity_snapshot(compound_name, current_samples)
            self.graph_view.refresh_plots_with_session_data(
                validation_data, identity=identity
            )


            def update_charts():
                self._refresh_mode_charts(compound_name)

            QTimer.singleShot(150, update_charts)

        except Exception as e:
            logger.error(
                f"Failed to refresh plots after baseline correction change: {e}"
            )
            msg_box = self._create_message_box(
                "warning",
                "Refresh Failed",
                f"Failed to refresh plots with baseline correction: {str(e)}",
            )
            msg_box.exec()

    def on_data_regeneration_requested(
        self,
        compound_name: str,
        tr_window: float,
        sample_names: list,
        retention_time: float | dict[str, float],
    ):
        """Handle data regeneration request - start background regeneration with progress dialog"""
        rt_description = (
            "per-sample retention times"
            if isinstance(retention_time, dict)
            else f"RT {retention_time:.3f}"
        )
        logger.info(
            f"Data regeneration requested for compound '{compound_name}' "
            f"with tR window {tr_window} centered at {rt_description}"
        )

        try:
            # Build and show progress dialog
            self.regen_progress_dialog = self._build_progress_dialog(
                f"Regenerating EIC data for '{compound_name}'..."
            )
            self.regen_progress_dialog.show()

            # Create background thread and worker
            self._regen_thread = QThread(self)
            pending_regeneration = self.toolbar.integration._pending_session_update
            self._regen_worker = EicRegenerationWorker(
                compound_name,
                tr_window,
                sample_names,
                retention_time,
                pending_regeneration,
                mass_tol=self.mass_tolerance,
            )
            self._regen_worker.moveToThread(self._regen_thread)

            # Connect progress updates
            self._regen_worker.progress.connect(self._update_regeneration_progress)

            # Connect completion/failure handlers
            self._regen_worker.finished.connect(self._regeneration_completed)
            self._regen_worker.failed.connect(self._regeneration_failed)
            self._regen_worker.finished.connect(self._regen_thread.quit)
            self._regen_worker.failed.connect(self._regen_thread.quit)

            # Start the background work
            self._regen_thread.started.connect(self._regen_worker.run)
            self._regen_thread.finished.connect(self._regen_thread.deleteLater)
            self._regen_thread.start()

        except Exception as e:
            logger.error(f"Failed to start regeneration: {e}")
            self._regeneration_failed(
                f"Could not start data regeneration. "
                f"No changes were applied. {e}"
            )

    def _on_mass_tolerance_changed(self, new_mass_tol: float):
        """Handle mass tolerance change - regenerate all EICs with new tolerance"""
        from manic.constants import DEFAULT_RT_WINDOW

        logger.info(f"Starting EIC regeneration with mass tolerance {new_mass_tol} Da")

        try:
            # Disable UI during regeneration
            self.load_cdf_action.setEnabled(False)
            self.load_compound_action.setEnabled(False)
            self.export_data_action.setEnabled(False)
            self.export_method_action.setEnabled(False)

            # Build and show progress dialog
            self.mass_tol_progress_dialog = self._build_progress_dialog(
                f"Regenerating all EICs with mass tolerance {new_mass_tol} Da..."
            )
            self.mass_tol_progress_dialog.show()

            # Create background thread and worker
            self._mass_tol_thread = QThread(self)
            self._mass_tol_worker = MassToleranceReloadWorker(
                mass_tol=new_mass_tol, rt_window=DEFAULT_RT_WINDOW
            )
            self._mass_tol_worker.moveToThread(self._mass_tol_thread)

            # Connect progress updates
            self._mass_tol_worker.progress.connect(self._update_mass_tolerance_progress)

            # Connect completion/failure handlers
            self._mass_tol_worker.finished.connect(
                self._mass_tolerance_reload_completed
            )
            self._mass_tol_worker.failed.connect(self._mass_tolerance_reload_failed)
            self._mass_tol_worker.finished.connect(self._mass_tol_thread.quit)
            self._mass_tol_worker.failed.connect(self._mass_tol_thread.quit)

            # Start the background work
            self._mass_tol_thread.started.connect(self._mass_tol_worker.run)
            self._mass_tol_thread.finished.connect(self._mass_tol_thread.deleteLater)
            self._mass_tol_thread.start()

        except Exception as e:
            logger.error(f"Failed to start mass tolerance reload: {e}")
            self._re_enable_ui_actions()
            msg_box = self._create_message_box(
                "critical",
                "Reload Error",
                f"Failed to start EIC regeneration: {str(e)}",
            )
            msg_box.exec()

    def _update_mass_tolerance_progress(self, current: int, total: int):
        """Update mass tolerance regeneration progress dialog"""
        if hasattr(self, "mass_tol_progress_dialog"):
            pct = int(current / total * 100) if total > 0 else 0
            self.mass_tol_progress_dialog.setMaximum(100)
            self.mass_tol_progress_dialog.setValue(pct)
            self.mass_tol_progress_dialog.setLabelText(
                f"Processing {current} of {total}..."
            )
            QCoreApplication.processEvents()

    def _mass_tolerance_reload_completed(self, regenerated_count: int):
        """Handle successful mass tolerance reload completion"""
        if hasattr(self, "mass_tol_progress_dialog"):
            self.mass_tol_progress_dialog.close()

        logger.info(
            f"Mass tolerance reload completed: {regenerated_count} EICs regenerated"
        )

        # Invalidate caches
        data_provider = DataProvider()
        data_provider.invalidate_cache()

        # Invalidate validation provider cache
        if self._validation_provider is not None:
            self._validation_provider.invalidate_cache()

        # Refresh plots
        current_compound = self.toolbar.get_selected_compound()
        current_samples = self.toolbar.get_selected_samples()
        if current_compound and current_samples:
            self.on_plot_button(current_compound, current_samples)

        # Re-enable UI
        self._re_enable_ui_actions()

        show_status_toast(
            self.statusBar(),
            f"Regenerated {_eics(regenerated_count)} at {self.mass_tolerance} Da mass tolerance",
        )

    def _mass_tolerance_reload_failed(self, error_msg: str):
        """Handle mass tolerance reload failure"""
        if hasattr(self, "mass_tol_progress_dialog"):
            self.mass_tol_progress_dialog.close()

        logger.error(f"Mass tolerance reload failed: {error_msg}")

        # Re-enable UI
        self._re_enable_ui_actions()

        msg_box = self._create_message_box(
            "critical",
            "Regeneration Failed",
            f"Failed to regenerate EICs: {error_msg}",
        )
        msg_box.exec()

    def _re_enable_ui_actions(self):
        """Re-enable UI actions after background operations"""
        self._update_menu_states()

    def _update_regeneration_progress(self, current: int, total: int):
        """Update regeneration progress dialog"""
        if hasattr(self, "regen_progress_dialog"):
            pct = int(current / total * 100) if total > 0 else 0
            self.regen_progress_dialog.setMaximum(100)
            self.regen_progress_dialog.setValue(pct)
            self.regen_progress_dialog.setLabelText(
                f"Processing sample {current} of {total}..."
            )
            QCoreApplication.processEvents()

    def _regeneration_completed(self, regenerated_count: int):
        if hasattr(self, "regen_progress_dialog"):
            self.regen_progress_dialog.close()

        logger.info(
            f"Regeneration completed successfully: {regenerated_count} EICs regenerated"
        )

        try:
            pending_update = self.toolbar.integration._pending_session_update
            if pending_update is not None:
                if pending_update.regenerated_sample_names:
                    logger.info(
                        f"Refreshing bounds for "
                        f"{len(pending_update.regenerated_sample_names)} "
                        f"regenerated samples"
                    )
                    self.toolbar.integration.refresh_data_window_bounds(
                        pending_update.compound_name,
                        list(pending_update.regenerated_sample_names),
                    )

                self.toolbar.integration._pending_session_update = None

            current_compound = self.graph_view.get_current_compound()
            current_selected = self.graph_view.get_selected_samples()
            current_samples = self.graph_view.get_current_samples()

            if current_compound and current_samples:
                if self._validation_provider is not None:
                    self._validation_provider.invalidate_cache()

                self.toolbar.integration.populate_fields_from_plots(
                    current_compound, current_selected, current_samples
                )

                self.toolbar.integration.populate_tr_window_field(current_compound)

                validation_data = self._peak_verdicts(current_compound, current_samples)
                _provider, identity = self._identity_snapshot(
                    current_compound, current_samples
                )
                self.graph_view.refresh_plots_with_session_data(
                    validation_data, identity=identity
                )
                self._refresh_mode_charts(
                    current_compound,
                    current_samples,
                    identity=identity,
                    provider=_provider,
                )
            else:
                self.graph_view.refresh_plots_with_session_data()

            show_status_toast(self.statusBar(), f"Regenerated {_eics(regenerated_count)}")

        except Exception as e:
            self.toolbar.integration._pending_session_update = None
            logger.error(f"Error during post-regeneration refresh: {e}")
            msg_box = self._create_message_box(
                "warning",
                "Plots Did Not Refresh",
                f"The new EIC data was saved, but the display failed: "
                f"{e}\n\nRefresh the plots manually.",
            )
            msg_box.exec()

    def _regeneration_failed(self, error_msg: str):
        if hasattr(self, "regen_progress_dialog"):
            self.regen_progress_dialog.close()

        self.toolbar.integration._pending_session_update = None

        try:
            current_compound = self.graph_view.get_current_compound()
            current_samples = self.graph_view.get_current_samples()
            if current_compound and current_samples:
                self.toolbar.integration.populate_fields_from_plots(
                    current_compound,
                    self.graph_view.get_selected_samples(),
                    current_samples,
                )
                self.toolbar.integration.populate_tr_window_field(current_compound)
        except Exception as e:
            logger.warning(f"Failed to restore integration fields: {e}")

        logger.error(f"Regeneration failed: {error_msg}")
        msg_box = self._create_message_box(
            "critical",
            "Regeneration Blocked",
            error_msg,
        )
        msg_box.exec()

    def export_method(self):
        """Export current analytical session to a file."""
        from PySide6.QtWidgets import QFileDialog

        # Get export file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Analytical Session",
            "manic_session.json",
            "MANIC Session (*.json);;All files (*.*)",
        )

        if not file_path:
            return  # User cancelled

        try:
            success = export_session_method(
                file_path,
                self.analysis_mode,
                internal_standard=self.toolbar.get_internal_standard(),
                internal_standard_reference_isotope=self.internal_standard_reference_isotope,
            )

            if success:
                # Where export_session_method writes, which is not where the user chose.
                chosen = Path(file_path)
                stem = chosen.stem if chosen.suffix.lower() == ".json" else chosen.name
                written = chosen.parent / "manic_session_export" / f"{stem}.json"
                self._show_export_toast(
                    f"Exported {written.name} to {written.parent.name}", written
                )
                logger.info(f"Session exported to {written}")
            else:
                msg_box = self._create_message_box(
                    "critical",
                    "Export Failed",
                    "Failed to export session. Check logs for details.",
                )
                msg_box.exec()

        except Exception as e:
            logger.error(f"Session export error: {e}")
            msg_box = self._create_message_box(
                "critical",
                "Export Error",
                f"An error occurred during export:\n{str(e)}",
            )
            msg_box.exec()

    def import_session(self):
        """Import session overrides from a session file."""
        from PySide6.QtWidgets import QFileDialog

        # Get import file path
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Session Overrides",
            "",
            "MANIC Session (*.json);;All files (*.*)",
        )

        if not file_path:
            return  # User cancelled

        try:
            # Validate method file
            is_valid, error_msg = validate_method_file(
                file_path,
                expected_mode=self.analysis_mode,
            )

            if not is_valid:
                msg_box = self._create_message_box(
                    "warning",
                    "Invalid Session File",
                    f"The selected file is not a valid session file:\n\n{error_msg}",
                )
                msg_box.exec()
                return

            # Get method info to show what will be imported
            method_info = get_method_info(file_path)
            if not method_info:
                msg_box = self._create_message_box(
                    "warning",
                    "Invalid Session File",
                    "Could not read session file information.",
                )
                msg_box.exec()
                return

            has_overrides = method_info["session_override_count"] > 0
            has_deletion_data = method_info.get("has_deletion_data", False)
            deleted_compound_count = method_info.get("deleted_compound_count", 0)
            deleted_sample_count = method_info.get("deleted_sample_count", 0)

            if not has_overrides and not has_deletion_data:
                msg_box = self._create_message_box(
                    "information",
                    "No Session Data",
                    "This session file does not contain any session overrides to import.",
                )
                msg_box.exec()
                return

            # What the session holds and what importing it replaces.
            info_lines = ["Session contains:"]
            if has_overrides:
                info_lines.append(f"• {method_info['session_override_count']} integration overrides")
                info_lines.append(f"• Expected samples: {method_info['expected_sample_count']}")
            if has_deletion_data:
                if deleted_compound_count > 0:
                    info_lines.append(f"• {deleted_compound_count} deleted compound(s)")
                if deleted_sample_count > 0:
                    info_lines.append(f"• {deleted_sample_count} deleted sample(s)")
            info_lines.append("")
            if has_overrides:
                info_lines.append("Any existing session overrides will be replaced.")
            if has_deletion_data:
                info_lines.append("Deleted compounds and samples will match the file.")
            if not self._confirm(
                "Import Session Overrides",
                f"Import {Path(file_path).name}?",
                "\n".join(info_lines),
                "Import Overrides",
            ):
                return

            # Import the session overrides
            success, has_deletion_data = import_session_overrides(
                file_path,
                expected_mode=self.analysis_mode,
            )

            if success:
                restore = self._apply_imported_internal_standard(file_path)
                if not has_deletion_data:
                    legacy_msg = self._create_message_box(
                        "warning",
                        "Legacy Session Format",
                        "This session was exported with an older version of MANIC.",
                        "The session file does not contain deletion information, "
                        "so the deleted/restored state of compounds and samples cannot be synchronized.\n\n"
                        "To include deletion state in future exports, re-export the session with the current version.",
                    )
                    legacy_msg.exec()

                standard_note = format_session_import_standard_note(
                    restore,
                    labelled=self.analysis_mode is AnalysisMode.LABELLED,
                )
                if restore.kind is InternalStandardRestoreKind.FAILED:
                    self._create_message_box(
                        "warning", "Internal Standard Not Restored", standard_note
                    ).exec()
                # Routine success: a toast, with the restored standard when there is one.
                message = f"Imported {Path(file_path).name}"
                if standard_note and restore.kind is not InternalStandardRestoreKind.FAILED:
                    message = f"{message} · {standard_note.rstrip('.')}"
                show_status_toast(self.statusBar(), message, hover=file_path)
                logger.info(f"Session overrides imported from {file_path}")
                self._refresh_after_session_import()
            else:
                msg_box = self._create_message_box(
                    "critical",
                    "Import Failed",
                    "Failed to import session overrides. Check logs for details.",
                )
                msg_box.exec()

        except Exception as e:
            logger.error(f"Session import error: {e}")
            msg_box = self._create_message_box(
                "critical",
                "Import Error",
                f"An error occurred during session import:\n{str(e)}",
            )
            msg_box.exec()

    def update_old_data(self):
        """Rebuild an export from a legacy compounds file and Raw Values workbook."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QFileDialog, QProgressDialog

        from manic.io.legacy_rebuild import rebuild_export_from_files
        from manic.ui.update_old_data_dialog import UpdateOldDataDialog

        dlg = UpdateOldDataDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        compounds_path, raw_values_path = dlg.get_paths()
        if not compounds_path or not raw_values_path:
            return
        internal_standard = dlg.get_internal_standard()

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Rebuilt Export",
            "manic_data_export.xlsx",
            "Excel Workbook (*.xlsx);;All files (*.*)",
        )
        if not out_path:
            return

        progress_dialog = QProgressDialog("Rebuilding data export...", "", 0, 100, self)
        progress_dialog.setWindowTitle("Process External Data")
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setCancelButton(None)

        def progress_cb(val):
            progress_dialog.setValue(int(val))
            QCoreApplication.processEvents()

        try:
            success = rebuild_export_from_files(
                compounds_path,
                raw_values_path,
                out_path,
                internal_standard=internal_standard,
                use_legacy_integration=self.use_legacy_integration,
                progress_callback=progress_cb,
            )
            progress_dialog.setValue(100)
            if success:
                msg = self._create_message_box(
                    "information",
                    "Update Complete",
                    f"Export rebuilt successfully to:\n{out_path}",
                )
                msg.exec()
        except Exception as e:
            logger.error(f"Update Old Data error: {e}")
            progress_dialog.setValue(0)
            msg = self._create_message_box(
                "critical",
                "Update Failed",
                f"Failed to rebuild export.\n{e}",
            )
            msg.exec()

    def _apply_imported_internal_standard(
        self, import_path: str
    ) -> InternalStandardRestore:
        try:
            parsed = read_session_internal_standard(import_path)
            resolved = resolve_session_internal_standard(parsed, list_compound_names())
            if resolved is None:
                return InternalStandardRestore(InternalStandardRestoreKind.UNCHANGED)
            if resolved.compound_name is None:
                self.toolbar.standard.clear_internal_standard()
                isotope = 0
                result = InternalStandardRestore(InternalStandardRestoreKind.CLEARED)
            else:
                compound = read_compound(resolved.compound_name)
                isotope = clamp_reference_isotope(
                    resolved.reference_isotope,
                    compound.channel_count,
                )
                self.toolbar.standard.set_internal_standard(resolved.compound_name)
                result = InternalStandardRestore(
                    InternalStandardRestoreKind.RESTORED,
                    compound_name=resolved.compound_name,
                    reference_isotope=isotope,
                )
            self.internal_standard_reference_isotope = isotope
            if self._validation_provider is not None:
                self._validation_provider.invalidate_cache()
            self._update_menu_states()
            return result
        except Exception:
            logger.exception(
                "Failed to restore internal standard from session import"
            )
            return InternalStandardRestore(InternalStandardRestoreKind.FAILED)

    def _refresh_after_session_import(self):
        """Refresh display after session import if data is currently displayed."""
        try:
            # Refresh compound and sample lists to reflect deletion state changes
            active_compounds = list_compound_names()
            active_samples = list_active_samples()
            self.toolbar.update_compound_list(active_compounds)
            self.toolbar.update_sample_list(active_samples)

            # If we have compound and samples selected, refresh the display
            selected_compound = self.toolbar.get_selected_compound()
            selected_samples = self.toolbar.get_selected_samples()

            if selected_compound and selected_samples:
                # Regenerate the plots with new session data
                self.on_samples_selected(selected_samples)

        except Exception as e:
            logger.error(f"Failed to refresh after session import: {e}")

    def choose_internal_standard(self, global_pos: QPoint) -> None:
        self.toolbar.show_internal_standard_menu(global_pos)

    def open_settings_window(self) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self, host=self)
        self.settings_window.open()

    def open_settings_page(self, title: str) -> None:
        self.open_settings_window()
        pages = self.settings_window.page_list
        for item in pages.findItems(title, Qt.MatchExactly):
            pages.setCurrentItem(item)

    def open_documentation_window(self) -> None:
        if self.documentation_window is None:
            self.documentation_window = DocumentationViewer(self)
        self.documentation_window.open()

    def show_post_load_checklist(self) -> None:
        rows = list_compound_mm_files()
        compound_names = [name for name, _pattern in rows]
        report = build_mm_file_report(rows, DataProvider().resolve_mm_samples)
        if self._post_load_checklist is not None:
            self._post_load_checklist.close()
        dialog = PostLoadChecklistDialog(
            compound_names,
            self.toolbar.get_internal_standard(),
            report,
            self,
            compound_list_path=self.compound_list_path,
            lacking=lacking_amount(compound_names, self.analysis_mode),
        )
        dialog.open_user_guide_requested.connect(self._open_checklist_guide)
        dialog.accepted.connect(self._apply_checklist)
        self._post_load_checklist = dialog
        dialog.open()
        show_over_parent(dialog)

    def _apply_checklist(self) -> None:
        dialog = self._post_load_checklist
        if dialog is None:
            return
        chosen = dialog.selected_internal_standard()
        if chosen == self.toolbar.get_internal_standard():
            return
        if chosen is None:
            self.toolbar.on_internal_standard_cleared()
        else:
            self.toolbar.on_internal_standard_selected(chosen)

    def open_documentation_link(self, href: str) -> None:
        if self.documentation_window is None:
            self.documentation_window = DocumentationViewer(self)
        self.documentation_window.open_link(href)

    def _open_checklist_guide(self) -> None:
        if self.documentation_window is None:
            self.documentation_window = DocumentationViewer(self)
        if self.analysis_mode is AnalysisMode.LABELLED:
            path = Path(docs_path("01_user_guide.md"))
            fragment = "step-3-configure-internal-standard"
        else:
            path = Path(docs_path("Unlabelled_Targeted_Analysis.md"))
            fragment = "additional-columns"
        self.documentation_window.open_at(path, fragment)

    def selected_compound_name(self) -> str | None:
        name = self.toolbar.get_selected_compound()
        if not name or name.startswith("- No"):
            return None
        return name

    def selected_sample_names(self) -> list[str]:
        return self.graph_view.get_selected_samples()

    def qualifier_channels(self, compound_name: str | None) -> list[IonChannel]:
        if not compound_name:
            return []
        try:
            compound = read_compound(compound_name)
        except LookupError:
            return []
        return sorted(
            (
                channel
                for channel in compound.analysis_channels
                if channel.role is IonRole.QUALIFIER
            ),
            key=lambda channel: channel.ordinal,
        )

    def apply_qualifier_tolerances(
        self, compound_name: str, tolerances: dict[int, float | None]
    ) -> None:
        current = {
            channel.ordinal: channel.ratio_tolerance
            for channel in self.qualifier_channels(compound_name)
        }
        changed = {
            ordinal: value
            for ordinal, value in tolerances.items()
            if current.get(ordinal) != value
        }
        if not changed:
            return
        with get_connection() as conn:
            for ordinal, value in changed.items():
                conn.execute(
                    "UPDATE compound_ions SET ratio_tolerance = ? "
                    "WHERE compound_name = ? AND role = 'qualifier' AND ordinal = ?",
                    (value, compound_name, ordinal),
                )
        logger.info(
            "Qualifier tolerances updated for '%s': %s",
            compound_name,
            changed,
        )
        self._replot_current_selection()

    def internal_standard_name(self) -> str | None:
        return self.toolbar.get_internal_standard()

    def internal_standard_label_atoms(self) -> int:
        internal_standard = self.toolbar.get_internal_standard()
        if not internal_standard:
            return 0
        with get_connection() as conn:
            row = conn.execute(
                "SELECT label_atoms FROM compounds WHERE compound_name = ? AND deleted = 0",
                (internal_standard,),
            ).fetchone()
        if row is None or row["label_atoms"] is None:
            return 0
        return max(int(row["label_atoms"]), 0)

    def deconvolution_settings(
        self, compound_name: str | None
    ) -> tuple[str, str, str]:
        if not compound_name:
            return DEFAULT_DECONVOLUTION_LEVEL, "auto", "balanced"
        try:
            compound = read_compound_with_session(compound_name)
        except LookupError:
            # The toolbar can still name a compound that was just deleted.
            return DEFAULT_DECONVOLUTION_LEVEL, "auto", "balanced"
        return (
            normalize_stringency(compound.deconvolution_level),
            normalize_fit_type(compound.deconvolution_fit_type),
            normalize_noise_gate(compound.deconvolution_noise_gate),
        )

    def _replot_current_selection(self) -> None:
        if not (self.cdf_data_loaded and self.compound_data_loaded):
            return
        compound = self.toolbar.get_selected_compound()
        samples = self.toolbar.get_selected_samples()
        if compound and samples:
            self.on_plot_button(compound, samples)

    def apply_mass_tolerance(self, new_value: float) -> None:
        if new_value == self.mass_tolerance:
            return
        logger.info(f"Mass tolerance changed from {self.mass_tolerance} to {new_value} Da")
        self.mass_tolerance = new_value
        if self.cdf_data_loaded:
            self._on_mass_tolerance_changed(new_value)

    def apply_min_peak_area_ratio(self, new_value: float) -> None:
        if new_value == self.min_peak_height_ratio:
            return
        logger.info(
            f"Minimum peak area ratio changed from {self.min_peak_height_ratio:.3f} to {new_value:.3f}"
        )
        self.min_peak_height_ratio = new_value
        self._replot_current_selection()

    def apply_use_legacy_integration(self, enabled: bool) -> None:
        self.use_legacy_integration = enabled
        if self._validation_provider is not None:
            self._validation_provider.set_use_legacy_integration(enabled)
        logger.info(f"Legacy integration mode toggled: {'ON' if enabled else 'OFF'}")
        self._replot_current_selection()

    def apply_nat_abundance_preview(self, enabled: bool) -> None:
        self.preview_nat_abundance = enabled
        logger.info(
            f"Natural abundance correction visualization toggled: {'ON' if enabled else 'OFF'}"
        )
        self.summary.isotopologue_ratios.set_use_corrected(enabled)
        self.graph_view.set_use_corrected(enabled)
        self._replot_current_selection()

    def apply_internal_standard_reference_isotope(self, index: int) -> None:
        if index == self.internal_standard_reference_isotope:
            return
        self.internal_standard_reference_isotope = index
        if self._validation_provider is not None:
            self._validation_provider.invalidate_cache()
        self._replot_current_selection()

    def apply_deconvolution(
        self,
        compound_name: str | None,
        new_level: str,
        new_fit: str,
        new_gate: str,
        apply_to_all: bool,
        replot: bool = True,
    ) -> None:
        if not compound_name:
            return
        if apply_to_all:
            if not self._apply_deconvolution_to_all(new_level, new_fit, new_gate):
                return
        else:
            if (new_level, new_fit, new_gate) == self.deconvolution_settings(compound_name):
                return
            with get_connection() as conn:
                conn.execute(
                    "UPDATE compounds SET deconvolution_level = ?, "
                    "deconvolution_fit_type = ?, deconvolution_noise_gate = ? "
                    "WHERE compound_name = ? AND deleted = 0",
                    (new_level, new_fit, new_gate, compound_name),
                )
            logger.info(
                f"Deconvolution settings updated for '{compound_name}': "
                f"level={new_level}, fit_type={new_fit}, noise_gate={new_gate}"
            )
        if self._validation_provider is not None:
            self._validation_provider.invalidate_cache()
        self.update_deconvolution_indicator(compound_name)
        self.toolbar.sync_selected_peak_scale(self.toolbar.get_selected_compound())
        if replot:
            self._replot_current_selection()

    def on_sample_fit_type_changed(
        self,
        compound_name: str,
        sample_names: list[str],
        fit_type: str | None,
    ) -> None:
        self.apply_sample_fit_types(
            compound_name, {name: fit_type for name in sample_names}
        )

    def apply_sample_fit_types(
        self,
        compound_name: str | None,
        changes: dict[str, str | None],
    ) -> None:
        if not compound_name or not changes:
            return
        grouped: dict[str | None, list[str]] = {}
        for sample_name, fit_type in changes.items():
            grouped.setdefault(fit_type, []).append(sample_name)
        for fit_type, names in grouped.items():
            set_sample_fit_type(compound_name, names, fit_type)
        if self._validation_provider is not None:
            self._validation_provider.invalidate_cache()
        self._replot_current_selection()

    def _apply_deconvolution_to_all(self, new_level: str, new_fit: str, new_gate: str) -> bool:
        """Confirm with the user, then overwrite every compound. False when nothing changed."""
        with get_connection() as conn:
            compound_count = conn.execute(
                "SELECT COUNT(*) FROM compounds WHERE deleted = 0"
            ).fetchone()[0]
        if compound_count == 0:
            return False
        confirm = QMessageBox.question(
            self,
            "Apply to All Compounds",
            f"This will overwrite the deconvolution settings of all "
            f"{compound_count} compound(s) with:\n\n"
            f"    Resolution: {new_level}\n"
            f"    Fit type: {new_fit}\n"
            f"    Noise gate: {new_gate}\n\n"
            f"Existing per-compound settings will be replaced. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return False
        with get_connection() as conn:
            conn.execute(
                "UPDATE compounds SET deconvolution_level = ?, "
                "deconvolution_fit_type = ?, deconvolution_noise_gate = ? "
                "WHERE deleted = 0",
                (new_level, new_fit, new_gate),
            )
        logger.info(
            f"Deconvolution settings applied to all {compound_count} compounds: "
            f"level={new_level}, fit_type={new_fit}, noise_gate={new_gate}"
        )
        return True

    def _deconvolution_indicator_text(self, compound_name: str | None) -> str:
        """Plain-words status-bar text for the selected compound's deconvolution."""
        if not compound_name:
            return ""
        try:
            compound = read_compound_with_session(compound_name)
        except Exception:
            return ""
        level = normalize_stringency(getattr(compound, "deconvolution_level", "off"))
        if level == "off":
            return "Deconvolution off"
        fit_labels = {
            "auto": "automatic peak shape",
            "gaussian": "Gaussian peaks",
            "bi_gaussian": "bi-Gaussian peaks",
            "emg": "EMG peaks",
        }
        fit = fit_labels.get(
            normalize_fit_type(getattr(compound, "deconvolution_fit_type", "auto")),
            "automatic peak shape",
        )
        gate = normalize_noise_gate(
            getattr(compound, "deconvolution_noise_gate", "balanced")
        )
        return f"Deconvolution level {level} · {fit} · {gate} noise gate"

    def update_deconvolution_indicator(self, compound_name: str | None) -> None:
        """Refresh the status-bar deconvolution indicator for the given compound."""
        text = self._deconvolution_indicator_text(compound_name)
        self.deconvolution_indicator_label.setText(text)
        self.deconvolution_indicator_label.setVisible(bool(text))

    def show_about(self):
        """Show About dialog with version information."""
        from manic.ui.about_dialog import AboutDialog

        AboutDialog(self).exec()

    def clear_session(self):
        """Clear all loaded data and reset application state with progress tracking."""
        if self._background_work_running("clearing the session"):
            return

        confirm = self._create_message_box(
            "question",
            "Clear Session",
            "Clear the compound list, raw data, peak window edits and peak reviews?",
            "This cannot be undone.",
        )
        clear_button = confirm.button(QMessageBox.Yes)
        clear_button.setText("Clear Session")
        set_style_property(clear_button, "variant", "danger")
        confirm.button(QMessageBox.No).setText("Cancel")
        # Return must not clear a session by accident.
        confirm.setDefaultButton(QMessageBox.No)
        reply = confirm.exec()

        if reply == QMessageBox.Yes:
            # Create and show progress dialog
            progress = QProgressDialog(
                "Preparing to clear session...", None, 0, 100, self
            )
            progress.setWindowTitle("Clearing Session")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)  # Show immediately
            progress.setCancelButton(None)
            progress.setValue(0)
            progress.show()
            QCoreApplication.processEvents()  # Ensure dialog appears

            try:
                # Temporarily disconnect signals to prevent cascading events during clear
                self.toolbar.samples_selected.disconnect()
                self.toolbar.compound_selected.disconnect()
                self.toolbar.compounds_deleted.disconnect()

                progress.setValue(10)
                progress.setLabelText("Clearing UI state...")
                QCoreApplication.processEvents()

                # Reset UI state flags first
                self.compound_data_loaded = False
                self.compound_list_path = None
                self.cdf_data_loaded = False

                progress.setValue(20)
                progress.setLabelText("Clearing visual elements...")
                QCoreApplication.processEvents()

                # Clear visual elements immediately
                self.graph_view.clear_all_plots()
                self.summary.isotopologue_ratios._clear_chart()
                self.summary.total_abundance._clear_chart()
                self.summary.targeted_qc.clear()

                # Force UI update to show cleared graphs
                self.graph_view.repaint()

                progress.setValue(30)
                progress.setLabelText("Clearing data lists...")
                QCoreApplication.processEvents()

                # Clear data lists
                self.toolbar.update_compound_list([])
                self.toolbar.update_sample_list([])
                self.toolbar.update_label_colours(False, False)

                # Clear internal standard
                self.toolbar.standard.clear_internal_standard()

                # Clear integration window
                self.toolbar.integration.populate_fields(None)

                progress.setValue(40)
                progress.setLabelText("Clearing database...")
                QCoreApplication.processEvents()

                # Define progress callback for database clearing
                def db_progress_callback(current, total, operation):
                    # Map database progress to 40-90% of total progress
                    db_progress_percent = int(40 + (current / total) * 50)
                    progress.setValue(db_progress_percent)
                    progress.setLabelText(operation)

                    # OPTIMIZATION: Reduce UI update frequency for better performance
                    # Only update UI every 25% or on operation changes
                    if (
                        current == 0
                        or current == total
                        or db_progress_percent % 25 == 0
                    ):
                        QCoreApplication.processEvents()

                # Clear the database with progress tracking (fast mode enabled by default)
                clear_database(progress_callback=db_progress_callback)

                progress.setValue(90)
                progress.setLabelText("Reconnecting signals...")
                QCoreApplication.processEvents()

                # Reconnect signals
                self.toolbar.samples_selected.connect(self.on_samples_selected)
                self.toolbar.compound_selected.connect(self.on_compound_selected)
                self.toolbar.compounds_deleted.connect(self.on_compounds_deleted)

                # Update menu states
                self._update_menu_states()

                progress.setValue(100)
                progress.setLabelText("Session clearing complete")
                QCoreApplication.processEvents()

                # Close progress dialog
                progress.close()

                show_status_toast(self.statusBar(), "Session cleared")

                logger.info("Session cleared successfully")

            except Exception as e:
                # Close progress dialog
                progress.close()

                # Ensure signals are reconnected even if clearing fails
                try:
                    self.toolbar.samples_selected.connect(self.on_samples_selected)
                    self.toolbar.compound_selected.connect(self.on_compound_selected)
                    self.toolbar.compounds_deleted.connect(self.on_compounds_deleted)
                except Exception as ex:
                    pass  # Signals might already be connected
                    logger.error(f"{ex}")

                logger.error(f"Failed to clear session: {e}")
                msg_box = self._create_message_box(
                    "critical",
                    "Clear Session Failed",
                    f"Failed to clear session: {str(e)}",
                )
                msg_box.exec()

    def export_data(self):
        """
        Export processed data to Excel with 6 worksheets.

        IMPORTANT: This export function is completely independent of the UI toggle state
        for natural isotope correction. The Corrected Values sheet will ALWAYS contain
        properly corrected data, regardless of whether the user has the correction toggle
        enabled in the UI for visualization purposes.

        The UI toggle only controls what data is displayed in graphs. The export always
        uses the scientifically correct data:
        - Raw Values sheet: Uncorrected instrument signals
        - Corrected Values sheet: Natural isotope abundance corrected signals

        If corrections have not yet been applied to the database (because the user never
        toggled the correction on in the UI), they will be automatically applied before
        export to ensure data integrity.
        """
        try:
            options = ExportOptionsDialog(
                self.use_legacy_integration,
                self.analysis_mode is AnalysisMode.LABELLED,
                self,
            )
            if options.exec() != QDialog.Accepted:
                return  # user cancelled

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Data to Excel",
                "manic_data_export.xlsx",
                "Excel Files (*.xlsx);;All Files (*)",
            )

            if not file_path:
                return  # User cancelled

            # Ensure .xlsx extension
            if not file_path.lower().endswith(".xlsx"):
                file_path += ".xlsx"

            # Read selection and persist to window state
            self.use_legacy_integration = options.use_legacy_integration()
            include_carbon_enrichment = options.include_carbon_enrichment()

            # Get current internal standard selection from toolbar
            internal_standard = self.toolbar.get_internal_standard()

            internal_standard_for_export = internal_standard

            if not internal_standard:
                if not self._confirm(
                    "No Internal Standard Selected",
                    "You have not selected an internal standard. Export anyway?",
                    (
                        "Results will contain quantifier-ion peak areas."
                        if self.analysis_mode is AnalysisMode.UNLABELLED
                        else "Abundances will be peak areas, summed over the "
                        "corrected isotopologues."
                    ),
                    "Export",
                ):
                    return
            elif self.analysis_mode is AnalysisMode.LABELLED:
                ok, problems = validate_internal_standard_metadata(
                    DataProvider(use_legacy_integration=self.use_legacy_integration),
                    internal_standard,
                )
                if not ok:
                    missing = " or ".join(
                        words
                        for field, words in (
                            ("int_std_amount", "internal-standard amount"),
                            ("amount_in_std_mix", "amount in the standard mix"),
                        )
                        if any(field in problem for problem in problems)
                    )
                    if not self._confirm(
                        "No Internal-Standard Amount",
                        (
                            f"{internal_standard} has no {missing} in the compound list. "
                            if missing
                            else f"{internal_standard} is not in the compound list. "
                        )
                        + "Export peak areas instead?",
                        "Add it to the compound list and import the list again "
                        "to export calibrated abundances.",
                        "Export Peak Areas",
                    ):
                        return
                    internal_standard_for_export = None

            progress_dialog = QProgressDialog(
                "Exporting data to Excel...", "Cancel", 0, 100, self
            )
            progress_dialog.setWindowTitle("Data Export")
            progress_dialog.setMinimumDuration(0)
            progress_dialog.setModal(True)
            progress_dialog.setValue(0)

            exporter = DataExporter(self.analysis_mode)
            exporter.set_internal_standard(internal_standard_for_export)
            exporter.set_use_legacy_integration(self.use_legacy_integration)
            exporter.set_min_peak_area_ratio(self.min_peak_height_ratio)
            exporter.set_internal_standard_reference_isotope(
                self.internal_standard_reference_isotope
            )

            self._export_path = file_path
            self._export_progress_dialog = progress_dialog
            self._export_thread = QThread(self)
            self._export_worker = ExportWorker(
                exporter,
                file_path,
                use_legacy_integration=self.use_legacy_integration,
                include_carbon_enrichment=include_carbon_enrichment,
            )
            self._export_worker.moveToThread(self._export_thread)
            # The worker thread is busy inside run(), so a queued call to
            # cancel() would never be delivered. Direct connections let
            # cancel() and quit() cross threads without an event loop.
            progress_dialog.canceled.connect(
                self._export_worker.cancel, Qt.DirectConnection
            )
            self._export_worker.progress.connect(progress_dialog.setValue)
            self._export_worker.finished.connect(self._export_finished)
            self._export_worker.failed.connect(self._export_failed)
            self._export_worker.finished.connect(
                self._export_thread.quit, Qt.DirectConnection
            )
            self._export_worker.failed.connect(
                self._export_thread.quit, Qt.DirectConnection
            )
            self._export_thread.started.connect(self._export_worker.run)
            self._export_thread.finished.connect(self._clear_export_thread)
            self._export_thread.finished.connect(self._export_thread.deleteLater)

            progress_dialog.show()
            self._export_thread.start()
            self._update_menu_states()

        except Exception as e:
            logger.error(f"Data export error: {e}")
            msg_box = self._create_message_box(
                "critical",
                "Export Error",
                f"An error occurred during data export:\n{str(e)}",
            )
            msg_box.exec()

    def _show_export_toast(self, message: str, written: Path) -> None:
        show_status_toast(
            self.statusBar(),
            message,
            action=(
                "Show in Folder",
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(written.parent))),
            ),
            hover=str(written),
        )

    def _clear_export_thread(self):
        self._export_thread = None

    def _close_export_dialog(self):
        if self._export_progress_dialog is not None:
            self._export_progress_dialog.close()
            self._export_progress_dialog = None

    def _export_finished(self, success: bool):
        self._close_export_dialog()
        if success:
            path = Path(self._export_path)
            self._show_export_toast(f"Exported {path.name}", path)
            logger.info(f"Data exported successfully to {path}")
        else:
            show_status_toast(self.statusBar(), "Export cancelled")
            logger.info("Data export was cancelled")
        self._update_menu_states()

    def _export_failed(self, message: str):
        self._close_export_dialog()
        logger.error(f"Data export error: {message}")
        msg_box = self._create_message_box(
            "critical",
            "Export Error",
            f"An error occurred during data export:\n{message}",
        )
        msg_box.exec()
        self._update_menu_states()
