import logging
import os
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QThread
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from manic.__version__ import APP_NAME, __version__
from manic.io.compounds_import import import_compound_excel
from manic.io.data_exporter import DataExporter
from manic.io.list_compound_names import list_compound_names
from manic.io.sample_reader import list_active_samples
from manic.models.database import clear_database, get_connection, soft_delete_compound
from manic.ui.documentation_viewer import show_documentation_file
from manic.ui.graphs import GraphView
from manic.ui.left_toolbar import Toolbar
from manic.ui.recovery_dialog import RecoveryDialog
from manic.utils.paths import docs_path, resource_path
from manic.utils.utils import load_stylesheet
from manic.utils.workers import (
    CdfImportWorker,
    EicRegenerationWorker,
    MassToleranceReloadWorker,
)
from src.manic.utils.timer import measure_time

logger = logging.getLogger("manic_logger")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.setObjectName("mainWindow")

        # Flag to prevent cascading compound deletion events
        self._deleting_compound = False

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

        # Minimum peak height setting (as ratio of internal standard height)
        self.min_peak_height_ratio = 0.05

        # Integration method setting
        self.use_legacy_integration = False  # Time-based by default
        self.compound_data_loaded = False
        self.cdf_data_loaded = False

        # Cached DataProvider for validation (reused to avoid repeated bulk loads)
        self._validation_provider = None

        self.setup_ui()

        # Load and apply the stylesheet
        stylesheet = load_stylesheet(resource_path("resources", "style.qss"))
        self.setStyleSheet(stylesheet)

        # Connect toolbar signals (avoid duplicate connections; others are set in setup_ui)
        self.toolbar.internal_standard_selected.connect(
            self.on_internal_standard_selected
        )
        self.toolbar.compound_deleted.connect(self.on_compound_deleted)

    def setup_ui(self):
        """
        Set up the application UI.
        """

        # Create the main layout
        main_layout = QHBoxLayout()

        # Create the toolbar
        self.toolbar = Toolbar()
        self.toolbar.setObjectName("toolbar")
        main_layout.addWidget(self.toolbar)

        # Create the graph view
        self.graph_view = GraphView()
        main_layout.addWidget(self.graph_view)
        main_layout.setStretch(1, 1)

        # Set the main layout as the central widget
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Create menu bar
        menu_bar = QMenuBar()

        """ Create File Menu """

        # Initiate the file menu
        file_menu = menu_bar.addMenu("File")

        # Create the actions/logic for loading compound list data
        self.load_compound_action = QAction("Load Compounds/Parameter List", self)
        self.load_compound_action.triggered.connect(self.load_compound_list_data)
        # Add the load compound action/logic to the file menu
        file_menu.addAction(self.load_compound_action)

        # Create the actions/logic for loading CDF files
        self.load_cdf_action = QAction("Load Raw Data (CDF)", self)
        self.load_cdf_action.triggered.connect(self.load_cdf_files)
        # Add the load CDF action/logic to the file menu
        file_menu.addAction(self.load_cdf_action)

        # Add a separator to the file menu
        file_menu.addSeparator()

        # Create method export/import actions
        self.export_method_action = QAction("Export Session...", self)
        self.export_method_action.triggered.connect(self.export_method)
        file_menu.addAction(self.export_method_action)

        self.import_session_action = QAction("Import Session...", self)
        self.import_session_action.triggered.connect(self.import_session)
        file_menu.addAction(self.import_session_action)

        # Create the Clear Session action
        self.clear_session_action = QAction("Clear Session", self)
        self.clear_session_action.triggered.connect(self.clear_session)
        # Add the clear session action to the file menu
        file_menu.addAction(self.clear_session_action)

        # Add separator before recovery and export
        file_menu.addSeparator()

        # Recovery dialog action
        self.recovery_action = QAction("Recover Deleted Compounds...", self)
        self.recovery_action.triggered.connect(self.show_recovery_dialog)
        file_menu.addAction(self.recovery_action)

        # Add separator before export data
        file_menu.addSeparator()

        # Create export data action
        self.export_data_action = QAction("Export Data...", self)
        self.export_data_action.triggered.connect(self.export_data)
        file_menu.addAction(self.export_data_action)

        # Add separator and Update Old Data action
        file_menu.addSeparator()
        self.update_old_data_action = QAction("Update Old Data...", self)
        self.update_old_data_action.triggered.connect(self.update_old_data)
        file_menu.addAction(self.update_old_data_action)

        """ Create Settings Menu """

        settings_menu = menu_bar.addMenu("Settings")

        self.mass_tolerance_action = QAction("Mass Tolerance...", self)
        self.mass_tolerance_action.triggered.connect(self.show_mass_tolerance_dialog)
        settings_menu.addAction(self.mass_tolerance_action)

        self.min_peak_height_action = QAction("Minimum Peak Area...", self)
        self.min_peak_height_action.triggered.connect(self.show_min_peak_height_dialog)
        settings_menu.addAction(self.min_peak_height_action)

        # Natural abundance correction toggle action
        self.nat_abundance_toggle = QAction("Natural Abundance Correction: Off", self)
        self.nat_abundance_toggle.setCheckable(True)
        self.nat_abundance_toggle.setChecked(False)  # Off by default
        self.nat_abundance_toggle.triggered.connect(
            self.toggle_natural_abundance_correction
        )
        settings_menu.addAction(self.nat_abundance_toggle)

        # Legacy integration mode toggle action
        self.legacy_integration_toggle = QAction("Legacy Integration Mode: Off", self)
        self.legacy_integration_toggle.setCheckable(True)
        self.legacy_integration_toggle.setChecked(False)  # Off by default
        self.legacy_integration_toggle.triggered.connect(
            self.toggle_legacy_integration_mode
        )
        settings_menu.addAction(self.legacy_integration_toggle)

        """ Create Documentation Menu """

        docs_menu = menu_bar.addMenu("Documentation")
        self._create_documentation_menu(docs_menu)

        """ Create Help Menu """

        help_menu = menu_bar.addMenu("Help")

        self.about_action = QAction("About MANIC...", self)
        self.about_action.triggered.connect(self.show_about)
        help_menu.addAction(self.about_action)

        # Set the menu bar to the QMainWindow
        self.setMenuBar(menu_bar)

        # Initialize menu states
        self._update_menu_states()

        # Initialize natural abundance correction state
        self.toolbar.isotopologue_ratios.set_use_corrected(False)  # Off by default

        # Connect the toolbar's custom signals to handler methods
        self.toolbar.samples_selected.connect(self.on_samples_selected)
        self.toolbar.compound_selected.connect(self.on_compound_selected)

        # Connect the graph view's selection signal
        self.graph_view.selection_changed.connect(self.on_plot_selection_changed)

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

    def _show_question_dialog(
        self, title: str, text: str, informative_text: str = "", parent=None
    ) -> int:
        """Show a question dialog and return the result (QMessageBox.Yes or QMessageBox.No)."""
        msg_box = self._create_message_box(
            "question", title, text, informative_text, parent
        )
        return msg_box.exec()

    def _update_menu_states(self):
        """Update menu item enabled/disabled states based on current data state."""
        # Load Compound Data: enabled only if not yet loaded
        self.load_compound_action.setEnabled(not self.compound_data_loaded)

        # Load CDF Data: enabled only if compound data loaded but CDF not loaded
        self.load_cdf_action.setEnabled(
            self.compound_data_loaded and not self.cdf_data_loaded
        )

        # Export Session: enabled if compound data loaded
        self.export_method_action.setEnabled(self.compound_data_loaded)

        # Export Data: enabled only if compound data, CDF data loaded, AND internal standard selected
        internal_standard = self.toolbar.get_internal_standard()
        has_internal_standard = (
            internal_standard is not None and internal_standard != ""
        )
        self.export_data_action.setEnabled(
            self.compound_data_loaded and self.cdf_data_loaded and has_internal_standard
        )

        # Import Session: enabled only if both compound and CDF data loaded
        self.import_session_action.setEnabled(
            self.compound_data_loaded and self.cdf_data_loaded
        )

        # Clear Session: enabled if any data loaded
        self.clear_session_action.setEnabled(
            self.compound_data_loaded or self.cdf_data_loaded
        )

        # Add tooltips to disabled items
        if self.compound_data_loaded:
            self.load_compound_action.setToolTip(
                "Compound data already loaded. Use 'Clear Session' to start over."
            )
        else:
            self.load_compound_action.setToolTip(
                "Load compound list and parameter data"
            )

        if not self.compound_data_loaded:
            self.load_cdf_action.setToolTip(
                "Load compound data first before loading raw data"
            )
        elif self.cdf_data_loaded:
            self.load_cdf_action.setToolTip(
                "Raw data already loaded. Use 'Clear Session' to start over."
            )
        else:
            self.load_cdf_action.setToolTip("Load raw CDF data files")

        # Import Session tooltips
        if not self.compound_data_loaded:
            self.import_session_action.setToolTip("Load compound data first")
        elif not self.cdf_data_loaded:
            self.import_session_action.setToolTip(
                "Load CDF data before importing session"
            )
        else:
            self.import_session_action.setToolTip(
                "Import session-specific integration overrides"
            )

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

    def load_compound_list_data(self: QMainWindow) -> None:
        """
        1. Prompt the user to select a compound list file.
        2. Call the load_compound_list controller function to load the compound list.

        """
        from pathlib import Path

        default_dir = str(Path.home() / "Documents")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Compound List",
            default_dir,
            "Excel/CSV Files (*.xls *.xlsx *.csv)",
        )
        if not file_path:
            return

        try:
            self.compounds_data_storage = import_compound_excel(file_path)
            self.toolbar.update_label_colours(False, True)
            self.toolbar.update_compound_list(list_compound_names())

            # Auto-select scyllo-inositol as internal standard if available
            self._auto_select_scyllo_inositol()

            # Update state and menu
            self.compound_data_loaded = True
            self._update_menu_states()

        except Exception as e:
            msg_box = self._create_message_box("warning", "Error", str(e))
            msg_box.exec()

    def load_cdf_files(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory Containing CDF Files"
        )
        if not directory:
            return

        # build dialog & worker
        self.progress_dialog = self._build_progress_dialog("Importing CDF data…")
        self.progress_dialog.show()

        self._thread = QThread(self)  # background thread
        self._worker = CdfImportWorker(directory, self.mass_tolerance)  # heavy lifting
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
        msg_box = self._create_message_box(
            "information", "Import OK", f"Data for {rows} EICs successfully extracted."
        )
        msg_box.exec()
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

    def _import_fail(self, msg: str):
        self.progress_dialog.close()
        msg_box = self._create_message_box("critical", "Import failed", msg)
        msg_box.exec()

    def _validate_peak_area(self, compound_name: str, sample_name: str) -> bool:
        """
        Validate if the compound's total peak area meets the minimum threshold.

        This method compares the sum of all isotopologue peak areas for the compound
        against a threshold calculated as: internal_standard_total × min_peak_height_ratio.

        Both the compound and internal standard use their own integration boundaries
        (retention time ± offsets), which respect session overrides.

        Args:
            compound_name: Name of the compound being validated
            sample_name: Name of the sample

        Returns:
            True if compound total area >= threshold, False otherwise
        """
        internal_standard = self.toolbar.get_internal_standard()
        if not internal_standard:
            return True

        try:
            if self._validation_provider is None:
                from manic.io.data_provider import DataProvider

                self._validation_provider = DataProvider(
                    use_legacy_integration=self.use_legacy_integration
                )

            return self._validation_provider.validate_peak_area(
                sample_name,
                compound_name,
                internal_standard,
                self.min_peak_height_ratio,
            )

        except Exception as e:
            logger.warning(
                f"Peak area validation failed for {compound_name}/{sample_name}: {e}"
            )
            return True

    def on_plot_button(self, compound_name, samples):
        # Validate inputs before plotting
        if not compound_name or compound_name.startswith("- No"):
            return  # Don't plot with placeholder compound

        if not samples or any(sample.startswith("- No") for sample in samples):
            return  # Don't plot with placeholder samples

        try:
            if samples:
                with measure_time("total_plotting_speed"):
                    # Calculate validation data for all samples
                    validation_data = {}
                    if self.min_peak_height_ratio > 0:  # Only if validation is enabled
                        for sample in samples:
                            validation_data[sample] = self._validate_peak_area(
                                compound_name, sample
                            )

                    self.graph_view.plot_compound(
                        compound_name, samples, validation_data
                    )

                # After plotting, update integration window to show "All" state
                # (no plots selected initially)
                self.toolbar.integration.populate_fields_from_plots(
                    compound_name,
                    [],  # No plots selected initially
                    samples,  # All visible samples
                )

                # Update tR window field only when compound changes
                self.toolbar.integration.populate_tr_window_field(compound_name)

                # Update isotopologue ratios first (calculates both ratios and abundances)
                current_eics = self._get_current_eics()
                self.toolbar.isotopologue_ratios.update_ratios(
                    compound_name, current_eics
                )

                # Share the calculated abundances with total abundance widget (no recalculation)
                abundances, eics = (
                    self.toolbar.isotopologue_ratios.get_last_total_abundances()
                )
                if abundances is not None:
                    self.toolbar.total_abundance.update_abundance_from_data(
                        compound_name, eics, abundances
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

    def on_compound_selected(self, compound_selected):
        """
        This method will be called whenever a different compound is selected in the toolbar.
        'selected_text' is the text of the selected item (passed from the signal).
        """
        samples = self.toolbar.get_selected_samples()
        self.on_plot_button(compound_selected, samples)

    def on_compound_deleted(self, compound_name: str):
        """
        This method will be called when a compound is deleted.
        Updates the compound list and selects the next available compound.
        """
        # Prevent cascading deletion events
        if self._deleting_compound:
            return

        self._deleting_compound = True

        try:
            # Perform soft delete in database
            if soft_delete_compound(compound_name):
                # Get updated compound list
                active_compounds = list_compound_names()

                # Clear the graph view first before updating the list
                self.graph_view.clear_all_plots()

                # Force complete UI refresh to eliminate any visual artifacts
                from PySide6.QtCore import QCoreApplication

                QCoreApplication.processEvents()
                self.graph_view.update()
                self.graph_view.repaint()
                QCoreApplication.processEvents()

                # Update compound list (signals are blocked during update)
                self.toolbar.update_compound_list(active_compounds)

                logger.info(f"Compound '{compound_name}' deleted successfully.")

                if not active_compounds:
                    logger.info("No compounds remaining after deletion.")
            else:
                logger.error(
                    f"Failed to delete compound '{compound_name}' from database"
                )
        except Exception as e:
            logger.error(f"Error during compound deletion: {e}")
        finally:
            # Always reset the flag
            self._deleting_compound = False

    def on_samples_selected(self, samples_selected):
        compound = self.toolbar.get_selected_compound()
        self.on_plot_button(compound, samples_selected)

    def _auto_select_scyllo_inositol(self):
        """
        Automatically select scyllo-inositol as internal standard if available
        and it has a non-zero internal standard amount.
        """
        with get_connection() as conn:
            # Look for scyllo-inositol with non-zero internal standard amount
            row = conn.execute("""
                SELECT compound_name
                FROM compounds
                WHERE compound_name LIKE '%scyllo%ins%'
                AND int_std_amount IS NOT NULL
                AND int_std_amount > 0
                AND deleted = 0
                LIMIT 1
            """).fetchone()

            if row:
                compound_name = row["compound_name"]
                # Auto-select it as internal standard (this will emit the signal and update the indicator)
                self.toolbar.on_internal_standard_selected(compound_name)
                print(f"Auto-selected {compound_name} as internal standard")  # Debug
                return True
        return False

    def on_internal_standard_selected(self, internal_standard):
        """
        Handle internal standard selection changes.
        Updates menu states when internal standard is selected/deselected.
        """
        # Update menu states to enable/disable Export Data based on internal standard selection
        self._update_menu_states()

    def on_plot_selection_changed(self, selected_samples):
        """Handle when plots are selected/deselected"""
        # Update integration window based on plot selection
        current_compound = self.graph_view.get_current_compound()
        all_samples = self.graph_view.get_current_samples()

        if current_compound:
            self.toolbar.integration.populate_fields_from_plots(
                current_compound, selected_samples, all_samples
            )

            # Update isotopologue ratios and total abundance (integration parameters may have changed)
            current_eics = self._get_current_eics()
            self.toolbar.isotopologue_ratios.update_ratios(
                current_compound, current_eics
            )

            # Share calculated abundances
            abundances, eics = (
                self.toolbar.isotopologue_ratios.get_last_total_abundances()
            )
            if abundances is not None:
                self.toolbar.total_abundance.update_abundance_from_data(
                    current_compound, eics, abundances
                )

    def on_session_data_applied(self, compound_name: str, sample_names: list):
        """Handle when session data is applied - refresh plots to show updated parameters"""
        logger.info(f"Session data applied for {compound_name}, refreshing plots")

        try:
            # Invalidate validation provider cache since integration boundaries changed
            if self._validation_provider is not None:
                self._validation_provider.invalidate_cache()

            # Re-validate with new session data
            validation_data = {}
            if self.min_peak_height_ratio > 0:
                current_samples = self.graph_view.get_current_samples()
                for sample in current_samples:
                    validation_data[sample] = self._validate_peak_area(
                        compound_name, sample
                    )

            # Refresh plots with session data and updated validation
            self.graph_view.refresh_plots_with_session_data(validation_data)

            # After refreshing plots, update the integration window to show the new values
            # Add a small delay to ensure the plot refresh is fully complete
            from PySide6.QtCore import QTimer

            def update_integration_window():
                current_selected = self.graph_view.get_selected_samples()
                all_samples = self.graph_view.get_current_samples()

                if compound_name:
                    self.toolbar.integration.populate_fields_from_plots(
                        compound_name, current_selected, all_samples
                    )

            # Use a timer to delay the update slightly
            QTimer.singleShot(100, update_integration_window)

            # Update isotopologue ratios and total abundance with new integration parameters
            def update_charts():
                current_eics = self._get_current_eics()
                self.toolbar.isotopologue_ratios.update_ratios(
                    compound_name, current_eics
                )

                # Share calculated abundances
                abundances, eics = (
                    self.toolbar.isotopologue_ratios.get_last_total_abundances()
                )
                if abundances is not None:
                    self.toolbar.total_abundance.update_abundance_from_data(
                        compound_name, eics, abundances
                    )

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
            # Refresh plots with default data (session data has been removed)
            self.graph_view.refresh_plots_with_session_data()

            # After refreshing plots, update the integration window to show the default values
            from PySide6.QtCore import QTimer

            def update_integration_window():
                current_selected = self.graph_view.get_selected_samples()
                all_samples = self.graph_view.get_current_samples()

                if compound_name:
                    self.toolbar.integration.populate_fields_from_plots(
                        compound_name, current_selected, all_samples
                    )

            # Use a timer to delay the update slightly
            QTimer.singleShot(100, update_integration_window)

            # Update isotopologue ratios and total abundance with restored default parameters
            def update_charts():
                current_eics = self._get_current_eics()
                self.toolbar.isotopologue_ratios.update_ratios(
                    compound_name, current_eics
                )

                # Share calculated abundances
                abundances, eics = (
                    self.toolbar.isotopologue_ratios.get_last_total_abundances()
                )
                if abundances is not None:
                    self.toolbar.total_abundance.update_abundance_from_data(
                        compound_name, eics, abundances
                    )

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

    def on_data_regeneration_requested(
        self,
        compound_name: str,
        tr_window: float,
        sample_names: list,
        retention_time: float,
    ):
        """Handle data regeneration request - start background regeneration with progress dialog"""
        logger.info(
            f"Data regeneration requested for compound '{compound_name}' with tR window {tr_window} centered at RT {retention_time:.3f}"
        )

        try:
            # Build and show progress dialog
            self.regen_progress_dialog = self._build_progress_dialog(
                f"Regenerating EIC data for '{compound_name}'..."
            )
            self.regen_progress_dialog.show()

            # Create background thread and worker
            self._regen_thread = QThread(self)
            self._regen_worker = EicRegenerationWorker(
                compound_name, tr_window, sample_names, retention_time
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
            msg_box = self._create_message_box(
                "critical",
                "Regeneration Error",
                f"Failed to start data regeneration: {str(e)}",
            )
            msg_box.exec()

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
        from manic.io.data_provider import DataProvider

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

        # Show success message
        msg = self._create_message_box(
            "info",
            "Regeneration Complete",
            f"Successfully regenerated {regenerated_count} EICs with new mass tolerance {self.mass_tolerance} Da.",
        )
        msg.exec()

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
        self.load_cdf_action.setEnabled(True)
        self.load_compound_action.setEnabled(True)
        # Re-enable export actions based on data state
        self.export_method_action.setEnabled(self.compound_data_loaded)
        self.export_data_action.setEnabled(
            self.cdf_data_loaded and self.compound_data_loaded
        )

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
        """Handle successful regeneration completion"""
        if hasattr(self, "regen_progress_dialog"):
            self.regen_progress_dialog.close()

        logger.info(
            f"Regeneration completed successfully: {regenerated_count} EICs regenerated"
        )

        try:
            # Check if there's a pending session update from Apply button (auto-reload feature)
            if (
                hasattr(self.toolbar.integration, "_pending_session_update")
                and self.toolbar.integration._pending_session_update is not None
            ):
                # Apply the pending session update now that data has been reloaded
                retention_time, loffset, roffset, samples_to_apply = (
                    self.toolbar.integration._pending_session_update
                )

                from manic.models.session_activity import SessionActivityService

                SessionActivityService.update_session_data(
                    compound_name=self.graph_view.get_current_compound(),
                    sample_names=samples_to_apply,
                    retention_time=retention_time,
                    loffset=loffset,
                    roffset=roffset,
                )

                # Refresh data window bounds for the regenerated samples
                # Use the list of samples that were actually regenerated, not all samples_to_apply
                current_compound = self.graph_view.get_current_compound()
                samples_regenerated = getattr(
                    self.toolbar.integration, "_samples_regenerated", []
                )
                if samples_regenerated:
                    logger.info(
                        f"Refreshing bounds for {len(samples_regenerated)} regenerated samples"
                    )
                    self.toolbar.integration.refresh_data_window_bounds(
                        current_compound, samples_regenerated
                    )
                else:
                    logger.warning(
                        "No samples_regenerated list found, skipping bounds refresh"
                    )

                # Clear the pending update and regenerated list
                self.toolbar.integration._pending_session_update = None
                self.toolbar.integration._samples_regenerated = []

                logger.info(
                    f"Applied pending session update after EIC reload: RT={retention_time:.3f}, loffset={loffset:.3f}, roffset={roffset:.3f}"
                )

            # Update integration window BEFORE refreshing plots
            # This ensures the plots draw RT lines at the correct (updated) positions
            current_compound = self.graph_view.get_current_compound()
            current_selected = self.graph_view.get_selected_samples()
            current_samples = self.graph_view.get_current_samples()

            if current_compound and current_samples:
                # Update integration window fields with new session data (RT, loffset, roffset)
                self.toolbar.integration.populate_fields_from_plots(
                    current_compound, current_selected, current_samples
                )

                # Update tR window field with the ACTUAL persisted value from EIC table
                # (Don't use the old value - use the new regenerated RT window)
                self.toolbar.integration.populate_tr_window_field(current_compound)

                # NOW replot with fresh EIC data and updated integration parameters
                # The plots will draw RT lines at the correct new positions
                validation_data = {}
                if self.min_peak_height_ratio > 0:  # Only if validation is enabled
                    for sample in current_samples:
                        validation_data[sample] = self._validate_peak_area(
                            current_compound, sample
                        )
                self.graph_view.refresh_plots_with_session_data(validation_data)
            else:
                # Fallback to session data refresh
                self.graph_view.refresh_plots_with_session_data()

            # Show success message
            msg_box = self._create_message_box(
                "information",
                "Regeneration Complete",
                f"Data regeneration completed successfully!\n\n"
                f"Regenerated {regenerated_count} EIC records.\n"
                f"Plots have been refreshed with new data.",
            )
            msg_box.exec()

        except Exception as e:
            logger.error(f"Error during post-regeneration refresh: {e}")
            msg_box = self._create_message_box(
                "warning",
                "Regeneration Complete with Warning",
                f"Data regeneration completed ({regenerated_count} EICs), "
                f"but plot refresh failed: {str(e)}\n\n"
                f"Try manually refreshing the plots.",
            )
            msg_box.exec()

    def _regeneration_failed(self, error_msg: str):
        """Handle regeneration failure"""
        if hasattr(self, "regen_progress_dialog"):
            self.regen_progress_dialog.close()

        logger.error(f"Regeneration failed: {error_msg}")
        msg_box = self._create_message_box(
            "critical",
            "Regeneration Failed",
            f"Data regeneration failed:\n\n{error_msg}\n\n"
            f"Please check the log files for more details.",
        )
        msg_box.exec()

    def export_method(self):
        """Export current analytical session to a file."""
        from PySide6.QtWidgets import QFileDialog

        from manic.models.session_export import export_session_method

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
            success = export_session_method(file_path)

            if success:
                # Show info about what was exported
                # Extract base name to show directory structure
                from pathlib import Path

                export_path = Path(file_path)
                if export_path.suffix.lower() == ".json":
                    base_name = export_path.stem
                else:
                    base_name = export_path.name
                export_dir = export_path.parent / f"manic_export_{base_name}"

                info_text = (
                    f"Analytical session exported successfully!\n\n"
                    f"Export Directory: {export_dir}\n\n"
                    f"Files created:\n"
                    f"• {base_name}.json - Machine-readable session data\n"
                    f"• changelog.md - Human-readable summary\n\n"
                    f"The export contains compound definitions and analysis parameters only. "
                    f"To use this session, follow the 3-step import process described in the changelog."
                )
                msg_box = self._create_message_box(
                    "information", "Session Export Successful", info_text
                )
                msg_box.exec()
                logger.info(f"Session exported to {export_dir}")
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

        from manic.models.session_export import (
            get_method_info,
            import_session_overrides,
            validate_method_file,
        )

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
            is_valid, error_msg = validate_method_file(file_path)

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
            if method_info and method_info["session_override_count"] > 0:
                info_text = (
                    f"Session contains:\n"
                    f"• {method_info['session_override_count']} integration overrides\n"
                    f"• Expected samples: {method_info['expected_sample_count']}\n\n"
                    f"This will import session-specific integration boundaries.\n"
                    f"Any existing session overrides will be replaced.\n\n"
                    f"Continue with session import?"
                )
            else:
                msg_box = self._create_message_box(
                    "information",
                    "No Session Data",
                    "This session file does not contain any session overrides to import.",
                )
                msg_box.exec()
                return

            # Confirm import
            reply = self._show_question_dialog(
                "Import Session Overrides", "Import session data?", info_text
            )

            if reply != QMessageBox.Yes:
                return

            # Import the session overrides
            success = import_session_overrides(file_path)

            if success:
                msg_box = self._create_message_box(
                    "information",
                    "Session Import Successful",
                    f"Session overrides imported successfully from:\n{file_path}\n\n"
                    f"Integration boundaries have been updated for the affected samples.",
                )
                msg_box.exec()
                logger.info(f"Session overrides imported from {file_path}")

                # Refresh current display if compound/sample are selected
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
        progress_dialog.setWindowTitle("Update Old Data")
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
                internal_standard=internal_standard or self.internal_standard,
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

    def _refresh_after_session_import(self):
        """Refresh display after session import if data is currently displayed."""
        try:
            # If we have compound and samples selected, refresh the display
            selected_compound = self.toolbar.get_selected_compound()
            selected_samples = self.toolbar.get_selected_samples()

            if selected_compound and selected_samples:
                # Regenerate the plots with new session data
                self.on_samples_selected(selected_samples)

        except Exception as e:
            logger.error(f"Failed to refresh after session import: {e}")

    def show_mass_tolerance_dialog(self):
        """Show dialog to edit mass tolerance setting."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Mass Tolerance Settings")
        dialog.setModal(True)
        dialog.resize(400, 150)

        layout = QVBoxLayout(dialog)

        # Info label
        info_label = QLabel("Set the mass tolerance (±Da) for EIC extraction:")
        layout.addWidget(info_label)

        # Mass tolerance input
        mass_tol_layout = QHBoxLayout()
        mass_tol_label = QLabel("Mass Tolerance (Da):")
        mass_tol_layout.addWidget(mass_tol_label)

        mass_tol_spinbox = QDoubleSpinBox()
        mass_tol_spinbox.setRange(0.01, 1.0)
        mass_tol_spinbox.setSingleStep(0.01)
        mass_tol_spinbox.setDecimals(3)
        mass_tol_spinbox.setValue(self.mass_tolerance)
        # Remove suffix and set button symbols to nothing (removes spin buttons)
        mass_tol_spinbox.setButtonSymbols(QDoubleSpinBox.NoButtons)
        # Set white background with white text
        mass_tol_spinbox.setStyleSheet(
            "QDoubleSpinBox { background-color: white; color: black; }"
        )
        mass_tol_layout.addWidget(mass_tol_spinbox)
        mass_tol_layout.addStretch()

        layout.addLayout(mass_tol_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # Show dialog and handle result
        if dialog.exec() == QDialog.Accepted:
            old_value = self.mass_tolerance
            new_value = mass_tol_spinbox.value()

            if old_value != new_value:
                logger.info(
                    f"Mass tolerance changed from {old_value} to {new_value} Da"
                )
                self.mass_tolerance = new_value

                # If data is loaded, trigger regeneration immediately
                if self.cdf_data_loaded:
                    self._on_mass_tolerance_changed(new_value)

    def show_min_peak_height_dialog(self):
        """Show dialog to edit minimum peak height setting."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Minimum Peak Height Settings")
        dialog.setModal(True)
        dialog.resize(500, 280)

        layout = QVBoxLayout(dialog)

        # Info label
        info_label = QLabel(
            "Set the minimum peak height threshold as a fraction of the internal standard height.\n"
            "Peaks below this threshold will be highlighted with a red background.\n"
            "This validation only applies to the m0 peak (unlabeled isotope)."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Min peak area input
        peak_height_layout = QHBoxLayout()
        peak_height_label = QLabel("Minimum Area Ratio:")
        peak_height_layout.addWidget(peak_height_label)

        peak_height_spinbox = QDoubleSpinBox()
        peak_height_spinbox.setRange(0.001, 1.0)
        peak_height_spinbox.setSingleStep(0.001)
        peak_height_spinbox.setDecimals(3)
        peak_height_spinbox.setValue(self.min_peak_height_ratio)
        peak_height_spinbox.setButtonSymbols(QDoubleSpinBox.NoButtons)
        peak_height_spinbox.setStyleSheet(
            "QDoubleSpinBox { background-color: white; color: black; }"
        )
        peak_height_layout.addWidget(peak_height_spinbox)

        # Add explanation
        explanation_label = QLabel("(e.g., 0.05 = 5% of internal standard total area)")
        explanation_label.setStyleSheet("color: gray; font-style: italic;")
        peak_height_layout.addWidget(explanation_label)

        peak_height_layout.addStretch()
        layout.addLayout(peak_height_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # Show dialog and handle result
        if dialog.exec() == QDialog.Accepted:
            old_value = self.min_peak_height_ratio
            new_value = peak_height_spinbox.value()
            self.min_peak_height_ratio = new_value

            if old_value != new_value:
                logger.info(
                    f"Minimum peak height ratio changed from {old_value:.3f} to {new_value:.3f}"
                )

                # Refresh plots if data is loaded to apply new validation
                if self.cdf_data_loaded and self.compound_data_loaded:
                    current_compound = self.toolbar.get_selected_compound()
                    current_samples = self.toolbar.get_selected_samples()
                    if current_compound and current_samples:
                        self.on_plot_button(current_compound, current_samples)

    def show_recovery_dialog(self):
        """Show dialog to recover deleted compounds."""
        dialog = RecoveryDialog(self)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            # Refresh compound list in case compounds were restored
            active_compounds = list_compound_names()
            self.toolbar.update_compound_list(active_compounds)

            # Auto-select first compound if available
            if active_compounds:
                self.toolbar.compound_list.setCurrentRow(0)
                logger.info("Compound list refreshed after recovery")

    def _create_documentation_menu(self, docs_menu):
        """Create documentation menu with available markdown files."""
        # Get the docs directory path
        # From src/manic/ui/main_window.py, go up to project root, then to docs
        docs_dir = Path(docs_path())

        if not docs_dir.exists():
            no_docs_action = QAction("No documentation available", self)
            no_docs_action.setEnabled(False)
            docs_menu.addAction(no_docs_action)
            return

        # Find all markdown files in the docs directory
        md_files = list(docs_dir.glob("*.md"))

        if not md_files:
            no_files_action = QAction("No documentation files found", self)
            no_files_action.setEnabled(False)
            docs_menu.addAction(no_files_action)
            return

        # Sort files - put getting_started first, then alphabetical
        md_files.sort(key=lambda f: (f.name != "getting_started.md", f.name.lower()))

        # Create menu actions for each markdown file
        for md_file in md_files:
            # Create a nice display name from the filename
            display_name = md_file.stem.replace("_", " ").title()

            action = QAction(display_name, self)
            # Use lambda with default argument to capture the file path
            action.triggered.connect(
                lambda checked, file_path=md_file: self._show_documentation(file_path)
            )
            docs_menu.addAction(action)

    def _show_documentation(self, file_path: Path):
        """Show a documentation file in the viewer dialog."""
        try:
            show_documentation_file(self, file_path)
        except Exception as e:
            logger.error(f"Failed to show documentation {file_path}: {e}")
            msg_box = self._create_message_box(
                "critical",
                "Documentation Error",
                f"Failed to open documentation file:\n{str(e)}",
            )
            msg_box.exec()

    def show_about(self):
        """Show About dialog with version information."""
        from manic.__version__ import APP_DESCRIPTION

        about_text = f"""<h2>{APP_NAME} v{__version__}</h2>
<p><b>{APP_DESCRIPTION}</b></p>
<p>This application provides tools for analyzing natural isotope composition in mass spectrometry data.</p>
<p><b>Features:</b></p>
<ul>
<li>Compound definition and parameter management</li>
<li>Raw CDF data processing</li>
<li>Session export/import for reproducible analysis</li>
<li>Integration boundary customization</li>
<li>Isotopologue ratio analysis</li>
</ul>
<p><b>Version:</b> v{__version__}</p>"""

        msg_box = self._create_message_box(
            "information", f"About {APP_NAME}", about_text
        )
        msg_box.exec()

    def clear_session(self):
        """Clear all loaded data and reset application state with progress tracking."""
        reply = self._show_question_dialog(
            "Clear Session",
            "This will clear all loaded data and reset the application.",
            "All compound data, raw data, and session settings will be removed. This cannot be undone.",
        )

        if reply == QMessageBox.Yes:
            # Create and show progress dialog
            progress = QProgressDialog(
                "Preparing to clear session...", "Cancel", 0, 100, self
            )
            progress.setWindowTitle("Clearing Session")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)  # Show immediately
            progress.setValue(0)
            progress.show()
            QCoreApplication.processEvents()  # Ensure dialog appears

            try:
                # Temporarily disconnect signals to prevent cascading events during clear
                self.toolbar.samples_selected.disconnect()
                self.toolbar.compound_selected.disconnect()
                self.toolbar.compound_deleted.disconnect()

                progress.setValue(10)
                progress.setLabelText("Clearing UI state...")
                QCoreApplication.processEvents()

                # Reset UI state flags first
                self.compound_data_loaded = False
                self.cdf_data_loaded = False

                progress.setValue(20)
                progress.setLabelText("Clearing visual elements...")
                QCoreApplication.processEvents()

                # Clear visual elements immediately
                self.graph_view.clear_all_plots()
                self.toolbar.isotopologue_ratios._clear_chart()
                self.toolbar.total_abundance._clear_chart()

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
                    if progress.wasCanceled():
                        return

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

                if progress.wasCanceled():
                    progress.close()
                    return

                progress.setValue(90)
                progress.setLabelText("Reconnecting signals...")
                QCoreApplication.processEvents()

                # Reconnect signals
                self.toolbar.samples_selected.connect(self.on_samples_selected)
                self.toolbar.compound_selected.connect(self.on_compound_selected)
                self.toolbar.compound_deleted.connect(self.on_compound_deleted)

                # Update menu states
                self._update_menu_states()

                progress.setValue(100)
                progress.setLabelText("Session clearing complete")
                QCoreApplication.processEvents()

                # Close progress dialog
                progress.close()

                # Show success message
                msg_box = self._create_message_box(
                    "information",
                    "Session Cleared",
                    "All data has been cleared. You can now load new data.",
                )
                msg_box.exec()

                logger.info("Session cleared successfully")

            except Exception as e:
                # Close progress dialog
                progress.close()

                # Ensure signals are reconnected even if clearing fails
                try:
                    self.toolbar.samples_selected.connect(self.on_samples_selected)
                    self.toolbar.compound_selected.connect(self.on_compound_selected)
                    self.toolbar.compound_deleted.connect(self.on_compound_deleted)
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

    def toggle_natural_abundance_correction(self):
        """
        Toggle natural abundance correction visualization on/off.

        IMPORTANT: This toggle controls ONLY what data is displayed in the UI graphs:
        - When ON: Graphs show corrected data (natural isotope abundance removed)
        - When OFF: Graphs show raw uncorrected data

        This toggle does NOT affect data export. Exported data always contains properly
        corrected values in the Corrected Values sheet, regardless of this toggle state.
        See export_data() for details on how corrections are ensured during export.
        """
        is_enabled = self.nat_abundance_toggle.isChecked()
        logger.info(
            f"Natural abundance correction visualization toggled: {'ON' if is_enabled else 'OFF'}"
        )

        # Update menu text
        self.nat_abundance_toggle.setText(
            f"Natural Abundance Correction: {'On' if is_enabled else 'Off'}"
        )

        # Update the isotopologue ratio widget
        self.toolbar.isotopologue_ratios.set_use_corrected(is_enabled)

        # Also update the graph view to use corrected/uncorrected data
        self.graph_view.set_use_corrected(is_enabled)

        # If enabling correction, check if corrections need to be applied
        if is_enabled:
            try:
                from manic.models.database import get_connection
                from manic.processors.eic_correction_manager import (
                    process_all_corrections,
                )

                # Check if there are raw EICs that don't have corresponding corrected data
                with get_connection() as conn:
                    missing_corrections_count = conn.execute("""
                        SELECT COUNT(*) 
                        FROM eic e
                        JOIN compounds c ON e.compound_name = c.compound_name
                        LEFT JOIN eic_corrected ec
                           ON ec.sample_name = e.sample_name
                          AND ec.compound_name = e.compound_name
                        WHERE e.deleted = 0 
                          AND c.deleted = 0 
                          AND c.label_atoms > 0
                          AND (ec.id IS NULL OR ec.deleted = 1)
                    """).fetchone()[0]

                # If we have raw EICs without corrected data, apply corrections
                if missing_corrections_count > 0:
                    logger.info(
                        f"Applying natural abundance corrections for {missing_corrections_count} EICs..."
                    )

                    # Show progress dialog (no cancel button)
                    from PySide6.QtCore import Qt
                    from PySide6.QtWidgets import QProgressDialog

                    progress_dialog = QProgressDialog(
                        "Applying natural abundance corrections...", "", 0, 100, self
                    )
                    progress_dialog.setWindowTitle("Natural Abundance Correction")
                    progress_dialog.setWindowModality(Qt.WindowModal)
                    progress_dialog.setCancelButton(None)
                    progress_dialog.show()

                    def correction_progress(current, total):
                        if total > 0:
                            progress_value = int((current / total) * 100)
                            progress_dialog.setValue(progress_value)

                    try:
                        corrections_count = process_all_corrections(
                            progress_cb=correction_progress
                        )
                        logger.info(
                            f"Applied {corrections_count} natural abundance corrections"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to apply natural abundance corrections: {e}"
                        )
                    finally:
                        progress_dialog.close()

            except Exception as e:
                logger.error(
                    f"Error checking/applying natural abundance corrections: {e}"
                )

        # If we have data displayed, refresh everything
        selected_compound = self.toolbar.get_selected_compound()
        selected_samples = self.toolbar.get_selected_samples()

        if selected_compound and selected_samples:
            # Trigger a full replot of the main graphs
            self.on_plot_button(selected_compound, selected_samples)

    def toggle_legacy_integration_mode(self):
        """Toggle legacy MATLAB-compatible integration mode on/off."""
        is_enabled = self.legacy_integration_toggle.isChecked()
        self.use_legacy_integration = is_enabled

        logger.info(f"Legacy integration mode toggled: {'ON' if is_enabled else 'OFF'}")

        # Update menu text
        self.legacy_integration_toggle.setText(
            f"Legacy Integration Mode: {'On' if is_enabled else 'Off'}"
        )

        # Show information dialog about the change
        mode_name = "Legacy Unit-Spacing" if is_enabled else "Time-Based"

        msg = self._create_message_box(
            "info",
            "Integration Mode Changed",
            f"Integration method changed to: {mode_name}",
            "The change will only apply to graphs in the GUI. Integration method for export is chosen at the time of export. "
            "See documentation for detailed information about integration methods.",
        )
        msg.exec()

        # Also update the graph view to use corrected/uncorrected data
        self.graph_view.set_use_corrected(is_enabled)

        # If we have data displayed, refresh everything
        selected_compound = self.toolbar.get_selected_compound()
        selected_samples = self.toolbar.get_selected_samples()

        if selected_compound and selected_samples:
            # Trigger a full replot of the main graphs
            self.on_plot_button(selected_compound, selected_samples)

    def _ensure_corrections_applied_for_export(self):
        """
        Ensure natural isotope corrections are applied before data export.

        This method is called automatically before any export operation to guarantee
        that the Corrected Values sheet contains properly corrected data. This is
        completely independent of the UI visualization toggle state.

        If corrections are missing (user never toggled correction on in UI), they are
        applied automatically with a progress dialog. This is safe because:
        - Correction application is idempotent (INSERT OR REPLACE)
        - Only missing corrections are computed
        - Original raw data is never modified
        """
        try:
            from manic.models.database import get_connection
            from manic.processors.eic_correction_manager import process_all_corrections

            # Check if there are any labeled compounds that lack corrected data
            with get_connection() as conn:
                missing_corrections_count = conn.execute("""
                    SELECT COUNT(*) 
                    FROM eic e
                    JOIN compounds c ON e.compound_name = c.compound_name
                    LEFT JOIN eic_corrected ec
                       ON ec.sample_name = e.sample_name
                      AND ec.compound_name = e.compound_name
                      AND ec.deleted = 0
                    WHERE e.deleted = 0 
                      AND c.deleted = 0 
                      AND c.label_atoms > 0
                      AND ec.id IS NULL
                """).fetchone()[0]

            # If corrections are missing, apply them silently
            if missing_corrections_count > 0:
                logger.info(
                    f"Export requires natural isotope corrections. "
                    f"Applying corrections for {missing_corrections_count} labeled compounds..."
                )

                try:
                    corrections_count = process_all_corrections(progress_cb=None)
                    logger.info(
                        f"Successfully applied {corrections_count} natural isotope corrections for export"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to apply natural isotope corrections for export: {e}"
                    )
                    raise  # Re-raise to prevent export with incorrect data
            else:
                logger.debug("All required natural isotope corrections already applied")

        except Exception as e:
            logger.error(f"Error ensuring corrections for export: {e}")
            # Show error dialog
            msg = self._create_message_box(
                "error",
                "Export Preparation Failed",
                "Failed to prepare corrected data for export.",
                f"Error: {str(e)}\n\n"
                "The export cannot proceed without properly corrected data. "
                "Please check the logs for details.",
            )
            msg.exec()
            raise  # Prevent export from continuing

    def export_data(self):
        """
        Export processed data to Excel with 5 worksheets.

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
            # Get export file path
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

            # CRITICAL: Ensure natural isotope corrections are applied before export
            # This is independent of the UI visualization toggle state
            self._ensure_corrections_applied_for_export()

            # Export options popup: choose integration mode
            options_dialog = QDialog(self)
            options_dialog.setWindowTitle("Export Options")
            vbox = QVBoxLayout(options_dialog)
            info_label = QLabel(
                "Choose integration method for this export (can also be changed in Settings → Legacy Integration Mode):"
            )
            vbox.addWidget(info_label)
            # Force black text for label and radio buttons regardless of theme
            options_dialog.setStyleSheet("QLabel, QRadioButton { color: black; }")

            radio_time = QRadioButton("Time-based (recommended)")
            radio_legacy = QRadioButton("Legacy (MATLAB-compatible unit spacing)")
            vbox.addWidget(radio_time)
            vbox.addWidget(radio_legacy)

            # Default selection depends on current settings toggle
            if self.use_legacy_integration:
                radio_legacy.setChecked(True)
            else:
                radio_time.setChecked(True)
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            vbox.addWidget(buttons)
            buttons.accepted.connect(options_dialog.accept)
            buttons.rejected.connect(options_dialog.reject)

            if options_dialog.exec() != QDialog.Accepted:
                return  # user cancelled

            # Read selection and persist to window state
            chosen_use_legacy = radio_legacy.isChecked()
            self.use_legacy_integration = chosen_use_legacy

            # Get current internal standard selection from toolbar
            internal_standard = self.toolbar.get_internal_standard()

            # Create progress dialog
            progress_dialog = QProgressDialog(
                "Exporting data to Excel...", "Cancel", 0, 100, self
            )
            progress_dialog.setWindowTitle("Data Export")
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.setModal(True)
            progress_dialog.setValue(0)

            # Create exporter and set internal standard and integration mode
            exporter = DataExporter()
            exporter.set_internal_standard(internal_standard)
            exporter.set_use_legacy_integration(self.use_legacy_integration)

            # Progress callback function
            def update_progress(value):
                progress_dialog.setValue(value)
                QCoreApplication.processEvents()  # Keep UI responsive
                return not progress_dialog.wasCanceled()  # Return False if cancelled

            # Show progress dialog
            progress_dialog.show()
            QCoreApplication.processEvents()

            # Perform export
            success = exporter.export_to_excel(
                file_path,
                update_progress,
                use_legacy_integration=self.use_legacy_integration,
            )

            # Close progress dialog
            progress_dialog.close()

            if success:
                # Show success message
                msg_box = self._create_message_box(
                    "information",
                    "Data Export Successful",
                    f"Data exported successfully to:\n{file_path}\n\n"
                    f"The Excel file contains 5 worksheets:\n"
                    f"• Raw Values - Direct instrument signals\n"
                    f"• Corrected Values - Natural isotope corrected signals\n"
                    f"• Isotope Ratios - Normalized corrected values\n"
                    f"• Abundances - Absolute metabolite concentrations\n"
                    f"• % Label Incorporation - Experimental label percentages",
                )
                msg_box.exec()
                logger.info(f"Data exported successfully to {file_path}")
            else:
                # Show error message
                msg_box = self._create_message_box(
                    "critical",
                    "Export Failed",
                    "Data export was cancelled or failed. Check logs for details.",
                )
                msg_box.exec()
                logger.warning("Data export was cancelled or failed")

        except Exception as e:
            logger.error(f"Data export error: {e}")
            msg_box = self._create_message_box(
                "critical",
                "Export Error",
                f"An error occurred during data export:\n{str(e)}",
            )
            msg_box.exec()
