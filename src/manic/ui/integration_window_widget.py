from __future__ import annotations

from typing import Dict, List, Optional, Tuple

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
from manic.utils.paths import resource_path
from manic.utils.utils import load_stylesheet


# ─────────────────────── RT Window Boundary Checking Functions ───────────────────────
# These pure functions handle the logic for determining when EIC data needs to be reloaded
# due to integration boundaries falling outside the currently stored data window.


def _parse_rt_text(rt_text: str) -> tuple[str, float, Optional[tuple[float, float]]]:
    """Parse an RT input field value.

    Returns:
        (mode, rt_value, rt_range)

    Where:
        - mode is "single" or "range"
        - rt_value is the representative RT (single value, or min_rt for a range)
        - rt_range is (min_rt, max_rt) when mode == "range", else None

    Raises:
        ValueError if the format is invalid.
    """
    """Parse an RT input field value.

    Returns:
        ("single", rt_float) OR ("range", (min_rt, max_rt))

    Raises:
        ValueError if the format is invalid.
    """
    import re

    text = (rt_text or "").strip()
    if not text:
        raise ValueError("Retention time cannot be empty")

    # Robust range parsing: allow whitespace variations around '-'
    m = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*-\s*([0-9]*\.?[0-9]+)\s*$", text)
    if m:
        min_rt = float(m.group(1))
        max_rt = float(m.group(2))
        if min_rt <= 0 or max_rt <= 0 or min_rt > max_rt:
            raise ValueError("Invalid retention time range")
        return "range", min_rt, (min_rt, max_rt)

    rt = float(text)
    if rt <= 0:
        raise ValueError("Retention time must be positive")
    return "single", rt, None


def calculate_integration_boundaries(
    rt: float, loffset: float, roffset: float
) -> tuple[float, float]:

    """
    Calculate left and right integration boundaries from retention time and offsets.

    Integration boundaries define the time range where peak area integration occurs.
    These boundaries must fit within the stored EIC data window.

    Args:
        rt: Retention time (minutes)
        loffset: Left offset from retention time (minutes)
        roffset: Right offset from retention time (minutes)

    Returns:
        Tuple of (left_boundary, right_boundary) in minutes

    Example:
        >>> calculate_integration_boundaries(10.0, 0.5, 0.5)
        (9.5, 10.5)
    """
    return rt - loffset, rt + roffset


def calculate_minimum_rt_window(
    loffset: float, roffset: float, buffer: float = 0.1
) -> float:
    """
    Calculate minimum RT window size required to cover integration boundaries.

    The RT window must be large enough to contain both left and right integration
    boundaries. A safety buffer is added to prevent boundary conditions.

    Args:
        loffset: Left offset from retention time (minutes)
        roffset: Right offset from retention time (minutes)
        buffer: Safety buffer to add beyond max offset (minutes, default: 0.1)

    Returns:
        Minimum RT window size (minutes)

    Example:
        >>> calculate_minimum_rt_window(0.3, 0.5, buffer=0.1)
        0.6  # max(0.3, 0.5) + 0.1
    """
    return max(loffset, roffset) + buffer


def check_boundaries_within_window(
    left_boundary: float,
    right_boundary: float,
    window_min: float,
    window_max: float,
    tolerance: float = 0.001,
) -> bool:
    """
    Check if integration boundaries fit within the stored data window.

    Determines whether the current EIC data window contains the integration boundaries.
    If boundaries exceed the window, EIC data must be reloaded with a new RT center.

    Args:
        left_boundary: Left integration boundary (minutes)
        right_boundary: Right integration boundary (minutes)
        window_min: Minimum time in stored EIC data (minutes)
        window_max: Maximum time in stored EIC data (minutes)
        tolerance: Tolerance for floating point comparison (minutes, default: 0.001)

    Returns:
        True if boundaries fit within window (no reload needed), False otherwise

    Example:
        >>> check_boundaries_within_window(9.5, 10.5, 9.0, 11.0)
        True  # Boundaries fit comfortably within window
        >>> check_boundaries_within_window(8.5, 10.5, 9.0, 11.0)
        False  # Left boundary exceeds window minimum
    """
    return (left_boundary >= window_min - tolerance and
            right_boundary <= window_max + tolerance)


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

    # Signal emitted when regenerate button is clicked (for future implementation)
    data_regeneration_requested = Signal(
        str, float, list, float
    )  # compound_name, tr_window, sample_names, retention_time



    def __init__(self, parent=None):
        super().__init__("Selected Plots: All", parent)
        self.setObjectName("integrationWindow")

        # Track current state for apply button management
        self._current_compound: str = ""
        self._selected_samples: List[str] = []
        self._all_samples: List[str] = []

        # Track data window bounds for reload detection (per-sample)
        # Maps (compound_name, sample_name) to (min_time, max_time) of stored EIC data
        self._data_window_bounds: Dict[Tuple[str, str], Tuple[float, float]] = {}

        # Store pending session update when reload is triggered
        # Tuple of (retention_time_or_None, loffset, roffset, samples_to_apply)
        # If retention_time is None, retain each sample's existing RT (offset-only apply).
        self._pending_session_update: Optional[
            Tuple[Optional[float], float, float, List[str]]
        ] = None
        
        # Track which samples were actually regenerated (for bounds refresh)
        self._samples_regenerated: List[str] = []

        self._build_ui()
        self._setup_apply_button_state()

        # Load and apply the stylesheet
        stylesheet = load_stylesheet(
            resource_path("resources", "integration_window.qss")
        )
        # Replace placeholder with actual checkmark path for the checkbox indicator
        checkmark_path = resource_path("resources", "checkmark.svg").replace("\\", "/")
        stylesheet = stylesheet.replace("CHECKMARK_PATH", checkmark_path)
        self.setStyleSheet(stylesheet)

        font = self.font()
        font.setBold(True)
        self.setFont(font)

    def _get_main_window(self):
        """Get the main window instance to use its message box helper."""
        widget = self
        while widget.parent():
            widget = widget.parent()
            # Check if this widget has the _create_message_box method (i.e., it's the MainWindow)
            if hasattr(widget, "_create_message_box"):
                return widget
        return None

    def _show_message(
        self, msg_type: str, title: str, text: str, informative_text: str = ""
    ):
        """Show a message using the main window's styled message box helper."""
        main_window = self._get_main_window()
        if main_window and hasattr(main_window, "_create_message_box"):
            create_box = getattr(main_window, "_create_message_box")
            msg_box = create_box(msg_type, title, text, informative_text, self)
            return msg_box.exec()
        else:
            # Fallback to standard message box if main window not found
            if msg_type == "question":
                return QMessageBox.question(self, title, text)
            else:
                getattr(QMessageBox, msg_type)(self, title, text)
                return None

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Integration parameter fields
        for label_text, obj_name in [
            ("Left Offset", "lo_input"),
            ("tR", "tr_input"),
            ("Right Offset", "ro_input"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("QLabel { background-color: white; border: none; }")
            edt = QLineEdit()
            edt.setObjectName(obj_name)
            # Enable Enter key to trigger apply (same as clicking Apply button)
            edt.returnPressed.connect(self._on_apply_clicked)
            row.addWidget(lbl)
            row.addWidget(edt, 1)
            layout.addLayout(row)

        # Action buttons
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

        # tR Window field for data regeneration
        tr_window_row = QHBoxLayout()
        tr_window_lbl = QLabel("tR Window")
        tr_window_lbl.setStyleSheet("QLabel { background-color: white; border: none; }")
        self.tr_window_edit = QLineEdit()
        self.tr_window_edit.setObjectName("tr_window_input")
        # Enable Enter key to trigger regeneration (same as clicking Update tR Window button)
        self.tr_window_edit.returnPressed.connect(self._on_regenerate_clicked)
        tr_window_row.addWidget(tr_window_lbl)
        tr_window_row.addWidget(self.tr_window_edit, 1)
        layout.addLayout(tr_window_row)

        # Regeneration button
        regen_button_row = QHBoxLayout()
        self.regenerate_button = QPushButton("Update tR Window")
        self.regenerate_button.setObjectName("RegenerateButton")
        self.regenerate_button.clicked.connect(self._on_regenerate_clicked)
        regen_button_row.addWidget(self.regenerate_button)

        layout.addLayout(regen_button_row)

    def _format_number(self, value: float, sig_figs: int = 4) -> str:
        """
        Format number to specified significant figures.

        Args:
            value: Number to format
            sig_figs: Number of significant figures (default: 4)

        Returns:
            Formatted string with specified significant figures
        """
        if value == 0:
            return "0"
        return f"{value:.{sig_figs}g}"

    def populate_tr_window_field(self, compound_name: str):
        """Populate only the tR window field - called only when compound changes

        Reads the actual RT window from the EIC data (persisted value), falling back
        to compound defaults if no EIC data exists yet.
        """
        try:
            # Try to get RT window from actual EIC data (persisted value)
            from manic.models.database import get_connection

            tr_window_value = None
            with get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT rt_window FROM eic
                    WHERE compound_name = ? AND deleted = 0
                    LIMIT 1
                    """,
                    (compound_name,)
                ).fetchone()

                if row and row["rt_window"] is not None:
                    tr_window_value = row["rt_window"]

            # Fall back to compound default if no EIC data exists
            if tr_window_value is None:
                compound_data = read_compound(compound_name)
                tr_window_value = getattr(compound_data, "tr_window", 0.2)

            tr_window_field = self.findChild(QLineEdit, "tr_window_input")
            if tr_window_field:
                tr_window_field.setText(self._format_number(tr_window_value))


        except Exception as e:
            print(f"Error populating tR window field: {e}")

    def populate_fields(self, compound_dict):
        """Populate the line edit fields with compound data"""
        if compound_dict is None:
            self._clear_fields()
            return

        # Map compound data to UI fields (excluding tR window - only updated on compound change)
        field_mappings = {
            "lo_input": compound_dict.get("loffset", ""),
            "tr_input": compound_dict.get("retention_time", ""),
            "ro_input": compound_dict.get("roffset", ""),
        }

        for obj_name, value in field_mappings.items():
            line_edit = self.findChild(QLineEdit, obj_name)
            if line_edit:
                if value is not None and value != "":
                    line_edit.setText(self._format_number(value))
                else:
                    line_edit.setText("")

    def _clear_fields(self):
        """Clear all line edit fields"""
        for obj_name in ["lo_input", "tr_input", "ro_input", "tr_window_input"]:
            line_edit = self.findChild(QLineEdit, obj_name)
            if line_edit:
                line_edit.clear()

    def populate_fields_from_plots(
        self, compound_name: str, selected_samples: list, all_samples: Optional[list] = None
    ):
        """Populate fields based on plot selection state

        Args:
            compound_name: Name of the current compound
            selected_samples: List of currently selected sample names
            all_samples: List of all visible sample names (for fallback when no selection)
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"populate_fields_from_plots: compound={compound_name}, selected={len(selected_samples) if selected_samples else 0}, all={len(all_samples) if all_samples else 0}")
        
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

                # Get EIC data to capture data window bounds (per-sample)
                try:
                    eics = get_eics_for_compound(compound_name, [sample_name])
                    if eics and len(eics) > 0 and len(eics[0].time) > 0:
                        time_data = eics[0].time
                        key = (compound_name, sample_name)
                        self._data_window_bounds[key] = (time_data.min(), time_data.max())
                except Exception:
                    pass  # Bounds capture is best-effort

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
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error populating integration window fields: {e}")
            self._clear_fields()
            self._update_apply_button_state()

    def _populate_range_fields(self, compound_name: str, sample_names: list):
        """Populate fields with ranges for multiple samples"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Get EIC data for all specified samples
            eics = get_eics_for_compound(compound_name, sample_names)

            if not eics:
                logger.warning(f"No EIC data found for compound {compound_name}")
                self._clear_fields()
                return

            # Store data window bounds for all samples
            for idx, sample_name in enumerate(sample_names):
                if idx < len(eics) and len(eics[idx].time) > 0:
                    time_data = eics[idx].time
                    key = (compound_name, sample_name)
                    self._data_window_bounds[key] = (time_data.min(), time_data.max())

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

            # Format ranges or single values (excluding tR window - only updated on compound change)
            field_values = {
                "lo_input": self._format_range(loffsets),
                "tr_input": self._format_range(rt_times),
                "ro_input": self._format_range(roffsets),
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
            return self._format_number(min_val)
        else:
            # Show range with consistent formatting
            min_str = self._format_number(min_val)
            max_str = self._format_number(max_val)
            return f"{min_str} - {max_str}"

    def _get_current_retention_time(self) -> float:
        """
        Get current retention time for the compound.
        
        Checks for session override first, then falls back to compound default.
        Uses the first selected sample if available, otherwise uses compound default.
        
        Returns:
            Retention time in minutes
        """
        from manic.models.database import get_connection
        
        with get_connection() as conn:
            # Try session override first if we have selected samples
            if self._selected_samples:
                row = conn.execute(
                    """
                    SELECT retention_time FROM session_activity
                    WHERE compound_name = ? AND sample_name = ? AND sample_deleted = 0
                    LIMIT 1
                    """,
                    (self._current_compound, self._selected_samples[0]),
                ).fetchone()
                if row and row["retention_time"] is not None:
                    return row["retention_time"]
            
            # Fall back to compound default
            row = conn.execute(
                """
                SELECT retention_time FROM compounds
                WHERE compound_name = ? AND deleted = 0
                """,
                (self._current_compound,),
            ).fetchone()
            
            return row["retention_time"] if row and row["retention_time"] else 0.0

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

        # Set tooltip for regenerate button
        regenerate_tooltip = "Update tR window and recalculate EIC data"
        self.regenerate_button.setToolTip(regenerate_tooltip)

    def _get_samples_needing_reload(
        self,
        new_rt: float,
        new_loffset: float,
        new_roffset: float,
        samples_to_check: List[str]
    ) -> List[str]:
        """
        Determine which samples need EIC data reload based on integration boundaries.
        
        For each sample, checks if the new integration boundaries (RT ± offsets) 
        fall outside that sample's stored data window. Only samples whose boundaries 
        exceed their window need to be regenerated.
        
        Args:
            new_rt: New retention time (minutes)
            new_loffset: New left offset (minutes)
            new_roffset: New right offset (minutes)
            samples_to_check: List of sample names to check
            
        Returns:
            List of sample names that need reload (empty if none need reload)
        """
        import logging
        logger = logging.getLogger(__name__)
        
        samples_needing_reload = []
        
        # Calculate new integration boundaries using tested helper function
        left_boundary, right_boundary = calculate_integration_boundaries(
            new_rt, new_loffset, new_roffset
        )
        
        # Check each sample independently
        for sample_name in samples_to_check:
            key = (self._current_compound, sample_name)
            
            # If no bounds info, reload to be safe
            if key not in self._data_window_bounds:
                logger.debug(f"No bounds info for {sample_name} - marking for reload")
                samples_needing_reload.append(sample_name)
                continue
            
            window_min, window_max = self._data_window_bounds[key]
            
            # Check if boundaries fit within this sample's window using tested helper
            boundaries_fit = check_boundaries_within_window(
                left_boundary, right_boundary, window_min, window_max
            )
            
            if not boundaries_fit:
                logger.debug(
                    f"Sample {sample_name}: boundaries [{left_boundary:.3f}, {right_boundary:.3f}] "
                    f"exceed window [{window_min:.3f}, {window_max:.3f}] - marking for reload"
                )
                samples_needing_reload.append(sample_name)
        
        return samples_needing_reload

    def _get_samples_needing_reload_with_sample_rts(
        self,
        sample_rts: Dict[str, float],
        new_loffset: float,
        new_roffset: float,
        samples_to_check: List[str],
    ) -> List[str]:
        """Like _get_samples_needing_reload, but uses per-sample RTs.

        This supports "offset-only" applies when the UI shows a tR range.
        """
        import logging

        logger = logging.getLogger(__name__)

        samples_needing_reload: List[str] = []

        for sample_name in samples_to_check:
            if sample_name not in sample_rts:
                samples_needing_reload.append(sample_name)
                continue

            new_rt = sample_rts[sample_name]
            left_boundary, right_boundary = calculate_integration_boundaries(
                new_rt, new_loffset, new_roffset
            )

            key = (self._current_compound, sample_name)
            if key not in self._data_window_bounds:
                logger.debug(f"No bounds info for {sample_name} - marking for reload")
                samples_needing_reload.append(sample_name)
                continue

            window_min, window_max = self._data_window_bounds[key]
            boundaries_fit = check_boundaries_within_window(
                left_boundary, right_boundary, window_min, window_max
            )
            if not boundaries_fit:
                samples_needing_reload.append(sample_name)

        return samples_needing_reload

    def refresh_data_window_bounds(self, compound_name: str, sample_names: List[str]):
        """
        Refresh stored data window bounds after EIC reload.

        This should be called after EIC data is regenerated to update the stored
        time window bounds used for boundary checking.

        Args:
            compound_name: Name of the compound to refresh bounds for
            sample_names: List of sample names to refresh bounds for
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Refresh bounds for each regenerated sample
            for sample_name in sample_names:
                eics = get_eics_for_compound(compound_name, [sample_name], use_corrected=False)
                if eics and len(eics) > 0 and len(eics[0].time) > 0:
                    time_data = eics[0].time
                    key = (compound_name, sample_name)
                    self._data_window_bounds[key] = (time_data.min(), time_data.max())
                    logger.debug(
                        f"Refreshed bounds for {sample_name}: "
                        f"[{time_data.min():.3f}, {time_data.max():.3f}]"
                    )
        except Exception as e:
            logger.warning(f"Failed to refresh data window bounds: {e}")

    def _on_apply_clicked(self):
        """Handle apply button click - validate inputs and update session data"""
        if not self._current_compound:
            self._show_message("warning", "No Compound", "No compound selected.")
            return

        # Determine which samples to apply to
        samples_to_apply = (
            self._selected_samples if self._selected_samples else self._all_samples
        )

        if not samples_to_apply:
            self._show_message(
                "warning", "No Samples", "No samples available to apply changes to."
            )
            return

        try:
            # Get and validate input values
            input_values = self._get_validated_inputs()
            if input_values is None:
                return  # Validation failed, error already shown

            retention_time, loffset, roffset = input_values

            tr_field = self.findChild(QLineEdit, "tr_input")
            tr_text = tr_field.text().strip() if tr_field else ""

            # If we're applying to multiple samples and the tR field is a range ("min - max"),
            # treat this as an offset-only update. Preserve each sample's current retention time
            # so we don't clobber per-sample session overrides.
            try:
                rt_mode, _rt_value, _rt_range = _parse_rt_text(tr_text)
            except ValueError:
                rt_mode = "single"

            preserve_sample_rts = (len(samples_to_apply) > 1 and rt_mode == "range")

            # Determine which samples need reload (check each sample independently)
            # In offset-only mode, use each sample's existing RT for boundary checks.
            if preserve_sample_rts:
                sample_rts = {
                    sample_name: read_compound_with_session(
                        self._current_compound, sample_name
                    ).retention_time
                    for sample_name in samples_to_apply
                }
                samples_needing_reload = self._get_samples_needing_reload_with_sample_rts(
                    sample_rts, loffset, roffset, samples_to_apply
                )
            else:
                samples_needing_reload = self._get_samples_needing_reload(
                    retention_time, loffset, roffset, samples_to_apply
                )

            if samples_needing_reload:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(
                    f"Checking {len(samples_to_apply)} samples: "
                    f"{len(samples_needing_reload)} need reload"
                )
                
                # Get current RT window value
                tr_window_field = self.findChild(QLineEdit, "tr_window_input")
                current_tr_window = (
                    float(tr_window_field.text()) if tr_window_field and tr_window_field.text() else 0.2
                )

                # Calculate required RT window (ensure it covers integration boundaries)
                # Use tested helper function with configurable buffer constant
                from manic.constants import DEFAULT_RT_WINDOW_BUFFER
                min_required_window = calculate_minimum_rt_window(
                    loffset, roffset, buffer=DEFAULT_RT_WINDOW_BUFFER
                )
                actual_window = max(current_tr_window, min_required_window)

                logger.info(
                    f"Regenerating {len(samples_needing_reload)} samples with RT window {actual_window:.3f} min"
                )

                # Store pending session update to be applied after reload completes
                # Apply to ALL originally selected samples, not just those needing reload
                # If we're preserving per-sample RTs, store only offsets for later apply.
                # We can't persist per-sample RTs in this tuple, so we recompute them after reload.
                pending_rt = None if preserve_sample_rts else retention_time
                self._pending_session_update = (pending_rt, loffset, roffset, samples_to_apply)
                
                # Track which samples are being regenerated (for bounds refresh)
                self._samples_regenerated = samples_needing_reload.copy()

                # Emit signal to trigger EIC data regeneration for ONLY affected samples
                # Pass the new retention time so EIC is centered at the correct position
                self.data_regeneration_requested.emit(
                    self._current_compound, actual_window, samples_needing_reload, retention_time
                )

                # Note: Session data will be updated in _regeneration_completed handler
                return

            # No reload needed - update session activity data immediately
            if preserve_sample_rts:
                SessionActivityService.update_offsets_preserve_rt(
                    compound_name=self._current_compound,
                    sample_names=samples_to_apply,
                    loffset=loffset,
                    roffset=roffset,
                )
            else:
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
            self._show_message(
                "critical", "Apply Failed", f"Failed to apply changes: {str(e)}"
            )

    def _on_restore_clicked(self):
        """Handle restore button click - clear session data and restore to defaults"""
        if not self._current_compound:
            self._show_message("warning", "No Compound", "No compound selected.")
            return

        # Determine which samples to restore
        samples_to_restore = (
            self._selected_samples if self._selected_samples else self._all_samples
        )

        if not samples_to_restore:
            self._show_message(
                "warning", "No Samples", "No samples available to restore."
            )
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

        reply = self._show_message("question", "Confirm Restore", message)

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
                self._show_message(
                    "critical",
                    "Restore Failed",
                    f"Failed to restore to defaults: {str(e)}",
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

            if lo_field is None or ro_field is None or tr_field is None:
                raise ValueError("Could not find required input fields")

            # Parse and validate retention time
            try:
                rt_mode, retention_time, _rt_range = _parse_rt_text(tr_field.text())
            except ValueError:
                self._show_message(
                    "warning",
                    "Invalid Input",
                    "Retention time must be a single number or a range (e.g., '7.4 - 7.5')",
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
                self._show_message(
                    "warning", "Invalid Input", "Left offset must be a valid number"
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
                self._show_message(
                    "warning", "Invalid Input", "Right offset must be a valid number"
                )
                ro_field.setFocus()
                return None

            # Basic validation
            if retention_time <= 0:
                self._show_message(
                    "warning", "Invalid Input", "Retention time must be positive"
                )
                tr_field.setFocus()
                return None

            if loffset < 0:
                self._show_message(
                    "warning", "Invalid Input", "Left offset cannot be negative"
                )
                lo_field.setFocus()
                return None

            if roffset < 0:
                self._show_message(
                    "warning", "Invalid Input", "Right offset cannot be negative"
                )
                ro_field.setFocus()
                return None

            return retention_time, loffset, roffset

        except Exception as e:
            self._show_message(
                "critical", "Validation Error", f"Error validating inputs: {str(e)}"
            )
            return None

    def _on_regenerate_clicked(self):
        """Handle regenerate button click - validate tR window and trigger data regeneration"""
        if not self._current_compound:
            self._show_message("warning", "No Compound", "No compound selected.")
            return

        # Get and validate tR window input
        tr_window_field = self.findChild(QLineEdit, "tr_window_input")
        if not tr_window_field:
            self._show_message(
                "critical", "UI Error", "Could not find tR Window input field"
            )
            return

        try:
            tr_window_text = tr_window_field.text().strip()
            if not tr_window_text:
                self._show_message(
                    "warning", "Invalid Input", "tR Window cannot be empty"
                )
                tr_window_field.setFocus()
                return

            # Handle range format (take first value like other fields)
            if " - " in tr_window_text:
                tr_window_text = tr_window_text.split(" - ")[0]

            tr_window = float(tr_window_text)

            if tr_window <= 0:
                self._show_message(
                    "warning", "Invalid Input", "tR Window must be positive"
                )
                tr_window_field.setFocus()
                return

        except ValueError:
            self._show_message(
                "warning", "Invalid Input", "tR Window must be a valid number"
            )
            tr_window_field.setFocus()
            return

        # Get retention time from UI field (allows updating RT and window together)
        rt_field = self.findChild(QLineEdit, "retention_time_input")
        retention_time = None
        
        if rt_field:
            try:
                rt_text = rt_field.text().strip()
                if rt_text:
                    # Handle range format (take first value)
                    if " - " in rt_text:
                        rt_text = rt_text.split(" - ")[0]
                    retention_time = float(rt_text)
            except ValueError:
                pass  # Fall through to database query
        
        # Fall back to database if UI field unavailable or invalid
        if retention_time is None:
            retention_time = self._get_current_retention_time()

        # Check that samples are available
        samples_to_affect = self._all_samples if self._all_samples else []
        if not samples_to_affect:
            self._show_message(
                "warning", "No Samples", "No samples available for data regeneration."
            )
            return

        # Emit signal to trigger data regeneration
        try:
            self.data_regeneration_requested.emit(
                self._current_compound, tr_window, samples_to_affect, retention_time
            )
        except Exception as e:
            self._show_message(
                "critical",
                "Regeneration Failed",
                f"Failed to queue regeneration: {str(e)}",
            )
