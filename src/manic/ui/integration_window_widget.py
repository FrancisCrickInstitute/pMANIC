from typing import List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from manic.io.compound_reader import read_compound, read_compound_with_session
from manic.models.session_activity import SessionActivityService
from manic.processors.eic_processing import get_eics_for_compound
from manic.utils.utils import load_stylesheet


class IntegrationWindow(QGroupBox):
    """
    Integration window widget for modifying compound parameters.

    Provides input fields for left offset, retention time, right offset, and tR window,
    along with an apply button that updates session activity data for selected plots.
    The apply button is only enabled when plots are selected.
    """

    # Signal emitted when apply button is clicked and session data is updated
    session_data_applied = Signal(str, list)  # compound_name, sample_names

    # Signal emitted when restore button is clicked and session data is cleared
    session_data_restored = Signal(str, list)  # compound_name, sample_names

    def __init__(self, parent=None):
        super().__init__("Selected Plots: All", parent)
        self.setObjectName("integrationWindow")

        # Track current state for apply button management
        self._current_compound: str = ""
        self._selected_samples: List[str] = []
        self._all_samples: List[str] = []

        self._build_ui()
        self._setup_apply_button_state()

        # Load and apply the stylesheet
        stylesheet = load_stylesheet("src/manic/resources/integration_window.qss")
        self.setStyleSheet(stylesheet)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        for label_text, obj_name in [
            ("Left Offset", "lo_input"),
            ("tR", "tr_input"),
            ("Right Offset", "ro_input"),
            ("tR Window", "tr_window_input"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("QLabel { background-color: #F0F0F0; }")
            edt = QLineEdit()
            edt.setObjectName(obj_name)
            row.addWidget(lbl)
            row.addWidget(edt, 1)
            layout.addLayout(row)

        # Create button row layout
        button_row = QHBoxLayout()

        self.apply_button = QPushButton("Apply")
        self.apply_button.setObjectName("ApplyButton")
        self.apply_button.clicked.connect(self._on_apply_clicked)
        button_row.addWidget(self.apply_button)

        self.restore_button = QPushButton("Reset")
        self.restore_button.setObjectName("RestoreButton")
        self.restore_button.clicked.connect(self._on_restore_clicked)
        button_row.addWidget(self.restore_button)

        layout.addLayout(button_row)

    def populate_fields(self, compound_dict):
        """Populate the line edit fields with compound data"""
        if compound_dict is None:
            # Clear all fields
            self._clear_fields()
            return

        # Map compound data to UI fields
        field_mappings = {
            "lo_input": compound_dict.get("loffset", ""),
            "tr_input": compound_dict.get("retention_time", ""),
            "ro_input": compound_dict.get("roffset", ""),
            "tr_window_input": compound_dict.get("tr_window", ""),
        }

        for obj_name, value in field_mappings.items():
            line_edit = self.findChild(QLineEdit, obj_name)
            if line_edit:
                line_edit.setText(str(value) if value is not None else "")

    def _clear_fields(self):
        """Clear all line edit fields"""
        for obj_name in ["lo_input", "tr_input", "ro_input", "tr_window_input"]:
            line_edit = self.findChild(QLineEdit, obj_name)
            if line_edit:
                line_edit.clear()

    def populate_fields_from_plots(
        self, compound_name: str, selected_samples: list, all_samples: list = None
    ):
        """Populate fields based on plot selection state

        Args:
            compound_name: Name of the current compound
            selected_samples: List of currently selected sample names
            all_samples: List of all visible sample names (for fallback when no selection)
        """
        # Validate inputs
        if not compound_name:
            self._clear_fields()
            self._update_apply_button_state()
            return

        # Update internal state for apply button management
        self._current_compound = compound_name
        self._selected_samples = selected_samples.copy() if selected_samples else []
        self._all_samples = all_samples.copy() if all_samples else []

        try:
            # Case 1: No plots selected - show range for all visible plots
            if not selected_samples and all_samples:
                self._populate_range_fields(compound_name, all_samples)
                self.setTitle("Selected Plots: All")
                self._update_apply_button_state()
                return

            # Case 2: No plots selected and no samples provided - use compound defaults
            if not selected_samples:
                compound_data = read_compound(compound_name)
                compound_dict = {
                    "loffset": compound_data.loffset,
                    "retention_time": compound_data.retention_time,
                    "roffset": compound_data.roffset,
                    "tr_window": getattr(compound_data, "tr_window", 0.2),
                }
                self.populate_fields(compound_dict)
                self.setTitle("Selected Plots: All")
                self._update_apply_button_state()
                return

            # Case 3: Single plot selected - show specific values (with session data if available)
            if len(selected_samples) == 1:
                sample_name = selected_samples[0]
                compound_data = read_compound_with_session(compound_name, sample_name)
                compound_dict = {
                    "loffset": compound_data.loffset,
                    "retention_time": compound_data.retention_time,
                    "roffset": compound_data.roffset,
                    "tr_window": getattr(compound_data, "tr_window", 0.2),
                }
                self.populate_fields(compound_dict)
                self.setTitle("Selected Plots: 1 sample")
                self._update_apply_button_state()
                return

            # Case 4: Multiple plots selected - show ranges
            self._populate_range_fields(compound_name, selected_samples)
            self.setTitle(f"Selected Plots: {len(selected_samples)} samples")
            self._update_apply_button_state()

        except Exception as e:
            print(f"Error populating integration window fields: {e}")
            self._clear_fields()
            self._update_apply_button_state()

    def _populate_range_fields(self, compound_name: str, sample_names: list):
        """Populate fields with ranges for multiple samples"""
        try:
            # Get EIC data for all specified samples
            eics = get_eics_for_compound(compound_name, sample_names)

            if not eics:
                self._clear_fields()
                return

            # Get compound data for each sample (including session overrides)
            rt_times = []
            loffsets = []
            roffsets = []
            tr_windows = []

            for sample_name in sample_names:
                compound_data = read_compound_with_session(compound_name, sample_name)
                rt_times.append(compound_data.retention_time)
                loffsets.append(compound_data.loffset)
                roffsets.append(compound_data.roffset)
                tr_windows.append(getattr(compound_data, "tr_window", 0.2))

            # Format ranges or single values
            field_values = {
                "lo_input": self._format_range(loffsets),
                "tr_input": self._format_range(rt_times),
                "ro_input": self._format_range(roffsets),
                "tr_window_input": self._format_range(tr_windows),
            }

            # Populate fields
            for obj_name, value in field_values.items():
                line_edit = self.findChild(QLineEdit, obj_name)
                if line_edit:
                    line_edit.setText(str(value))

        except Exception as e:
            print(f"Error calculating ranges: {e}")
            self._clear_fields()

    def _format_range(self, values: list) -> str:
        """Format a list of values as a range string or single value"""
        if not values:
            return ""

        # Remove None values and convert to float
        clean_values = []
        for v in values:
            if v is not None:
                try:
                    clean_values.append(float(v))
                except (ValueError, TypeError):
                    continue

        if not clean_values:
            return ""

        min_val = min(clean_values)
        max_val = max(clean_values)

        # If all values are the same (or very close), show single value
        if abs(max_val - min_val) < 1e-6:
            return f"{min_val:.4f}".rstrip("0").rstrip(".")
        else:
            # Show range
            min_str = f"{min_val:.4f}".rstrip("0").rstrip(".")
            max_str = f"{max_val:.4f}".rstrip("0").rstrip(".")
            return f"{min_str} - {max_str}"

    def _setup_apply_button_state(self):
        """Setup initial apply button state and styling"""
        self._update_apply_button_state()

    def _update_apply_button_state(self):
        """Update button states and tooltips based on selection"""
        # Both buttons are always enabled, styling handled by QSS
        self.apply_button.setEnabled(True)
        self.restore_button.setEnabled(True)

        # Update tooltips based on selection state
        if not self._selected_samples:
            apply_tooltip = "Apply changes to all plots"
            restore_tooltip = "Restore all plots to defaults"
        else:
            sample_count = len(self._selected_samples)
            if sample_count == 1:
                apply_tooltip = f"Apply changes to {self._selected_samples[0]}"
                restore_tooltip = f"Restore {self._selected_samples[0]} to defaults"
            else:
                apply_tooltip = f"Apply changes to {sample_count} selected samples"
                restore_tooltip = f"Restore {sample_count} selected samples to defaults"

        self.apply_button.setToolTip(apply_tooltip)
        self.restore_button.setToolTip(restore_tooltip)

    def _on_apply_clicked(self):
        """Handle apply button click - validate inputs and update session data"""
        if not self._current_compound:
            QMessageBox.warning(self, "No Compound", "No compound selected.")
            return

        # Determine which samples to apply to
        samples_to_apply = (
            self._selected_samples if self._selected_samples else self._all_samples
        )

        if not samples_to_apply:
            QMessageBox.warning(
                self, "No Samples", "No samples available to apply changes to."
            )
            return

        try:
            # Get and validate input values
            input_values = self._get_validated_inputs()
            if input_values is None:
                return  # Validation failed, error already shown

            retention_time, loffset, roffset = input_values

            # Update session activity data for the target samples
            SessionActivityService.update_session_data(
                compound_name=self._current_compound,
                sample_names=samples_to_apply,
                retention_time=retention_time,
                loffset=loffset,
                roffset=roffset,
            )

            # Emit signal to trigger plot refresh
            self.session_data_applied.emit(self._current_compound, samples_to_apply)

        except Exception as e:
            QMessageBox.critical(
                self, "Apply Failed", f"Failed to apply changes: {str(e)}"
            )

    def _on_restore_clicked(self):
        """Handle restore button click - clear session data and restore to defaults"""
        if not self._current_compound:
            QMessageBox.warning(self, "No Compound", "No compound selected.")
            return

        # Determine which samples to restore
        samples_to_restore = (
            self._selected_samples if self._selected_samples else self._all_samples
        )

        if not samples_to_restore:
            QMessageBox.warning(self, "No Samples", "No samples available to restore.")
            return

        # Confirm restore action
        sample_count = len(samples_to_restore)
        if self._selected_samples:
            if sample_count == 1:
                message = f"Restore {samples_to_restore[0]} to default values?"
            else:
                message = f"Restore {sample_count} selected samples to default values?"
        else:
            message = f"Restore all {sample_count} samples to default values?"

        reply = QMessageBox.question(
            self,
            "Confirm Restore",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Remove session data to restore defaults
                SessionActivityService.restore_samples_to_defaults(
                    compound_name=self._current_compound,
                    sample_names=samples_to_restore,
                )

                # Emit signal to trigger plot refresh
                self.session_data_restored.emit(
                    self._current_compound, samples_to_restore
                )

            except Exception as e:
                QMessageBox.critical(
                    self, "Restore Failed", f"Failed to restore to defaults: {str(e)}"
                )

    def _get_validated_inputs(self) -> Optional[tuple[float, float, float]]:
        """
        Get and validate input field values.

        Returns:
            Tuple of (retention_time, loffset, roffset) if validation passes, None otherwise
        """
        try:
            # Get field values
            lo_field = self.findChild(QLineEdit, "lo_input")
            ro_field = self.findChild(QLineEdit, "ro_input")
            tr_field = self.findChild(QLineEdit, "tr_input")

            if not all([lo_field, ro_field, tr_field]):
                raise ValueError("Could not find required input fields")

            # Parse and validate retention time
            try:
                retention_time_text = tr_field.text().strip()
                if not retention_time_text:
                    raise ValueError("Retention time cannot be empty")
                # Handle range format (e.g., "7.4 - 7.5") by taking first value
                if " - " in retention_time_text:
                    retention_time_text = retention_time_text.split(" - ")[0]
                retention_time = float(retention_time_text)
            except ValueError:
                QMessageBox.warning(
                    self, "Invalid Input", "Retention time must be a valid number"
                )
                tr_field.setFocus()
                return None

            # Parse and validate left offset
            try:
                loffset_text = lo_field.text().strip()
                if not loffset_text:
                    raise ValueError("Left offset cannot be empty")
                # Handle range format (e.g., "1.2 - 1.5") by taking first value
                if " - " in loffset_text:
                    loffset_text = loffset_text.split(" - ")[0]
                loffset = float(loffset_text)
            except ValueError:
                QMessageBox.warning(
                    self, "Invalid Input", "Left offset must be a valid number"
                )
                lo_field.setFocus()
                return None

            # Parse and validate right offset
            try:
                roffset_text = ro_field.text().strip()
                if not roffset_text:
                    raise ValueError("Right offset cannot be empty")
                # Handle range format
                if " - " in roffset_text:
                    roffset_text = roffset_text.split(" - ")[0]
                roffset = float(roffset_text)
            except ValueError:
                QMessageBox.warning(
                    self, "Invalid Input", "Right offset must be a valid number"
                )
                ro_field.setFocus()
                return None

            # Basic validation
            if retention_time <= 0:
                QMessageBox.warning(
                    self, "Invalid Input", "Retention time must be positive"
                )
                tr_field.setFocus()
                return None

            if loffset < 0:
                QMessageBox.warning(
                    self, "Invalid Input", "Left offset cannot be negative"
                )
                lo_field.setFocus()
                return None

            if roffset < 0:
                QMessageBox.warning(
                    self, "Invalid Input", "Right offset cannot be negative"
                )
                ro_field.setFocus()
                return None

            return retention_time, loffset, roffset

        except Exception as e:
            QMessageBox.critical(
                self, "Validation Error", f"Error validating inputs: {str(e)}"
            )
            return None
