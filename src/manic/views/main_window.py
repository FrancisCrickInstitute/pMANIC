import logging

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QWidget,
)

from manic.controllers.load_cdf_data import load_cdf_files_from_directory
from manic.io.compounds_import import import_compound_excel
from manic.models.database import get_connection
from manic.utils.constants import APPLICATION_VERSION
from manic.utils.utils import load_stylesheet
from manic.views.graph_view import GraphView
from manic.views.toolbar import Toolbar
from src.manic.old_models import (
    CdfDirectory,
    CdfFileData,
    CompoundData,
    CompoundListData,
)

logger = logging.getLogger("manic_logger")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MANIC")
        self.setObjectName("mainWindow")
        self.cdf_data_storage: CdfDirectory | None = None
        self.compounds_data_storage: CompoundListData | None = None

        # Menu actions
        self.load_cdf_action = None
        self.load_compound_action = None
        self.save_compounds_action = None
        self.recover_deleted_files_action = None
        self.recover_deleted_compounds_action = None
        self.export_integrals_action = None
        self.load_session_action = None
        self.save_session_action = None
        self.clear_session_action = None

        self.setup_ui()

        # Load and apply the stylesheet
        stylesheet = load_stylesheet("src/manic/resources/style.qss")
        self.setStyleSheet(stylesheet)

        # Initialize menu state
        self.update_menu_state(compounds_loaded=False, raw_data_loaded=False)

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

        self.save_compounds_action = file_menu.addAction(
            "Save Compounds/Parameter List"
        )
        file_menu.addSeparator()
        self.recover_deleted_files_action = file_menu.addAction("Recover Deleted Files")
        self.recover_deleted_compounds_action = file_menu.addAction(
            "Recover Deleted Compounds"
        )
        file_menu.addSeparator()
        self.export_integrals_action = file_menu.addAction("Export Integrals")
        file_menu.addSeparator()
        self.load_session_action = file_menu.addAction("Load Session")
        self.save_session_action = file_menu.addAction("Save Session")
        self.clear_session_action = file_menu.addAction("Clear Session")
        file_menu.addSeparator()
        file_menu.addAction("Close App")

        # Create View Menu
        view_menu = menu_bar.addMenu("View")
        view_menu.addAction("Toggle Colour Blind Aid")

        # Create Version Menu
        version_menu = menu_bar.addMenu("Application Version")
        version_number = version_menu.addAction(f"MANIC v{APPLICATION_VERSION}")
        version_number.setEnabled(False)

        # Set the menu bar to the QMainWindow
        self.setMenuBar(menu_bar)

    def update_ui_with_compounds(self: QMainWindow) -> None:
        """
        Update the UIs indicator of compound list loaded state.

        """
        raw_data_loaded = self.cdf_data_storage is not None
        self.update_label_colors(
            raw_data_loaded=raw_data_loaded, compound_list_loaded=True
        )
        self.update_menu_state(compounds_loaded=True, raw_data_loaded=raw_data_loaded)

    def update_ui_with_data(self: QMainWindow) -> None:
        """
        Update the UIs indicator of raw data/cdf loaded state.

        """
        compound_list_loaded = self.compounds_data_storage is not None
        self.update_label_colors(
            raw_data_loaded=True, compound_list_loaded=compound_list_loaded
        )
        self.update_menu_state(
            compounds_loaded=compound_list_loaded, raw_data_loaded=True
        )

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

            sql = """
                    SELECT *
                    FROM   compounds
                    WHERE  compound_name = ?
                      AND  deleted = 0            -- omit if you don't use soft-deletes
                    LIMIT 1
                    """

            with get_connection() as conn:
                row = conn.execute(sql, ("Pyruvate",)).fetchone()
                print(dict(row))

            self.update_ui_with_compounds()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def load_cdf_files(self: QMainWindow) -> None:
        """
        1. Prompt the user to select a directory from which to load the CDF files.
        2. Call the load_cdf_files_from_directory controller function to load the CDF files.

        """
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if not directory:
            return
        try:
            self.cdf_data_storage = load_cdf_files_from_directory(directory)
            self.update_ui_with_data()
            QCoreApplication.processEvents()  # Process all pending events
        except FileNotFoundError as e:
            QMessageBox.warning(self, "Error", str(e))
            self.progress_dialog.close()

        if self.cdf_data_storage:
            self.plot_graphs()

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

    def update_plot_progress_bar(self, current, total):
        progress = int((current / total) * 100)
        self.progress_dialog.set_progress(progress)
        self.progress_dialog.label.setText(f"Plotting graphs... ({current}/{total})")
        QCoreApplication.processEvents()

    def update_label_colors(self, raw_data_loaded, compound_list_loaded):
        toolbar = self.findChild(Toolbar)
        toolbar.update_label_colors(raw_data_loaded, compound_list_loaded)

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
