import logging

from PySide6.QtCore import QCoreApplication, Qt, QThread
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QWidget,
)

from manic.io.compounds_import import import_compound_excel
from manic.io.list_compound_names import list_compound_names
from manic.io.sample_reader import list_active_samples
from manic.ui.graphs import GraphView
from manic.ui.left_toolbar import Toolbar
from manic.utils.utils import load_stylesheet
from manic.utils.workers import CdfImportWorker, EicRegenerationWorker
from src.manic.utils.timer import measure_time

logger = logging.getLogger("manic_logger")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MANIC")
        self.setObjectName("mainWindow")
        self.progress_bar = QProgressBar()

        # Menu actions
        self.load_cdf_action = None
        self.load_compound_action = None

        self.setup_ui()

        # Load and apply the stylesheet
        stylesheet = load_stylesheet("src/manic/resources/style.qss")
        self.setStyleSheet(stylesheet)

        # Connect the toolbar's custom signals to a handler methods
        self.toolbar.samples_selected.connect(self.on_samples_selected)
        self.toolbar.compound_selected.connect(self.on_compound_selected)

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

        # Set the menu bar to the QMainWindow
        self.setMenuBar(menu_bar)

        # Connect the toolbar's custom signals to handler methods
        self.toolbar.samples_selected.connect(self.on_samples_selected)
        self.toolbar.compound_selected.connect(self.on_compound_selected)

        # Connect the graph view's selection signal
        self.graph_view.selection_changed.connect(self.on_plot_selection_changed)
        
        # Connect the integration window's session data signals
        self.toolbar.integration.session_data_applied.connect(self.on_session_data_applied)
        self.toolbar.integration.session_data_restored.connect(self.on_session_data_restored)
        self.toolbar.integration.data_regeneration_requested.connect(self.on_data_regeneration_requested)

    # reusable progress dialog
    def _build_progress_dialog(self, title: str) -> QProgressDialog:
        dlg = QProgressDialog(title, None, 0, 100, self)
        dlg.setWindowTitle("Please wait")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setMinimumDuration(0)  # Show immediately
        dlg.setCancelButton(None)  # Remove cancel button for simplicity
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

        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def load_cdf_files(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if not directory:
            return

        # build dialog & worker
        self.progress_dialog = self._build_progress_dialog("Importing CDF data…")
        self.progress_dialog.show()

        self._thread = QThread(self)  # background thread
        self._worker = CdfImportWorker(directory)  # heavy lifting
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
        QMessageBox.information(
            self, "Import OK", f"Data for {rows} EICs successfully extracted."
        )
        # set raw data indicator to green
        self.toolbar.update_label_colours(True, True)

        # get active samples
        active_samples = list_active_samples()

        # update samples list in toolbar
        # update to samples list in toolbar will trigger plotting
        self.toolbar.update_sample_list(active_samples)

    def _import_fail(self, msg: str):
        self.progress_dialog.close()
        QMessageBox.critical(self, "Import failed", msg)

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
                    samples  # All visible samples
                )
                
                # Update tR window field only when compound changes
                self.toolbar.integration.populate_tr_window_field(compound_name)
                
                # Update isotopologue ratios first (calculates both ratios and abundances)
                current_eics = self._get_current_eics()
                self.toolbar.isotopologue_ratios.update_ratios(compound_name, current_eics)
                
                # Share the calculated abundances with total abundance widget (no recalculation)
                abundances, eics = self.toolbar.isotopologue_ratios.get_last_total_abundances()
                if abundances is not None:
                    self.toolbar.total_abundance.update_abundance_from_data(compound_name, eics, abundances)
                else:
                    # Fallback - clear the chart if no data available
                    self.toolbar.total_abundance._clear_chart()
        except LookupError as err:
            QMessageBox.warning(self, "Missing data", str(err))
        except Exception as e:
            logger.error(f"Error plotting: {e}")
            QMessageBox.warning(self, "Error", f"Error plotting: {str(e)}")

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

    def on_plot_selection_changed(self, selected_samples):
        """Handle when plots are selected/deselected"""
        # Update integration window based on plot selection
        current_compound = self.graph_view.get_current_compound()
        all_samples = self.graph_view.get_current_samples()
        
        if current_compound:
            self.toolbar.integration.populate_fields_from_plots(
                current_compound, 
                selected_samples, 
                all_samples
            )
            
            # Update isotopologue ratios and total abundance (integration parameters may have changed)
            current_eics = self._get_current_eics()
            self.toolbar.isotopologue_ratios.update_ratios(current_compound, current_eics)
            
            # Share calculated abundances
            abundances, eics = self.toolbar.isotopologue_ratios.get_last_total_abundances()
            if abundances is not None:
                self.toolbar.total_abundance.update_abundance_from_data(current_compound, eics, abundances)
    
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
                        compound_name,
                        current_selected,
                        all_samples
                    )
            
            # Use a timer to delay the update slightly
            QTimer.singleShot(100, update_integration_window)
            
            # Update isotopologue ratios and total abundance with new integration parameters
            def update_charts():
                current_eics = self._get_current_eics()
                self.toolbar.isotopologue_ratios.update_ratios(compound_name, current_eics)
                
                # Share calculated abundances
                abundances, eics = self.toolbar.isotopologue_ratios.get_last_total_abundances()
                if abundances is not None:
                    self.toolbar.total_abundance.update_abundance_from_data(compound_name, eics, abundances)
            
            QTimer.singleShot(150, update_charts)
            
        except Exception as e:
            logger.error(f"Failed to refresh plots after session data update: {e}")
            # Show error to user but don't crash the application
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Refresh Failed", 
                f"Failed to refresh plots with updated parameters: {str(e)}"
            )
    
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
                        compound_name,
                        current_selected,
                        all_samples
                    )
            
            # Use a timer to delay the update slightly
            QTimer.singleShot(100, update_integration_window)
            
            # Update isotopologue ratios and total abundance with restored default parameters
            def update_charts():
                current_eics = self._get_current_eics()
                self.toolbar.isotopologue_ratios.update_ratios(compound_name, current_eics)
                
                # Share calculated abundances
                abundances, eics = self.toolbar.isotopologue_ratios.get_last_total_abundances()
                if abundances is not None:
                    self.toolbar.total_abundance.update_abundance_from_data(compound_name, eics, abundances)
            
            QTimer.singleShot(150, update_charts)
            
        except Exception as e:
            logger.error(f"Failed to refresh plots after session data restore: {e}")
            # Show error to user but don't crash the application
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Refresh Failed", 
                f"Failed to refresh plots after restore: {str(e)}"
            )

    def on_data_regeneration_requested(self, compound_name: str, tr_window: float, sample_names: list):
        """Handle data regeneration request - start background regeneration with progress dialog"""
        logger.info(f"Data regeneration requested for compound '{compound_name}' with tR window {tr_window}")
        
        try:
            # Build and show progress dialog
            self.regen_progress_dialog = self._build_progress_dialog(
                f"Regenerating EIC data for '{compound_name}'..."
            )
            self.regen_progress_dialog.show()

            # Create background thread and worker
            self._regen_thread = QThread(self)
            self._regen_worker = EicRegenerationWorker(compound_name, tr_window, sample_names)
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
            QMessageBox.critical(
                self,
                "Regeneration Error",
                f"Failed to start data regeneration: {str(e)}"
            )

    def _update_regeneration_progress(self, current: int, total: int):
        """Update regeneration progress dialog"""
        if hasattr(self, 'regen_progress_dialog'):
            pct = int(current / total * 100) if total > 0 else 0
            self.regen_progress_dialog.setMaximum(100)
            self.regen_progress_dialog.setValue(pct)
            self.regen_progress_dialog.setLabelText(f"Processing sample {current} of {total}...")
            QCoreApplication.processEvents()

    def _regeneration_completed(self, regenerated_count: int):
        """Handle successful regeneration completion"""
        if hasattr(self, 'regen_progress_dialog'):
            self.regen_progress_dialog.close()
            
        logger.info(f"Regeneration completed successfully: {regenerated_count} EICs regenerated")
        
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
                tr_window_field = self.toolbar.integration.findChild(QLineEdit, "tr_window_input")
                current_tr_window = tr_window_field.text() if tr_window_field else ""
                
                if current_compound:
                    # Refresh other fields but preserve tR window
                    self.toolbar.integration.populate_fields_from_plots(
                        current_compound,
                        current_selected,
                        all_samples
                    )
                    
                    # Restore tR window value (don't overwrite with old default)
                    if tr_window_field and current_tr_window:
                        tr_window_field.setText(current_tr_window)
            
            # Small delay to ensure plot refresh completes
            QTimer.singleShot(100, update_integration_window)
            
            # Show success message
            QMessageBox.information(
                self,
                "Regeneration Complete",
                f"Data regeneration completed successfully!\n\n"
                f"Regenerated {regenerated_count} EIC records.\n"
                f"Plots have been refreshed with new data."
            )
            
        except Exception as e:
            logger.error(f"Error during post-regeneration refresh: {e}")
            QMessageBox.warning(
                self,
                "Regeneration Complete with Warning",
                f"Data regeneration completed ({regenerated_count} EICs), "
                f"but plot refresh failed: {str(e)}\n\n"
                f"Try manually refreshing the plots."
            )

    def _regeneration_failed(self, error_msg: str):
        """Handle regeneration failure"""
        if hasattr(self, 'regen_progress_dialog'):
            self.regen_progress_dialog.close()
            
        logger.error(f"Regeneration failed: {error_msg}")
        QMessageBox.critical(
            self,
            "Regeneration Failed",
            f"Data regeneration failed:\n\n{error_msg}\n\n"
            f"Please check the log files for more details."
        )
