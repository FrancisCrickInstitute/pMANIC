from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.manic.utils.constants import FONT, GREEN, RED


class Toolbar(QWidget):
    # the currently selected compound
    compound_selected = Signal(str)

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

        # Add selected standard indicator
        current_standard_widget = QLabel("- No Standard Selected -")
        current_standard_widget.setFont(QFont(FONT, 12))
        current_standard_widget.setAlignment(Qt.AlignCenter)
        current_standard_widget.setStyleSheet(
            "border: 1px solid lightgray; border-radius: 10px; padding: 5px;"
        )
        toolbar_layout.addWidget(current_standard_widget)

        # Add a vertical spacer
        toolbar_layout.addSpacing(5)

        # Add samples loaded widget
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

        # Add compounds loaded widget
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

        # Add a spacer item to push all elements to the top
        toolbar_layout.addStretch()

        # Set the toolbar layout
        self.setLayout(toolbar_layout)
        self.setFixedWidth(200)

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
        Returns the text of the currently selected compound, or None if nothing is selected.
        """
        selected_items = self.loaded_compounds_widget.selectedItems()
        if selected_items:
            return selected_items[
                0
            ].text()  # Return the text of the first selected item
        return None  # Or an empty string, depending on your needs

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
                for i in range(
                    self.loaded_samples_widget.count()
                ):  # iterate over all samples
                    item = self.loaded_samples_widget.item(i)
                    item.setSelected(True)  # select each item
