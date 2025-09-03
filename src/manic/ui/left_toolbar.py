from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.manic.io.compound_reader import read_compound

from .compound_list_widget import CompoundListWidget
from .integration_window_widget import IntegrationWindow
from .isotopologue_ratio_widget import IsotopologueRatioWidget
from .loaded_data_widget import LoadedDataWidget
from .sample_list_widget import SampleListWidget
from .standard_indicator_widget import StandardIndicator
from .total_abundance_widget import TotalAbundanceWidget


class Toolbar(QWidget):
    # Signal for the currently selected samples
    samples_selected = Signal(list)

    # Signal for the currently selected compound
    compound_selected = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("toolbar")  # Required for CSS targeting
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        """Set up the toolbar layout and child widgets"""
        # Container widget provides rounded border appearance
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
            }
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area handles overflow on smaller screens
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea { 
                border: none; 
                background-color: transparent; 
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 8px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Content widget holds all toolbar elements
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)

        self.loaded_data = LoadedDataWidget()
        content_layout.addWidget(self.loaded_data)

        self.standard = StandardIndicator()
        content_layout.addWidget(self.standard)

        self.sample_list = SampleListWidget()
        content_layout.addWidget(self.sample_list)

        self.compound_list = CompoundListWidget()
        content_layout.addWidget(self.compound_list)

        self.integration = IntegrationWindow()
        content_layout.addWidget(self.integration)

        self.isotopologue_ratios = IsotopologueRatioWidget()
        content_layout.addWidget(self.isotopologue_ratios, stretch=1)

        self.total_abundance = TotalAbundanceWidget()
        content_layout.addWidget(self.total_abundance, stretch=1)

        scroll_area.setWidget(content_widget)
        container_layout.addWidget(scroll_area)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)
        
        self.setFixedWidth(222)  # Accounts for border width
        self.setLayout(main_layout)

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
            # Initial fill - will be updated by plot selection logic after plotting
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
        # Skip if compound_name is empty or placeholder text
        if not compound_name or compound_name.startswith("- No") or compound_name.startswith("No "):
            self.integration.populate_fields(None)
            return
            
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
