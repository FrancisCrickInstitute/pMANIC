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
    QLineEdit,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QVBoxLayout,
    QWidget,
)

from manic.__version__ import APP_NAME, __version__
from manic.io.compounds_import import import_compound_excel
from manic.io.data_exporter import DataExporter
from manic.io.list_compound_names import list_compound_names
from manic.io.sample_reader import list_active_samples
from manic.models.database import clear_database, get_connection
from manic.ui.documentation_viewer import show_documentation_file
from manic.ui.graphs import GraphView
from manic.ui.left_toolbar import Toolbar
from manic.utils.utils import load_stylesheet
from manic.utils.workers import CdfImportWorker, EicRegenerationWorker
from src.manic.utils.timer import measure_time

logger = logging.getLogger("manic_logger")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.setObjectName("mainWindow")

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
        self.compound_data_loaded = False
        self.cdf_data_loaded = False

        self.setup_ui()

        # Load and apply the stylesheet
        stylesheet = load_stylesheet("src/manic/resources/style.qss")
        self.setStyleSheet(stylesheet)

        # Connect the toolbar's custom signals to a handler methods
        self.toolbar.samples_selected.connect(self.on_samples_selected)
        self.toolbar.compound_selected.connect(self.on_compound_selected)
        self.toolbar.internal_standard_selected.connect(
            self.on_internal_standard_selected
        )

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

        # Add separator before export data
        file_menu.addSeparator()

        # Create export data action
        self.export_data_action = QAction("Export Data...", self)
        self.export_data_action.triggered.connect(self.export_data)
        file_menu.addAction(self.export_data_action)

        """ Create Settings Menu """

        settings_menu = menu_bar.addMenu("Settings")

        self.mass_tolerance_action = QAction("Mass Tolerance...", self)
        self.mass_tolerance_action.triggered.connect(self.show_mass_tolerance_dialog)
        settings_menu.addAction(self.mass_tolerance_action)

        # Natural abundance correction toggle action
        self.nat_abundance_toggle = QAction("Natural Abundance Correction: On", self)
        self.nat_abundance_toggle.setCheckable(True)
        self.nat_abundance_toggle.setChecked(True)  # On by default
        self.nat_abundance_toggle.triggered.connect(
            self.toggle_natural_abundance_correction
        )
        settings_menu.addAction(self.nat_abundance_toggle)

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
        self.toolbar.isotopologue_ratios.set_use_corrected(True)  # On by default

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
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(base_dir, "resources", "manic_logo.png")
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

        # Set the logo as window icon and replace standard icon
        logo_path = self._get_logo_path()
        if logo_path:
            msg_box.setWindowIcon(QIcon(logo_path))
            # Replace the standard icon with our logo (scaled appropriately)
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                msg_box.setIconPixmap(scaled_pixmap)

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
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Compound List", "", "Excel Files (*.xls *.xlsx)"
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
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
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

    def on_plot_button(self, compound_name, samples):
        # Validate inputs before plotting
        if not compound_name or compound_name.startswith("- No"):
            return  # Don't plot with placeholder compound

        if not samples or any(sample.startswith("- No") for sample in samples):
            return  # Don't plot with placeholder samples

        try:
            if samples:
                with measure_time("total_plotting_speed"):
                    self.graph_view.plot_compound(compound_name, samples)

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
            # Refresh plots with session data
            self.graph_view.refresh_plots_with_session_data()

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
        self, compound_name: str, tr_window: float, sample_names: list
    ):
        """Handle data regeneration request - start background regeneration with progress dialog"""
        logger.info(
            f"Data regeneration requested for compound '{compound_name}' with tR window {tr_window}"
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
                compound_name, tr_window, sample_names
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
            # Refresh plots to show new EIC data
            # Since EIC data was regenerated, we need a full replot
            current_compound = self.graph_view.get_current_compound()
            current_samples = self.graph_view.get_current_samples()

            if current_compound and current_samples:
                # Force a complete replot with fresh EIC data
                self.graph_view.plot_compound(current_compound, current_samples)
            else:
                # Fallback to session data refresh
                self.graph_view.refresh_plots_with_session_data()

            # Update integration window after refresh - but preserve tR window value
            from PySide6.QtCore import QTimer

            def update_integration_window():
                current_compound = self.graph_view.get_current_compound()
                current_selected = self.graph_view.get_selected_samples()
                all_samples = self.graph_view.get_current_samples()

                # Store current tR window value before refresh
                tr_window_field = self.toolbar.integration.findChild(
                    QLineEdit, "tr_window_input"
                )
                current_tr_window = tr_window_field.text() if tr_window_field else ""

                if current_compound:
                    # Refresh other fields but preserve tR window
                    self.toolbar.integration.populate_fields_from_plots(
                        current_compound, current_selected, all_samples
                    )

                    # Restore tR window value (don't overwrite with old default)
                    if tr_window_field and current_tr_window:
                        tr_window_field.setText(current_tr_window)

            # Small delay to ensure plot refresh completes
            QTimer.singleShot(100, update_integration_window)

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
            self.mass_tolerance = new_value

            if old_value != new_value:
                logger.info(
                    f"Mass tolerance changed from {old_value} to {new_value} Da"
                )

                # Notify user that re-import may be needed
                if self.cdf_data_loaded:
                    msg = self._create_message_box(
                        "info",
                        "Mass Tolerance Changed",
                        f"Mass tolerance changed to {new_value} Da.",
                        "Note: This change will only apply to new data imports. "
                        "You may need to re-import CDF files to apply the new tolerance.",
                    )
                    msg.exec()

    def _create_documentation_menu(self, docs_menu):
        """Create documentation menu with available markdown files."""
        # Get the docs directory path
        # From src/manic/ui/main_window.py, go up to project root, then to docs
        docs_dir = Path(__file__).parent.parent.parent.parent / "docs"

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
        """Clear all loaded data and reset application state."""
        reply = self._show_question_dialog(
            "Clear Session",
            "This will clear all loaded data and reset the application.",
            "All compound data, raw data, and session settings will be removed. This cannot be undone.",
        )

        if reply == QMessageBox.Yes:
            try:
                # Temporarily disconnect signals to prevent cascading events during clear
                self.toolbar.samples_selected.disconnect()
                self.toolbar.compound_selected.disconnect()

                # Reset UI state flags first
                self.compound_data_loaded = False
                self.cdf_data_loaded = False

                # Clear visual elements immediately
                self.graph_view.clear_all_plots()
                self.toolbar.isotopologue_ratios._clear_chart()
                self.toolbar.total_abundance._clear_chart()

                # Force UI update to show cleared graphs
                self.graph_view.repaint()

                # Clear data lists
                self.toolbar.update_compound_list([])
                self.toolbar.update_sample_list([])
                self.toolbar.update_label_colours(False, False)

                # Clear internal standard
                self.toolbar.standard.clear_internal_standard()

                # Clear integration window
                self.toolbar.integration.populate_fields(None)

                # Clear graphs
                self.graph_view.clear_all_plots()

                # Clear the database
                clear_database()
                logger.info("Database cleared successfully")

                # Reconnect signals
                self.toolbar.samples_selected.connect(self.on_samples_selected)
                self.toolbar.compound_selected.connect(self.on_compound_selected)

                # Update menu states
                self._update_menu_states()

                # Show success message
                msg_box = self._create_message_box(
                    "information",
                    "Session Cleared",
                    "All data has been cleared. You can now load new data.",
                )
                msg_box.exec()

                logger.info("Session cleared successfully")

            except Exception as e:
                # Ensure signals are reconnected even if clearing fails
                try:
                    self.toolbar.samples_selected.connect(self.on_samples_selected)
                    self.toolbar.compound_selected.connect(self.on_compound_selected)
                except:
                    pass  # Signals might already be connected

                logger.error(f"Failed to clear session: {e}")
                msg_box = self._create_message_box(
                    "critical",
                    "Clear Session Failed",
                    f"Failed to clear session: {str(e)}",
                )
                msg_box.exec()

    def toggle_natural_abundance_correction(self):
        """Toggle natural abundance correction on/off."""
        is_enabled = self.nat_abundance_toggle.isChecked()
        logger.info(
            f"Natural abundance correction toggled: {'ON' if is_enabled else 'OFF'}"
        )

        # Update menu text
        self.nat_abundance_toggle.setText(
            f"Natural Abundance Correction: {'On' if is_enabled else 'Off'}"
        )

        # Update the isotopologue ratio widget
        self.toolbar.isotopologue_ratios.set_use_corrected(is_enabled)

        # Also update the graph view to use corrected/uncorrected data
        self.graph_view.set_use_corrected(is_enabled)

        # If we have data displayed, refresh everything
        selected_compound = self.toolbar.get_selected_compound()
        selected_samples = self.toolbar.get_selected_samples()

        if selected_compound and selected_samples:
            # Trigger a full replot of the main graphs
            self.on_plot_button(selected_compound, selected_samples)

    def export_data(self):
        """Export processed data to Excel with 5 worksheets."""
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

            # Create exporter and set internal standard
            exporter = DataExporter()
            exporter.set_internal_standard(internal_standard)

            # Progress callback function
            def update_progress(value):
                progress_dialog.setValue(value)
                QCoreApplication.processEvents()  # Keep UI responsive
                return not progress_dialog.wasCanceled()  # Return False if cancelled

            # Show progress dialog
            progress_dialog.show()
            QCoreApplication.processEvents()

            # Perform export
            success = exporter.export_to_excel(file_path, update_progress)

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
