import logging

from PySide6.QtCore import QCoreApplication, Qt, QThread
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QWidget,
)

from manic.io.compounds_import import import_compound_excel
from manic.ui.graph_view import GraphView
from manic.utils.utils import load_stylesheet
from manic.utils.workers import CdfImportWorker
from manic.views.toolbar import Toolbar

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

        # Initialize menu state
        # self.update_menu_state(compounds_loaded=False, raw_data_loaded=False)

    def setup_ui(self):
        """
        Set up the application UI.
        """

        # Create the main layout
        main_layout = QHBoxLayout()

        # Create the toolbar
        toolbar = Toolbar()
        toolbar.setObjectName("toolbar")
        main_layout.addWidget(toolbar)

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

        # Create the actions/logic for loading CDF files
        self.load_cdf_action = QAction("Load Raw Data (CDF)", self)
        self.load_cdf_action.triggered.connect(self.load_cdf_files)
        # Add the load CDF action/logic to the file menu
        file_menu.addAction(self.load_cdf_action)

        # Add a separator to the file menu
        file_menu.addSeparator()

        # Create the actions/logic for loading compound list data
        self.load_compound_action = QAction("Load Compounds/Parameter List", self)
        self.load_compound_action.triggered.connect(self.load_compound_list_data)
        # Add the load compound action/logic to the file menu
        file_menu.addAction(self.load_compound_action)

        # Set the menu bar to the QMainWindow
        self.setMenuBar(menu_bar)

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
        # Automatically plot after successful import
        self.on_plot_button()

    def _import_fail(self, msg: str):
        self.progress_dialog.close()
        QMessageBox.critical(self, "Import failed", msg)

    def on_plot_button(self):
        try:
            self.graph_view.plot_compound("Pyruvate")  # "C12:0"
        except LookupError as err:
            QMessageBox.warning(self, "Missing data", str(err))
        except Exception as e:
            logger.error(f"Error plotting: {e}")
            QMessageBox.warning(self, "Error", f"Error plotting: {str(e)}")

    """
    def plot_graphs(
        self: QMainWindow,
        compound: CompoundData | None = None,
        cdf_files: list[CdfFileData] | None = None,
    ):
        if compound is None and self.compounds_data_storage is not None:
            compound = self.compounds_data_storage.compound_data[
                0
            ]  # Use the first compound if none are specified
            logger.info(f"First compound: {vars(compound)}")

        if cdf_files is None and self.cdf_data_storage is not None:
            cdf_files = self.cdf_data_storage.cdf_directory
            # Use all loaded CDF files if none are specified

        if compound is None or cdf_files is None:
            QMessageBox.warning(self, "Error: No data to plot.")
            return

        try:
            num_files = len(cdf_files)
            graphs = []
            for i, cdf_object in enumerate(cdf_files):
                eic_data = self.graph_view.extract_eic_data(cdf_object, compound)
                graph = self.graph_view.create_eic_plot(eic_data)
                graphs.append(graph)

                # Update the progress bar
                self.update_plot_progress_bar(i + 1, num_files)

            # Refresh the plots in the graph view
            self.graph_view.refresh_plots(graphs)
        finally:
            self.progress_dialog.close()
    """

    def update_plot_progress_bar(self, current, total):
        progress = int((current / total) * 100)
        self.progress_dialog.set_progress(progress)
        self.progress_dialog.label.setText(f"Plotting graphs... ({current}/{total})")
        QCoreApplication.processEvents()

    def update_label_colors(self, raw_data_loaded, compound_list_loaded):
        toolbar = self.findChild(Toolbar)
        toolbar.update_label_colors(raw_data_loaded, compound_list_loaded)


"""

    def update_menu_state(self, compounds_loaded, raw_data_loaded):
        # Always enable these actions
        self.load_compound_action.setEnabled(True)
        self.load_session_action.setEnabled(True)

        # Enable/disable based on compounds loaded
        self.load_cdf_action.setEnabled(compounds_loaded)

        # Enable/disable based on raw data loaded
        self.recover_deleted_files_action.setEnabled(raw_data_loaded)
        self.export_integrals_action.setEnabled(raw_data_loaded)
        self.save_session_action.setEnabled(raw_data_loaded)
        self.clear_session_action.setEnabled(raw_data_loaded)
        self.save_compounds_action.setEnabled(raw_data_loaded)
        self.recover_deleted_compounds_action.setEnabled(raw_data_loaded)

"""
