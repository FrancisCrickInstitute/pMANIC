from typing import List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from src.manic.io.compound_reader import read_compound

from .compound_list_widget import CompoundListWidget
from .integration_window_widget import IntegrationWindow
from .loaded_data_widget import LoadedDataWidget
from .sample_list_widget import SampleListWidget
from .standard_indicator_widget import StandardIndicator


class Toolbar(QWidget):
    # Signal for the currently selected samples
    samples_selected = Signal(list)

    # Signal for the currently selected compound
    compound_selected = Signal(str)

    def __init__(self):
        super().__init__()
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        """Set up the toolbar layout and child widgets"""
        layout = QVBoxLayout()

        # Create child widgets
        self.loaded_data = LoadedDataWidget()
        layout.addWidget(self.loaded_data)

        self.standard = StandardIndicator()
        layout.addWidget(self.standard)

        self.sample_list = SampleListWidget()
        layout.addWidget(self.sample_list)

        self.compound_list = CompoundListWidget()
        layout.addWidget(self.compound_list)

        self.integration = IntegrationWindow()
        layout.addWidget(self.integration)

        # Add spacer to push elements to top
        layout.addStretch()
        self.setFixedWidth(200)

        # set the layout
        self.setLayout(layout)

    def _connect_signals(self):
        """Connect child widget signals to toolbar signal handlers"""
        self.sample_list.itemSelectionChanged.connect(self.on_samples_selection_changed)
        self.compound_list.itemSelectionChanged.connect(
            self.on_compound_selection_changed
        )

    # --- Signal Handlers ---
    def on_samples_selection_changed(self):
        """
        Handler for when the selection changes in the samples list widget.
        Emits the custom signal with the selected samples.
        """
        selected_items = self.sample_list.selectedItems()
        if selected_items:
            selected_samples = [item.text() for item in selected_items]
            self.samples_selected.emit(selected_samples)
        else:
            self.samples_selected.emit([])

    def on_compound_selection_changed(self):
        """
        Handler for when the selection changes in the compounds list widget.
        Emits the custom signal with the selected compound.
        """
        selected_items = self.compound_list.selectedItems()
        if selected_items:
            selected_text = selected_items[0].text()
            self.compound_selected.emit(selected_text)
            self.fill_integration_window(selected_text)
        else:
            self.compound_selected.emit("")

    # --- Public Methods ---
    def update_label_colours(self, raw_data_loaded, compound_list_loaded):
        """Update the status indicators via the LoadedDataWidget"""
        self.loaded_data.update_status(raw_data_loaded, compound_list_loaded)

    def update_compound_list(self, compounds: List[str]):
        """Update the compounds list widget"""
        self.compound_list.update_compounds(compounds)

    def update_sample_list(self, samples: List[str]):
        """Update the samples list widget"""
        self.sample_list.update_samples(samples)

    def get_selected_samples(self):
        """
        Get the currently selected samples without emitting signals.
        Avoid infinite recursion via signals.
        Returns a list of strings.
        """
        selected_items = self.sample_list.selectedItems()
        if selected_items:
            return [item.text() for item in selected_items]
        else:
            return []

    def get_selected_compound(self):
        """
        Get the currently selected compound without emitting signals.
        Avoid infinite recursion via signals.
        Returns a string.
        """
        selected_items = self.compound_list.selectedItems()
        if selected_items:
            return selected_items[0].text()
        else:
            return ""

    def fill_integration_window(self, compound_name: str):
        """Fill integration window fields with data for the specified compound"""
        try:
            compound_data = read_compound(compound_name)

            compound_dict = {
                "loffset": compound_data.loffset,
                "retention_time": compound_data.retention_time,
                "roffset": compound_data.roffset,
                "tr_window": getattr(
                    compound_data, "tr_window", 0.2
                ),  # default if not exists
            }

            self.integration.populate_fields(compound_dict)

        except Exception as e:
            print(f"Could not load compound data for {compound_name}: {e}")
            # Clear fields if data can't be loaded
            self.integration.populate_fields(None)
