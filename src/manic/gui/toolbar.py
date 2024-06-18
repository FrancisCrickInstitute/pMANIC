from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, Signal
from src.manic.utils.constants import FONT, GREEN, RED


class Toolbar(QWidget):
    updateChartSignal = Signal()
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        # Create the toolbar layout
        toolbar_layout = QVBoxLayout()

        # Add label indicators for loaded data
        loaded_data_widget = QWidget()
        loaded_data_widget.setObjectName("loadedDataWidget")
        loaded_data_widget_layout = QHBoxLayout()
        data_loading_labels = [
            ("Raw Data", RED),
            ("Compound List", GREEN)
        ]
        for text, color in data_loading_labels:
            label = QLabel(text)
            label.setAlignment(Qt.AlignCenter)
            label.setAutoFillBackground(True)
            font = QFont(FONT, 12)
            label.setFont(font)
            label.setFixedSize(125, 50)
            label.setStyleSheet(f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, "
                                f"{color.alpha() / 255}); color: black; border-radius: 10px;")
            loaded_data_widget_layout.addWidget(label)
        loaded_data_widget.setLayout(loaded_data_widget_layout)
        toolbar_layout.addWidget(loaded_data_widget)

        # Add a vertical spacer
        toolbar_layout.addSpacing(10)

        # Add current metabolite indicator
        current_metabolite_widget = QLabel("- No Metabolite Selected -")
        current_metabolite_widget.setFont(QFont(FONT, 12))
        current_metabolite_widget.setAlignment(Qt.AlignCenter)
        current_metabolite_widget.setStyleSheet("border: 1px solid lightgray; border-radius: 10px; padding: 5px;")
        toolbar_layout.addWidget(current_metabolite_widget)

        # Add selected standard indicator
        current_standard_widget = QLabel("- No Standard Selected -")
        current_standard_widget.setFont(QFont(FONT, 12))
        current_standard_widget.setAlignment(Qt.AlignCenter)
        current_standard_widget.setStyleSheet("border: 1px solid lightgray; border-radius: 10px; padding: 5px;")
        toolbar_layout.addWidget(current_standard_widget)

        # Add a vertical spacer
        toolbar_layout.addSpacing(10)

        # Add samples loaded widget
        sample_list_widget = QListWidget()
        sample_list_widget.setFont(QFont(FONT, 10))
        sample_list_widget.setFixedHeight(150)
        no_samples_item = QListWidgetItem("- No Samples Loaded -")
        sample_list_widget.addItem(no_samples_item)
        sample_list_widget.setCurrentItem(no_samples_item)
        toolbar_layout.addWidget(sample_list_widget)

        # Add compounds loaded widget
        loaded_compounds_widget = QListWidget()
        loaded_compounds_widget.setFont(QFont(FONT, 10))
        loaded_compounds_widget.setFixedHeight(150)
        no_compounds_item = QListWidgetItem("- No Compounds Loaded -")
        loaded_compounds_widget.addItem(no_compounds_item)
        loaded_compounds_widget.setCurrentItem(no_samples_item)
        toolbar_layout.addWidget(loaded_compounds_widget)

        # Add "Update Chart" button
        update_chart_button = QPushButton("Update Chart")
        update_chart_button.clicked.connect(self.emit_update_chart_signal)
        toolbar_layout.addWidget(update_chart_button)

        # Add a spacer item to push all elements to the top
        toolbar_layout.addStretch()

        # Set the toolbar layout
        self.setLayout(toolbar_layout)
        self.setFixedWidth(300)

    def emit_update_chart_signal(self):
        self.updateChartSignal.emit()
