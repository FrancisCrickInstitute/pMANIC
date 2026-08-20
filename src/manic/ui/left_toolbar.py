from dataclasses import dataclass
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from manic.io.compound_reader import read_compound
from manic.models.analysis import AnalysisMode
from manic.utils.paths import resource_path

from .compound_list_widget import CompoundListWidget
from .integration_window_widget import IntegrationWindow
from .isotopologue_ratio_widget import IsotopologueRatioWidget
from .loaded_data_widget import LoadedDataWidget
from .sample_list_widget import SampleListWidget
from .standard_indicator_widget import StandardIndicator
from .targeted_qc_widget import TargetedQcWidget
from .total_abundance_widget import TotalAbundanceWidget


@dataclass(frozen=True, slots=True)
class UnlabelledToolbarLayoutSpec:
    list_max_height: int = 120
    qc_min_height: int = 260
    qc_split_share: float = 0.42
    toolbar_min_width: int = 272


class Toolbar(QWidget):
    samples_selected = Signal(list)
    compound_selected = Signal(str)
    internal_standard_selected = Signal(str)
    compounds_deleted = Signal(list)
    compounds_restored = Signal(list)
    samples_deleted = Signal(list)
    samples_restored = Signal(list)
    baseline_correction_changed = Signal(str, bool)
    shared_y_scale_toggled = Signal(bool)
    targeted_trace_normalization_toggled = Signal(bool)

    def __init__(
        self,
        analysis_mode: AnalysisMode | str = AnalysisMode.LABELLED,
    ):
        super().__init__()
        self.analysis_mode = AnalysisMode.coerce(analysis_mode)
        self.setObjectName("toolbar")
        self._layout_spec = UnlabelledToolbarLayoutSpec()
        self._unlabelled_sizes_applied = False
        self.load_status_label = None
        self.is_status_label = None
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        self.loaded_data = LoadedDataWidget()
        self.standard = StandardIndicator()
        self.sample_list = SampleListWidget()
        self.compound_list = CompoundListWidget()
        self.integration = IntegrationWindow(self.analysis_mode)
        self._build_plot_toggles()
        self.targeted_qc = TargetedQcWidget()

        if self.analysis_mode is AnalysisMode.UNLABELLED:
            self.isotopologue_ratios = None
            self.total_abundance = None
            self._assemble_unlabelled()
        else:
            self.isotopologue_ratios = IsotopologueRatioWidget()
            self.total_abundance = TotalAbundanceWidget()
            self._assemble_labelled()

    def _checkbox_stylesheet(self, compact: bool) -> str:
        checkmark_path = resource_path("resources", "checkmark.svg").replace("\\", "/")
        padding = "2px 4px" if compact else "10px 8px"
        return f"""
            QCheckBox {{
                background-color: transparent;
                color: black;
                spacing: 6px;
                padding: {padding};
                border: none;
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
        """

    def _build_plot_toggles(self):
        compact = self.analysis_mode is AnalysisMode.UNLABELLED
        stylesheet = self._checkbox_stylesheet(compact)

        self.baseline_checkbox = QCheckBox("Baseline correction")
        self.baseline_checkbox.setObjectName("baseline_correction_checkbox")
        self.baseline_checkbox.setToolTip(
            "Enable linear baseline subtraction for this compound.\n"
            "Fits a line through 3 points at each edge of the integration window\n"
            "and subtracts the area under this baseline from the peak area."
        )
        self.baseline_checkbox.stateChanged.connect(self._on_baseline_checkbox_toggled)
        self.baseline_checkbox.setStyleSheet(stylesheet)

        self.shared_yscale_checkbox = QCheckBox("Shared y-scale")
        self.shared_yscale_checkbox.setObjectName("shared_yscale_checkbox")
        self.shared_yscale_checkbox.setToolTip(
            "Use one common intensity scale for all sample plots.\n"
            "Off: each plot autoscales to its own tallest peak."
        )
        self.shared_yscale_checkbox.setStyleSheet(stylesheet)
        self.shared_yscale_checkbox.stateChanged.connect(
            lambda state: self.shared_y_scale_toggled.emit(state != 0)
        )

        self.targeted_trace_normalization_checkbox = QCheckBox("Normalize Q/V shapes")
        self.targeted_trace_normalization_checkbox.setObjectName(
            "targeted_trace_normalization_checkbox"
        )
        self.targeted_trace_normalization_checkbox.setToolTip(
            "Scale each V-ion trace to the Q-ion peak height so their chromatographic "
            "shapes and apex alignment can be compared visually.\n"
            "Display only: integration and exported areas always use the original signals."
        )
        self.targeted_trace_normalization_checkbox.setStyleSheet(stylesheet)
        self.targeted_trace_normalization_checkbox.stateChanged.connect(
            lambda state: self.targeted_trace_normalization_toggled.emit(state != 0)
        )

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            "color: #334155; font-size: 11px; font-weight: 600; "
            "background-color: transparent; border: none;"
        )
        return label

    def _quiet_status_label(self, object_name: str, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setStyleSheet(
            "color: #64748b; font-size: 11px; background-color: transparent; border: none;"
        )
        return label

    def _build_status_strip(self) -> QWidget:
        strip = QWidget()
        strip.setObjectName("unlabelledStatusStrip")
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(0, 0, 2, 2)
        layout.setSpacing(10)

        self.load_status_label = self._quiet_status_label(
            "unlabelledLoadStatus", ""
        )
        self.is_status_label = self._quiet_status_label("unlabelledIsStatus", "IS —")
        self.mz_indicator = self._quiet_status_label(
            "unlabelledIonStatus", "Q-ion m/z —"
        )
        self._refresh_load_status(False, False)
        self._refresh_is_status()

        layout.addWidget(self.load_status_label, 0)
        layout.addWidget(self.is_status_label, 0)
        layout.addStretch(1)
        layout.addWidget(self.mz_indicator, 0)
        return strip

    def _assemble_unlabelled(self):
        spec = self._layout_spec
        self.standard.hide()
        self.loaded_data.hide()
        self.baseline_checkbox.setText("Baseline")
        self.shared_yscale_checkbox.setText("Shared y-scale")
        self.targeted_trace_normalization_checkbox.setText("Normalize Q/V")

        self.sample_list.setMaximumHeight(spec.list_max_height)
        self.compound_list.setMaximumHeight(spec.list_max_height)
        self.integration.setMinimumWidth(0)

        session = QWidget()
        session_layout = QVBoxLayout(session)
        session_layout.setContentsMargins(10, 10, 10, 8)
        session_layout.setSpacing(6)
        session_layout.addWidget(self._build_status_strip(), 0)
        session_layout.addWidget(self._section_label("Samples"), 0)
        session_layout.addWidget(self.sample_list, 0)
        session_layout.addWidget(self._section_label("Compounds"), 0)
        session_layout.addWidget(self.compound_list, 0)
        session_layout.addWidget(self.integration, 0)

        toggles = QWidget()
        toggles.setObjectName("plotToggleStrip")
        toggle_grid = QGridLayout(toggles)
        toggle_grid.setContentsMargins(0, 0, 0, 0)
        toggle_grid.setHorizontalSpacing(10)
        toggle_grid.setVerticalSpacing(2)
        for checkbox in (
            self.baseline_checkbox,
            self.shared_yscale_checkbox,
            self.targeted_trace_normalization_checkbox,
        ):
            checkbox.setSizePolicy(
                QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
            )
        toggle_grid.addWidget(self.baseline_checkbox, 0, 0)
        toggle_grid.addWidget(self.shared_yscale_checkbox, 0, 1)
        toggle_grid.addWidget(
            self.targeted_trace_normalization_checkbox, 1, 0, 1, 2
        )
        session_layout.addWidget(toggles, 0)
        session_layout.addStretch(1)

        session_scroll = QScrollArea()
        session_scroll.setWidgetResizable(True)
        session_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        session_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        session_scroll.setFrameShape(QFrame.NoFrame)
        session_scroll.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        session_scroll.setWidget(session)

        self.targeted_qc.setMinimumHeight(spec.qc_min_height)
        self.targeted_qc.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setObjectName("unlabelledToolbarSplitter")
        splitter.addWidget(session_scroll)
        splitter.addWidget(self.targeted_qc)
        splitter.setCollapsible(1, False)
        session_share = 1.0 - spec.qc_split_share
        splitter.setStretchFactor(0, int(round(session_share * 100)))
        splitter.setStretchFactor(1, int(round(spec.qc_split_share * 100)))
        default_total = 900
        qc_size = max(spec.qc_min_height, int(default_total * spec.qc_split_share))
        splitter.setSizes([default_total - qc_size, qc_size])

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(splitter)
        self.setMinimumWidth(spec.toolbar_min_width)

    def _assemble_labelled(self):
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

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)

        indicators_container = QWidget()
        indicators_container.setStyleSheet("""
            QWidget {
                border: none;
                background-color: transparent;
            }
        """)
        indicators_layout = QVBoxLayout(indicators_container)
        indicators_layout.setContentsMargins(2, 2, 2, 2)
        indicators_layout.setSpacing(4)
        indicators_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )

        indicators_layout.addWidget(
            self.loaded_data, alignment=Qt.AlignmentFlag.AlignCenter
        )
        indicators_layout.addSpacing(8)
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

        indicators_container.setMaximumHeight(
            self.loaded_data.sizeHint().height()
            + self.standard.sizeHint().height()
            + self.mz_indicator.sizeHint().height()
            + 24
        )
        content_layout.addWidget(indicators_container, stretch=0)

        content_layout.addWidget(self.sample_list, stretch=1)
        content_layout.addWidget(self.compound_list, stretch=1)
        content_layout.addWidget(self.integration, stretch=0)
        content_layout.addWidget(self.baseline_checkbox, stretch=0)
        content_layout.addWidget(self.shared_yscale_checkbox, stretch=0)
        content_layout.addWidget(
            self.targeted_trace_normalization_checkbox, stretch=0
        )
        content_layout.addWidget(self.isotopologue_ratios, stretch=2)
        content_layout.addWidget(self.total_abundance, stretch=2)
        content_layout.addWidget(self.targeted_qc, stretch=1)

        self.targeted_qc.hide()
        self.targeted_trace_normalization_checkbox.hide()

        scroll_area.setWidget(content_widget)
        container_layout.addWidget(scroll_area)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)
        self.setMinimumWidth(256)

    def _apply_unlabelled_splitter_sizes(self):
        splitter = self.findChild(QSplitter, "unlabelledToolbarSplitter")
        if splitter is None:
            return
        spec = self._layout_spec
        total = splitter.height() or self.height()
        if total <= 0:
            return
        qc_size = max(spec.qc_min_height, int(total * spec.qc_split_share))
        session_size = max(1, total - qc_size)
        splitter.setSizes([session_size, qc_size])

    def showEvent(self, event):
        super().showEvent(event)
        if (
            self.analysis_mode is AnalysisMode.UNLABELLED
            and not self._unlabelled_sizes_applied
            and self.height() > 0
        ):
            self._apply_unlabelled_splitter_sizes()
            self._unlabelled_sizes_applied = True

    def _connect_signals(self):
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

    def on_samples_selection_changed(self):
        selected_items = self.sample_list.selectedItems()
        if selected_items:
            selected_samples = [item.text() for item in selected_items]
            self.samples_selected.emit(selected_samples)
        else:
            self.samples_selected.emit([])

    def on_compound_selection_changed(self):
        selected_items = self.compound_list.selectedItems()
        if selected_items:
            selected_text = selected_items[0].text()
            self.compound_selected.emit(selected_text)
            self._set_mz_indicator_from_compound(selected_text)
            self._set_baseline_checkbox_from_compound(selected_text)
        else:
            self.compound_selected.emit("")
            if self.analysis_mode is AnalysisMode.UNLABELLED:
                self.mz_indicator.setText("Q-ion m/z —")
            else:
                self.mz_indicator.setText("m/z - --")

    def on_internal_standard_selected(self, compound_name: str):
        self.standard.set_internal_standard(compound_name)
        self._refresh_is_status()
        self.internal_standard_selected.emit(compound_name)

    def update_label_colours(self, raw_data_loaded, compound_list_loaded):
        self.loaded_data.update_status(raw_data_loaded, compound_list_loaded)
        self._refresh_load_status(raw_data_loaded, compound_list_loaded)

    def update_compound_list(self, compounds: List[str]):
        self.compound_list.update_compounds(compounds)
        self._set_mz_indicator_from_compound(self.get_selected_compound())

    def update_sample_list(self, samples: List[str]):
        self.sample_list.update_samples(samples)

    def get_selected_samples(self):
        selected_items = self.sample_list.selectedItems()
        if selected_items:
            return [item.text() for item in selected_items]
        return []

    def get_selected_compound(self):
        selected_items = self.compound_list.selectedItems()
        if selected_items:
            return selected_items[0].text()
        return ""

    def get_internal_standard(self):
        return self.standard.internal_standard

    def clear_internal_standard(self):
        self.standard.clear_internal_standard()
        self._refresh_is_status()

    def _refresh_load_status(self, raw_loaded: bool, compounds_loaded: bool) -> None:
        if self.load_status_label is None:
            return
        raw = "●" if raw_loaded else "○"
        compounds = "●" if compounds_loaded else "○"
        self.load_status_label.setText(f"{raw} Raw  {compounds} Compounds")

    def _refresh_is_status(self) -> None:
        if self.is_status_label is None:
            return
        name = self.standard.internal_standard
        if name:
            self.is_status_label.setText(f"IS {name}")
            self.is_status_label.setStyleSheet(
                "color: #334155; font-size: 11px; "
                "background-color: transparent; border: none;"
            )
        else:
            self.is_status_label.setText("IS —")
            self.is_status_label.setStyleSheet(
                "color: #94a3b8; font-size: 11px; "
                "background-color: transparent; border: none;"
            )

    def _set_mz_indicator_from_compound(self, compound_name: str) -> None:
        if self.analysis_mode is AnalysisMode.UNLABELLED:
            empty = "Q-ion m/z —"
            try:
                comp = read_compound(compound_name)
                channels = comp.analysis_channels
                if channels:
                    self.mz_indicator.setText(f"Q-ion m/z {channels[0].mz:g}")
                else:
                    self.mz_indicator.setText(empty)
            except Exception:
                self.mz_indicator.setText(empty)
            return
        try:
            comp = read_compound(compound_name)
            self.mz_indicator.setText(f"m/z - {comp.mass0}")
        except Exception:
            self.mz_indicator.setText("m/z - --")

    def _set_baseline_checkbox_from_compound(self, compound_name: str):
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
        self.clear_internal_standard()
        self.internal_standard_selected.emit(None)
