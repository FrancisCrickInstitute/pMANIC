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
from manic.io.list_compound_names import list_compound_names
from manic.io.sample_reader import list_active_samples
from manic.ui.graph_view import GraphView
from manic.ui.left_toolbar import Toolbar
from manic.utils.utils import load_stylesheet
from manic.utils.workers import CdfImportWorker
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
        except LookupError as err:
            QMessageBox.warning(self, "Missing data", str(err))
        except Exception as e:
            logger.error(f"Error plotting: {e}")
            QMessageBox.warning(self, "Error", f"Error plotting: {str(e)}")

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
