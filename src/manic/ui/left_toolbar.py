from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.manic.utils.constants import FONT, GREEN, RED


class Toolbar(QWidget):
    # Signal for the currently selected samples
    samples_selected = Signal(list)

    # Signal for the currently selected compound
    compound_selected = Signal(str)

    #####
    # Instantiate Toolbar Components
    #####
    def __init__(self):
        super().__init__()
        self.setup_ui()

    #####
    # Define Toolbar Components
    #####
    def setup_ui(self):
        #####
        # Toolbar Created
        #####
        toolbar_layout = QVBoxLayout()

        #####
        # Loaded Data Indicators
        #####
        loaded_data_widget = QWidget()
        loaded_data_widget.setObjectName("loadedDataWidget")
        loaded_data_widget_layout = QHBoxLayout()
        loaded_data_widget_layout.setContentsMargins(0, 0, 0, 0)
        data_loading_labels = [("Raw Data", RED), ("Compounds", RED)]
        for text, color in data_loading_labels:
            label = QLabel(text)
            label.setAlignment(Qt.AlignCenter)
            label.setAutoFillBackground(True)
            font = QFont(FONT, 10)
            label.setFont(font)
            label.setFixedSize(75, 20)
            label.setStyleSheet(
                f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, "
                f"{color.alpha() / 255}); color: black; border-radius: 10px;"
            )
            loaded_data_widget_layout.addWidget(label)
        loaded_data_widget.setLayout(loaded_data_widget_layout)
        toolbar_layout.addWidget(loaded_data_widget)

        #####
        # Internal Standard Indicator
        #####
        current_standard_widget = QLabel("- No Standard Selected -")
        current_standard_widget.setFont(QFont(FONT, 12))
        current_standard_widget.setAlignment(Qt.AlignCenter)
        current_standard_widget.setStyleSheet(
            "border: 1px solid lightgray; border-radius: 10px; padding: 5px;"
        )
        toolbar_layout.addWidget(current_standard_widget)

        #####
        # Sample List
        #####
        self.loaded_samples_widget = QListWidget()
        self.loaded_samples_widget.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )  # allow multi select with shift
        self.loaded_samples_widget.setFont(QFont(FONT, 10))
        self.loaded_samples_widget.setFixedHeight(150)
        # list empty when created so no compounds item added
        no_samples_item = QListWidgetItem("- No Samples Loaded -")
        self.loaded_samples_widget.addItem(no_samples_item)
        self.loaded_samples_widget.setCurrentItem(no_samples_item)
        # add samples list to toolbar
        toolbar_layout.addWidget(self.loaded_samples_widget)

        # connect signal to slot
        self.loaded_samples_widget.itemSelectionChanged.connect(
            self.on_samples_selection_changed
        )

        ######
        # Compounds List
        ######
        self.loaded_compounds_widget = QListWidget()
        self.loaded_compounds_widget.setFont(QFont(FONT, 10))
        self.loaded_compounds_widget.setFixedHeight(150)
        # only allow the selection of a single compound at a time
        self.loaded_compounds_widget.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        # list empty when created so no compounds item added
        no_compounds_item = QListWidgetItem("- No Compounds Loaded -")
        self.loaded_compounds_widget.addItem(no_compounds_item)
        self.loaded_compounds_widget.setCurrentItem(no_compounds_item)

        # add compounds list to toolbar
        toolbar_layout.addWidget(self.loaded_compounds_widget)

        # connect signal to slot
        self.loaded_compounds_widget.itemSelectionChanged.connect(
            self.on_compound_selection_changed
        )

        ################################
        ###### CURRENT DEV STARTS ######
        ################################
        ## integration window
        integration_window = QGroupBox("Integration Window")
        # Set the stylesheet for the groupbox title
        integration_window.setStyleSheet(
            "QGroupBox { background-color: #F0F0F0; border: solid gray; margin-top: 2ex;}"
            "QGroupBox::title { color: black; subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px;}"
        )

        # vertical layout for integraton window
        int_wnd_vlayout = QVBoxLayout()

        # int window first row
        int_wnd_row1 = QHBoxLayout()
        lo_label = QLabel("Left Offset")
        lo_label.setStyleSheet("QLabel { background-color: #F0F0F0; }")
        lo_input = QLineEdit()
        # Set the background color to a light gray
        lo_input.setStyleSheet("QLineEdit { background-color: white; }")
        int_wnd_row1.addWidget(lo_label)
        int_wnd_row1.addWidget(lo_input)
        int_wnd_vlayout.addLayout(int_wnd_row1)

        # int window second row
        int_wnd_row2 = QHBoxLayout()
        tr_label = QLabel("tR")
        tr_label.setStyleSheet("QLabel { background-color: #F0F0F0; }")
        tr_input = QLineEdit()
        # Set the background color to a light gray
        tr_input.setStyleSheet("QLineEdit { background-color: white; }")
        int_wnd_row2.addWidget(tr_label)
        int_wnd_row2.addWidget(tr_input)
        int_wnd_vlayout.addLayout(int_wnd_row2)

        # int window third row
        int_wnd_row3 = QHBoxLayout()
        ro_label = QLabel("Right Offset")
        ro_label.setStyleSheet("QLabel { background-color: #F0F0F0; }")
        ro_input = QLineEdit()
        # Set the background color to a light gray
        ro_input.setStyleSheet("QLineEdit { background-color: white; }")
        int_wnd_row3.addWidget(ro_label)
        int_wnd_row3.addWidget(ro_input)
        int_wnd_vlayout.addLayout(int_wnd_row3)

        # int window fourth row
        int_wnd_row4 = QHBoxLayout()
        tr_window_label = QLabel("tR Window")
        tr_window_label.setStyleSheet("QLabel { background-color: #F0F0F0; }")
        tr_window_input = QLineEdit()
        # Set the background color to a light gray
        tr_window_input.setStyleSheet("QLineEdit { background-color: white; }")
        int_wnd_row4.addWidget(tr_window_label)
        int_wnd_row4.addWidget(tr_window_input)
        int_wnd_vlayout.addLayout(int_wnd_row4)

        # set the integration window vertical layout
        integration_window.setLayout(int_wnd_vlayout)

        toolbar_layout.addWidget(integration_window)

        ################################
        ###### CURRENT DEV ENDS ######
        ################################

        #####
        # Toolbar Formatting
        #####

        # Add a spacer item to push all elements to the top
        toolbar_layout.addStretch()
        # Set the toolbar layout
        self.setLayout(toolbar_layout)
        self.setFixedWidth(200)

    #####
    # Toolbar Functions
    #####

    def update_label_colours(self, raw_data_loaded, compound_list_loaded):
        labels = self.findChildren(QLabel)
        for label in labels:
            if label.text() == "Raw Data":
                color = GREEN if raw_data_loaded else RED
            elif label.text() == "Compounds":
                color = GREEN if compound_list_loaded else RED
            else:
                continue
            label.setStyleSheet(
                f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, "
                f"{color.alpha() / 255}); color: black; border-radius: 10px;"
            )

    def update_compound_list(self, compounds: List[str]):
        self.loaded_compounds_widget.clear()
        if not compounds:
            self.loaded_compounds_widget.addItem("- No Compounds Loaded -")
        else:
            for compound_name in compounds:
                item = QListWidgetItem(compound_name)
                self.loaded_compounds_widget.addItem(item)

            # set the first item in compounds list as the selected one
            first_item = self.loaded_compounds_widget.item(0)  # Get the first item
            self.loaded_compounds_widget.setCurrentItem(
                first_item
            )  # Set it as the selected item

    def on_compound_selection_changed(self):
        """
        Handler for when the selection changes in the list widget.
        Emits the custom signal with the selected item's text.
        """
        selected_items = self.loaded_compounds_widget.selectedItems()
        if selected_items:
            selected_text = selected_items[
                0
            ].text()  # Get the text of the first selected item
            self.compound_selected.emit(selected_text)  # Emit the custom signal
        else:
            # Optional: Emit something for no selection (e.g., an empty string)
            self.compound_selected.emit("")

    def get_selected_compound(self):
        """
        Get the currently selected compound without emitting signals.
        Avoid infinite recursion via signals.
        Returns a string.
        """
        selected_items = self.loaded_compounds_widget.selectedItems()
        if selected_items:
            return selected_items[0].text()
        else:
            return ""

    def update_sample_list(self, samples: List[str]):
        self.loaded_samples_widget.clear()
        if not samples:
            self.loaded_samples_widget.addItem("- No Samples Loaded -")
        else:
            for sample_name in samples:
                item = QListWidgetItem(sample_name)
                self.loaded_samples_widget.addItem(item)
            # select all samples as default
            if self.loaded_samples_widget.count() > 0:  # Check if there are items
                self.loaded_samples_widget.selectAll()

    def on_samples_selection_changed(self):
        """
        Handler for when the selection changes in the list widget.
        Emits the custom signal with the selected item's text.
        """
        selected_items = self.loaded_samples_widget.selectedItems()
        if selected_items:
            selected_samples = [item.text() for item in selected_items]
            self.samples_selected.emit(selected_samples)  # Emit the custom signal
        else:
            self.samples_selected.emit([])

    def get_selected_samples(self):
        """
        Get the currently selected samples without emitting signals.
        Avoid infinite recursion via signals.
        Returns a list of strings.
        """
        selected_items = self.loaded_samples_widget.selectedItems()
        if selected_items:
            return [item.text() for item in selected_items]
        else:
            return []
