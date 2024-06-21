from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QMenuBar, QFileDialog, QMessageBox,
                               QProgressBar)
from PySide6.QtGui import QAction
from PySide6.QtCore import QCoreApplication
from src.manic.gui.toolbar import Toolbar
from src.manic.gui.graph_view import GraphView
from src.manic.utils.constants import APPLICATION_VERSION
from src.manic.utils.utils import load_stylesheet
from src.manic.data.load_cdfs import load_cdf_files_from_directory
from src.manic.gui.progress_bar import ProgressDialog
from src.manic.data.load_compound_list import load_compound_list


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MANIC")
        self.setObjectName("mainWindow")
        self.cdf_data_storage = None
        self.compounds_data_storage = None

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

        # Create File Menu
        file_menu = menu_bar.addMenu("File")
        self.load_cdf_action = QAction("Load Raw Data (CDF)", self)
        self.load_cdf_action.triggered.connect(self.load_cdf_files)
        file_menu.addAction(self.load_cdf_action)
        file_menu.addSeparator()
        self.load_compound_action = QAction("Load Compounds/Parameter List", self)
        self.load_compound_action.triggered.connect(self.load_compound_list)
        file_menu.addAction(self.load_compound_action)
        self.save_compounds_action = file_menu.addAction("Save Compounds/Parameter List")
        file_menu.addSeparator()
        self.recover_deleted_files_action = file_menu.addAction("Recover Deleted Files")
        self.recover_deleted_compounds_action = file_menu.addAction("Recover Deleted Compounds")
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

    def load_cdf_files(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if not directory:
            return

        self.progress_dialog = ProgressDialog(self, "Loading CDF Files", "Loading CDF files, please wait...")
        self.progress_dialog.show()

        try:
            self.cdf_data_storage = load_cdf_files_from_directory(directory, self.update_cdf_progress_bar)
            self.update_ui_with_data()
            self.progress_dialog.close()
            QCoreApplication.processEvents()  # Process all pending events
            self.plot_graphs()
        except FileNotFoundError as e:
            QMessageBox.warning(self, "Error", str(e))
            self.progress_dialog.close()


    def load_compound_list(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Compound List", "", "Excel Files (*.xls *.xlsx)")
        if not file_path:
            return

        try:
            self.compounds_data_storage = load_compound_list(file_path)
            self.update_ui_with_compounds()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def update_cdf_progress_bar(self, current, total):
        progress = int((current / total) * 100)
        self.progress_dialog.set_progress(progress)
        self.progress_dialog.label.setText(f"Loading CDF files... ({current}/{total})")
        QCoreApplication.processEvents()

    def update_ui_with_compounds(self):
        QMessageBox.information(self, "Compounds Loaded", f"Loaded {len(self.compounds_data_storage)} compounds.")
        raw_data_loaded = self.cdf_data_storage is not None
        self.update_label_colors(raw_data_loaded=raw_data_loaded, compound_list_loaded=True)
        self.update_menu_state(compounds_loaded=True, raw_data_loaded=raw_data_loaded)

    def update_ui_with_data(self):
        compound_list_loaded = self.compounds_data_storage is not None
        self.update_label_colors(raw_data_loaded=True, compound_list_loaded=compound_list_loaded)
        self.update_menu_state(compounds_loaded=compound_list_loaded, raw_data_loaded=True)

    def plot_graphs(self, compound=None, cdf_files=None):
        if compound is None:
            compound = self.compounds_data_storage[0]  # Use the first compound if none is specified
            print(compound)

        if cdf_files is None:
            cdf_files = self.cdf_data_storage  # Use all loaded CDF files if none are specified

        # Sort the cdf_files based on their file names
        cdf_files = sorted(cdf_files, key=lambda x: x.file_name)

        self.progress_dialog = ProgressDialog(self, "Creating EIC Plots", "Plotting graphs, please wait...")
        self.progress_dialog.show()

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


