from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from manic.io.compound_reader import read_compound
from manic.utils.paths import resource_path

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

    # Signal for when internal standard is selected
    internal_standard_selected = Signal(str)

    # Signal for when compounds are deleted
    compounds_deleted = Signal(list)

    # Signal for when compounds are restored
    compounds_restored = Signal(list)

    # Signal for when samples are deleted
    samples_deleted = Signal(list)

    # Signal for when samples are restored
    samples_restored = Signal(list)

    # Signal emitted when baseline correction checkbox is toggled
    baseline_correction_changed = Signal(str, bool)  # compound_name, enabled

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

        # Group indicators together in a compact container
        # Minimize vertical space while maintaining visual grouping
        indicators_container = QWidget()
        # Remove any border styling from the container
        indicators_container.setStyleSheet("""
            QWidget {
                border: none;
                background-color: transparent;
            }
        """)
        indicators_layout = QVBoxLayout(indicators_container)
        indicators_layout.setContentsMargins(2, 2, 2, 2)  # Minimal padding
        indicators_layout.setSpacing(4)  # Reduced spacing between indicators
        indicators_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )

        self.loaded_data = LoadedDataWidget()
        indicators_layout.addWidget(
            self.loaded_data, alignment=Qt.AlignmentFlag.AlignCenter
        )

        # Add extra vertical spacing between data indicators and standard indicator
        indicators_layout.addSpacing(8)  # Additional spacing

        self.standard = StandardIndicator()
        indicators_layout.addWidget(
            self.standard, alignment=Qt.AlignmentFlag.AlignCenter
        )

        self.mz_indicator = QLabel("m/z - --")
        self.mz_indicator.setFont(self.standard.font())
        self.mz_indicator.setAlignment(Qt.AlignCenter)
        self.mz_indicator.setFixedSize(self.standard.size())
        self.mz_indicator.setStyleSheet(
            "background-color: #e9ecef; color: black; border-radius: 10px; padding: 2px;"
        )
        indicators_layout.addWidget(
            self.mz_indicator, alignment=Qt.AlignmentFlag.AlignCenter
        )

        # Compact the container to fit content size
        indicators_container.setMaximumHeight(
            self.loaded_data.sizeHint().height()
            + self.standard.sizeHint().height()
            + self.mz_indicator.sizeHint().height()
            + 24  # Account for margins, spacing, and extra vertical gap
        )

        # Add the container to the main layout with no stretch
        content_layout.addWidget(indicators_container, stretch=0)

        self.sample_list = SampleListWidget()
        content_layout.addWidget(
            self.sample_list, stretch=1
        )  # Give sample list more space

        self.compound_list = CompoundListWidget()
        content_layout.addWidget(
            self.compound_list, stretch=1
        )  # Give compound list more space

        self.integration = IntegrationWindow()
        content_layout.addWidget(
            self.integration, stretch=0
        )  # No stretch for integration window

        # Baseline correction checkbox (between integration window and plots)
        self.baseline_checkbox = QCheckBox("Baseline correction")
        self.baseline_checkbox.setObjectName("baseline_correction_checkbox")
        self.baseline_checkbox.setToolTip(
            "Enable linear baseline subtraction for this compound.\n"
            "Fits a line through 3 points at each edge of the integration window\n"
            "and subtracts the area under this baseline from the peak area."
        )
        self.baseline_checkbox.stateChanged.connect(self._on_baseline_checkbox_toggled)
        # Apply checkbox styling
        checkmark_path = resource_path("resources", "checkmark.svg").replace("\\", "/")
        self.baseline_checkbox.setStyleSheet(f"""
            QCheckBox {{
                background-color: transparent;
                color: black;
                spacing: 8px;
                padding: 10px 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: none;
                border-radius: 3px;
                background-color: #e9ecef;
            }}
            QCheckBox::indicator:checked {{
                background-color: #0d6efd;
                image: url({checkmark_path});
            }}
            QCheckBox::indicator:hover {{
                background-color: #d0d0d0;
            }}
        """)
        content_layout.addWidget(self.baseline_checkbox, stretch=0)

        self.isotopologue_ratios = IsotopologueRatioWidget()
        content_layout.addWidget(
            self.isotopologue_ratios, stretch=2
        )  # Increased stretch for plots

        self.total_abundance = TotalAbundanceWidget()
        content_layout.addWidget(
            self.total_abundance, stretch=2
        )  # Increased stretch for plots

        scroll_area.setWidget(content_widget)
        container_layout.addWidget(scroll_area)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

        # self.setFixedWidth(222)
        self.setMinimumWidth(222)

        self.setLayout(main_layout)

    def _connect_signals(self):
        """Connect child widget signals to toolbar signal handlers"""
        self.sample_list.itemSelectionChanged.connect(self.on_samples_selection_changed)
        self.compound_list.itemSelectionChanged.connect(
            self.on_compound_selection_changed
        )
        self.compound_list.internal_standard_selected.connect(
            self.on_internal_standard_selected
        )
        self.compound_list.compounds_deleted.connect(self.compounds_deleted.emit)
        self.compound_list.compounds_restored.connect(self.compounds_restored.emit)
        self.compound_list.internal_standard_cleared.connect(
            self.on_internal_standard_cleared
        )
        self.sample_list.samples_deleted.connect(self.samples_deleted.emit)
        self.sample_list.samples_restored.connect(self.samples_restored.emit)

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
            self._set_mz_indicator_from_compound(selected_text)
            # Initial fill - will be updated by plot selection logic after plotting
            self.fill_integration_window(selected_text)
            # Update baseline checkbox state
            self._set_baseline_checkbox_from_compound(selected_text)
        else:
            self.compound_selected.emit("")
            self.mz_indicator.setText("m/z - --")



    def on_internal_standard_selected(self, compound_name: str):
        """
        Handler for when a compound is selected as internal standard.
        Updates the standard indicator widget and emits signal.
        """
        self.standard.set_internal_standard(compound_name)
        self.internal_standard_selected.emit(compound_name)

    # --- Public Methods ---
    def update_label_colours(self, raw_data_loaded, compound_list_loaded):
        """Update the status indicators via the LoadedDataWidget"""
        self.loaded_data.update_status(raw_data_loaded, compound_list_loaded)

    def update_compound_list(self, compounds: List[str]):
        """Update the compounds list widget"""
        self.compound_list.update_compounds(compounds)
        self._set_mz_indicator_from_compound(self.get_selected_compound())

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

    def get_internal_standard(self):
        """
        Get the currently selected internal standard.
        Returns the compound name or None if no standard is selected.
        """
        return self.standard.internal_standard

    def fill_integration_window(self, compound_name: str):
        """
        Legacy method - no longer used.

        Integration window fields are now populated by populate_fields_from_plots()
        which properly handles session data overrides. This method previously
        populated fields with base compound data, overwriting session values.
        """
        pass

    def _set_mz_indicator_from_compound(self, compound_name: str) -> None:
        try:
            comp = read_compound(compound_name)
            self.mz_indicator.setText(f"m/z - {comp.mass0}")
        except Exception:
            self.mz_indicator.setText("m/z - --")

    def _set_baseline_checkbox_from_compound(self, compound_name: str):
        """Set baseline correction checkbox state from compound data."""
        try:
            comp = read_compound(compound_name)
            enabled = bool(getattr(comp, "baseline_correction", 0))
            self.baseline_checkbox.blockSignals(True)
            self.baseline_checkbox.setChecked(enabled)
            self.baseline_checkbox.blockSignals(False)
        except Exception:
            self.baseline_checkbox.blockSignals(True)
            self.baseline_checkbox.setChecked(False)
            self.baseline_checkbox.blockSignals(False)

    def _on_baseline_checkbox_toggled(self, state: int):
        """Handle baseline correction checkbox toggle - update DB and emit signal."""
        compound_name = self.get_selected_compound()
        if not compound_name:
            return

        enabled = state != 0

        try:
            from manic.models.database import get_connection

            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE compounds
                    SET baseline_correction = ?
                    WHERE compound_name = ? AND deleted = 0
                    """,
                    (1 if enabled else 0, compound_name),
                )

            self.baseline_correction_changed.emit(compound_name, enabled)

        except Exception as e:
            print(f"Failed to update baseline setting: {e}")
            self._set_baseline_checkbox_from_compound(compound_name)

    def on_internal_standard_cleared(self):
        """Handler for clearing the internal standard."""
        self.standard.clear_internal_standard()  # Calls existing method
        self.internal_standard_selected.emit(None)  # Notify MainWindow standard is gone
