from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QMenuBar
from src.manic.gui.toolbar import Toolbar
from src.manic.gui.graph_view import GraphView
from src.manic.utils.constants import APPLICATION_VERSION
from src.manic.utils.utils import load_stylesheet


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MANIC")
        self.setup_ui()

    def setup_ui(self):
        # Create the main layout
        main_layout = QHBoxLayout()

        # Create the toolbar
        toolbar = Toolbar()
        main_layout.addWidget(toolbar)

        # Create the chart view
        chart_view = GraphView()
        toolbar.updateChartSignal.connect(chart_view.update_chart)
        main_layout.addWidget(chart_view)
        main_layout.setStretch(1, 1)

        # Set the main layout as the central widget
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Create menu bar
        menu_bar = QMenuBar()

        # Create File Menu
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("Load Raw Data (CDF)")
        file_menu.addSeparator()
        file_menu.addAction("Load Compounds/Parameter List")
        file_menu.addAction("Save Compounds/Parameter List")
        file_menu.addSeparator()
        file_menu.addAction("Recover Deleted Files")
        file_menu.addAction("Recover Deleted Compounds")
        file_menu.addSeparator()
        file_menu.addAction("Export Integrals")
        file_menu.addSeparator()
        file_menu.addAction("Load Session")
        file_menu.addAction("Save Session")
        file_menu.addAction("Clear Session")
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

        # Load and apply the stylesheet
        stylesheet = load_stylesheet("src/manic/resources/style.qss")
        self.setStyleSheet(stylesheet)