import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QLineEdit, QCheckBox, QPushButton, QMenuBar, QMenu, QGridLayout, QGraphicsView)
from PySide6.QtGui import QPalette, QColor, QFont
from PySide6.QtCore import Qt

APPLICATION_VERSION = "1.0.0"


class MANIC(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MANIC")

        # Set the application style and palette for a light theme
        app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
        palette.setColor(QPalette.Base, QColor(240, 240, 240))
        palette.setColor(QPalette.AlternateBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
        palette.setColor(QPalette.Text, QColor(0, 0, 0))
        palette.setColor(QPalette.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
        palette.setColor(QPalette.BrightText, QColor(255, 255, 255))
        palette.setColor(QPalette.Link, QColor(0, 0, 255))
        palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        app.setPalette(palette)

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

        # Create the main widow layout
        main_layout = QHBoxLayout()  # Window split into two columns

        # Create toolbar on the left hand side
        left_toolbar = QWidget()
        left_toolbar.setFixedWidth(300)  # Set the width of the toolbar
        toolbar_layout = QVBoxLayout()  # Widgets arranged in a vertical layout

        # Add elements to the left toolbar
        loaded_data_widget = QWidget()
        loaded_data_widget_layout = QHBoxLayout()


        color_labels = [
            ("Raw Data", QColor(215, 50, 50)),
            ("Compound List", QColor(102, 215, 102)),
            ("Metadata", QColor(215, 50, 50))
        ]

        for text, color in color_labels:
            label = QLabel(text)
            label.setAlignment(Qt.AlignCenter)
            label.setAutoFillBackground(True)
            font = QFont("Arial", 10)
            label.setFont(font)
            palette = label.palette()
            palette.setColor(QPalette.Window, color)
            palette.setColor(QPalette.WindowText, Qt.black)
            label.setPalette(palette)
            label.setFixedSize(85, 50)  # Set the size of the labels
            label.setStyleSheet(f"background-color: {color.name()}; color: black; border-radius: 10px;")
            loaded_data_widget_layout.addWidget(label)
            loaded_data_widget_layout.addWidget(label)

        loaded_data_widget.setLayout(loaded_data_widget_layout)
        toolbar_layout.addWidget(loaded_data_widget)  # Add the top widget to the toolbar layout

        # Add a spacer item to push all elements to the top
        toolbar_layout.addStretch()

        # Confirm the layout of the left toolbar
        left_toolbar.setLayout(toolbar_layout)

        # Create main content area
        main_content = QWidget()
        main_content_layout = QGridLayout()

        # Determine the number of graphs based on the input data
        num_graphs = 15  # Example value, replace with your actual data

        # Calculate the number of rows and columns for the grid
        num_columns = 3  # Example value, adjust as needed
        num_rows = (num_graphs + num_columns - 1) // num_columns

        # Create and add graph widgets to the grid layout
        for i in range(num_graphs):
            graph = QGraphicsView()
            row = i // num_columns
            column = i % num_columns
            main_content_layout.addWidget(graph, row, column)

        # Confirm the layout of the main content area
        main_content.setLayout(main_content_layout)

        # Add toolbar and main content to the main layout
        main_layout.addWidget(left_toolbar)
        main_layout.addWidget(main_content)
        main_layout.setStretch(1, 1)  # Set the main content to occupy the remaining space

        # Set the main layout as the central widget
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("MANIC")
    app.setApplicationVersion(APPLICATION_VERSION)
    manic = MANIC()
    manic.show()
    sys.exit(app.exec())
