from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QValidator
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from manic.constants import DEFAULT_RT_WINDOW_BUFFER, minimum_extract_rt_window
from manic.io.compound_reader import read_compound, read_compound_with_session
from manic.models.analysis import AnalysisMode
from manic.models.session_activity import PendingRegeneration, SessionActivityService
from manic.processors.eic_processing import get_eics_for_compound
from manic.ui.sidebar_widgets import CollapsibleSection
from manic.ui.theme import set_style_property

logger = logging.getLogger(__name__)

_TOOLBAR_DECIMAL_RE = re.compile(
    r"^\s*[+-]?\d*\.?\d{0,3}(?:\s*-\s*[+-]?\d*\.?\d{0,3})?\s*$"
)


def toolbar_decimal_text_is_allowed(text: str) -> bool:
    return _TOOLBAR_DECIMAL_RE.fullmatch(text or "") is not None


PEAK_FIELDS = ("lo_input", "tr_input", "ro_input")
# Non-breaking, so a wrapped caption never strands "·" or "not" at a line end.
NOT_APPLIED = "\u00a0·\u00a0not\u00a0applied"


def _field_value(text: str) -> str:
    """A field's text as a value, so "0.10" and "0.1" are the same edit."""
    text = " ".join(text.split())
    try:
        return repr(float(text))
    except ValueError:
        return text


def _differs(texts: Dict[str, str], other: Dict[str, str]) -> bool:
    return any(
        _field_value(texts.get(name, "")) != _field_value(other.get(name, ""))
        for name in PEAK_FIELDS
    )


class ToolbarDecimalValidator(QValidator):
    def validate(self, text, pos):
        if toolbar_decimal_text_is_allowed(text):
            return QValidator.State.Acceptable, text, pos
        return QValidator.State.Invalid, text, pos


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
    loffset: float, roffset: float, buffer: float = DEFAULT_RT_WINDOW_BUFFER
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
    return minimum_extract_rt_window(loffset, roffset, buffer)


def _widest_offset(text: str) -> float | None:
    parts = [part.strip() for part in (text or "").split(" - ") if part.strip()]
    if not parts:
        return None
    try:
        return max(float(part) for part in parts)
    except ValueError:
        return None


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


class IntegrationWindow(QWidget):
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
        str, float, list, object
    )  # compound_name, tr_window, sample_names, retention_time



    def __init__(
        self,
        analysis_mode: AnalysisMode | str = AnalysisMode.LABELLED,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("integrationWindow")
        self.analysis_mode = AnalysisMode.coerce(analysis_mode)

        # Track current state for apply button management
        self._current_compound: str = ""
        self._selected_samples: List[str] = []
        self._all_samples: List[str] = []

        # Track data window bounds for reload detection (per-sample)
        # Maps (compound_name, sample_name) to (min_time, max_time) of stored EIC data
        self._data_window_bounds: Dict[Tuple[str, str], Tuple[float, float]] = {}

        self._pending_session_update: PendingRegeneration | None = None
        # What the peak fields last loaded, and each target's unapplied edit until Apply or Reset.
        self._loaded: Dict[str, str] = {}
        self._drafts: Dict[Tuple[str, Tuple[str, ...]], Dict[str, str]] = {}
        # The tR window is per compound, whatever the selection, so its draft is too.
        self._window_compound = ""
        self._loaded_window = ""
        self._window_drafts: Dict[str, str] = {}

        self._build_ui()
        self._update_apply_button_state()

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
        if main_window:
            main_window._create_message_box(msg_type, title, text, informative_text, self).exec()
        else:
            getattr(QMessageBox, msg_type)(self, title, text)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # The offsets and the Reset/Apply that acts on them stay whole together;
        # on a short sidebar the rows below fold instead.
        self.editor = QWidget()
        editor_layout = QVBoxLayout(self.editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(8)

        self.scope_label = QLabel()
        self.scope_label.setObjectName("peakScope")
        self.scope_label.setProperty("role", "secondary")
        self.scope_label.setWordWrap(True)
        editor_layout.addWidget(self.scope_label)

        fields = QGridLayout()
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setHorizontalSpacing(12)
        fields.setVerticalSpacing(4)
        fields.setColumnStretch(1, 1)
        for row, (label_text, obj_name, tip) in enumerate(
            [
                ("Left offset", "lo_input", "Minutes before tR where integration starts"),
                ("tR", "tr_input", "Retention time in minutes"),
                ("Right offset", "ro_input", "Minutes after tR where integration ends"),
            ]
        ):
            lbl = QLabel(label_text)
            lbl.setToolTip(tip)
            edt = QLineEdit()
            edt.setObjectName(obj_name)
            edt.setToolTip(tip)
            edt.setValidator(ToolbarDecimalValidator(edt))
            # Enable Enter key to trigger apply (same as clicking Apply button)
            edt.returnPressed.connect(self._on_apply_clicked)
            edt.textEdited.connect(self._update_apply_button_state)
            fields.addWidget(lbl, row, 0)
            fields.addWidget(edt, row, 1)
        editor_layout.addLayout(fields)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        self.restore_button = QPushButton("Reset")
        self.restore_button.setObjectName("RestoreButton")
        self.restore_button.clicked.connect(self._on_restore_clicked)
        action_row.addWidget(self.restore_button, 1)

        self.apply_button = QPushButton("Apply")
        self.apply_button.setObjectName("ApplyButton")
        self.apply_button.clicked.connect(self._on_apply_clicked)
        apply_key = QKeySequence("Ctrl+Return")
        self._apply_key_text = apply_key.toString(QKeySequence.SequenceFormat.NativeText)
        for key in (apply_key, QKeySequence("Ctrl+Enter")):
            QShortcut(
                key, self, self.apply_button.click, Qt.ShortcutContext.WidgetWithChildrenShortcut
            )
        action_row.addWidget(self.apply_button, 2)
        editor_layout.addLayout(action_row)
        layout.addWidget(self.editor)

        # tR Window field for data regeneration
        tr_window_row = QHBoxLayout()
        tr_window_row.setSpacing(8)
        tr_window_lbl = QLabel("tR window")
        tr_window_lbl.setToolTip(
            "Width of the extracted chromatogram around tR, in minutes"
        )
        self.tr_window_edit = QLineEdit()
        self.tr_window_edit.setObjectName("tr_window_input")
        self.tr_window_edit.setToolTip(tr_window_lbl.toolTip())
        self.tr_window_edit.setValidator(ToolbarDecimalValidator(self.tr_window_edit))
        # Enable Enter key to trigger regeneration (same as clicking Apply window)
        self.tr_window_edit.returnPressed.connect(self._on_regenerate_clicked)
        self.tr_window_edit.textEdited.connect(self._update_apply_button_state)
        self.regenerate_button = QPushButton("Apply window")
        self.regenerate_button.setObjectName("RegenerateButton")
        self.regenerate_button.setToolTip("Ignores the plot selection")
        self.regenerate_button.clicked.connect(self._on_regenerate_clicked)
        tr_window_row.addWidget(tr_window_lbl)
        tr_window_row.addWidget(self.tr_window_edit, 1)
        tr_window_row.addWidget(self.regenerate_button)
        window_group = QWidget()
        window_layout = QVBoxLayout(window_group)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(4)
        window_layout.addLayout(tr_window_row)
        # Apply window ignores the selection, so it states its own scope.
        self.window_scope_label = QLabel()
        self.window_scope_label.setObjectName("windowScope")
        self.window_scope_label.setProperty("role", "hint")
        self.window_scope_label.setWordWrap(True)
        window_layout.addWidget(self.window_scope_label)
        rows = QWidget()
        rows_layout = QVBoxLayout(rows)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(4)
        rows_layout.addWidget(window_group)
        # Plain rows when they fit; on a short sidebar the toolbar folds them behind a
        # heading that names them, so the editor above stays whole.
        self.more = CollapsibleSection("Baseline, tR window", rows, sub=True)
        self.more.set_headless(True)
        self.more.toggled.connect(self.more.summary.setHidden)
        self.more.summary.setHidden(self.more.is_expanded())
        layout.addWidget(self.more)
        layout.addStretch(1)

    def _editor_height(self, width: int) -> int:
        height = self.editor.heightForWidth(width)
        return height if height >= 0 else self.editor.sizeHint().height()

    def editor_height(self) -> int:
        """The editor's height counting the scope line whether or not it shows,
        so a selection never moves what sits around the Peak window."""
        height = self._editor_height(self.width())
        if self.scope_label.isHidden():
            height += self.scope_label.fontMetrics().height() + self.editor.layout().spacing()
        return height

    def hasHeightForWidth(self) -> bool:
        # A parent asks a layout for height-for-width, which would count the rows below
        # at their last fitted height; the size hint counts every one.
        return False

    def lower_height(self, whole: bool) -> int:
        """Height of the rows below the editor: all of them as plain rows, or as they show
        now, folded behind their heading open or closed as the user left it."""
        rows = self.more.body.sizeHint().height()
        if whole or self.more.header.isHidden():
            return rows
        heading = self.more.header.minimumHeight()
        return heading + (self.more.layout().spacing() + rows if self.more.is_expanded() else 0)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        height = (
            self._editor_height(self.width()) + self.layout().spacing() + self.lower_height(True)
        )
        return QSize(hint.width(), height)

    def _format_number(self, value: float) -> str:
        if value == 0:
            return "0"
        return f"{float(value):.3f}".rstrip("0").rstrip(".") or "0"

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

            field = self.tr_window_edit
            if self._has_window_draft():
                self._window_drafts[self._window_compound] = field.text()
            else:
                self._window_drafts.pop(self._window_compound, None)
            field.setText(self._format_number(tr_window_value))
            self._window_compound = compound_name
            self._loaded_window = field.text()
            draft = self._window_drafts.pop(compound_name, None)
            if draft is not None and _field_value(draft) != _field_value(self._loaded_window):
                field.setText(draft)
            self._update_apply_button_state()
        except Exception as e:
            logger.exception("Error populating tR window field: %s", e)

    def populate_fields(self, compound_dict):
        """Populate the line edit fields with compound data"""
        if compound_dict is None:
            # A cleared session leaves no edit to come back to.
            self._clear_fields()
            self.tr_window_edit.clear()
            self._drafts.clear()
            self._window_drafts.clear()
            self._loaded = self._field_texts()
            self._loaded_window = ""
            self._update_apply_button_state()
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
        """Clear the peak fields; the tR window has its own loader and draft."""
        for obj_name in PEAK_FIELDS:
            self.findChild(QLineEdit, obj_name).clear()

    def _field_texts(self) -> Dict[str, str]:
        return {name: self.findChild(QLineEdit, name).text() for name in PEAK_FIELDS}

    def _draft_key(self) -> Tuple[str, Tuple[str, ...]]:
        return self._current_compound, tuple(self._selected_samples or self._all_samples)

    def _has_draft(self) -> bool:
        return bool(self._current_compound) and _differs(self._field_texts(), self._loaded)

    def _has_window_draft(self) -> bool:
        return bool(self._window_compound) and _field_value(
            self.tr_window_edit.text()
        ) != _field_value(self._loaded_window)

    def populate_fields_from_plots(
        self, compound_name: str, selected_samples: list, all_samples: Optional[list] = None
    ):
        """Show the stored peak window for the selection, or the shown samples without one.

        An unapplied edit is kept for its compound and target, and comes back with them."""
        if self._has_draft():
            self._drafts[self._draft_key()] = self._field_texts()
        else:
            self._drafts.pop(self._draft_key(), None)
        self._load_fields(compound_name, selected_samples, all_samples)
        self._loaded = self._field_texts()
        draft = self._drafts.get(self._draft_key())
        if draft is not None and _differs(draft, self._loaded):
            for name, text in draft.items():
                self.findChild(QLineEdit, name).setText(text)
        else:
            # Applied (the store now holds it) or never made.
            self._drafts.pop(self._draft_key(), None)
        self._update_apply_button_state()

    def _load_fields(
        self, compound_name: str, selected_samples: list, all_samples: Optional[list]
    ) -> None:
        if not compound_name:
            self._clear_fields()
            return

        # Update internal state for apply button management
        self._current_compound = compound_name
        self._selected_samples = selected_samples.copy() if selected_samples else []
        self._all_samples = all_samples.copy() if all_samples else []

        try:
            # Case 1: No plots selected - show range for all visible plots
            if not selected_samples and all_samples:
                self._populate_range_fields(compound_name, all_samples)
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
                return

            # Case 4: Multiple plots selected - show ranges
            self._populate_range_fields(compound_name, selected_samples)

        except Exception as e:
            logger.error(f"Error populating integration window fields: {e}")
            self._clear_fields()

    def _populate_range_fields(self, compound_name: str, sample_names: list):
        """Populate fields with ranges for multiple samples"""
        
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
            logger.exception("Error calculating ranges: %s", e)
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

    def _update_apply_button_state(self, *_args):
        """Name whom Apply and Reset change: a selection in the caption, all shown samples
        (the default) on hover. An unapplied edit says so. Apply window states its own."""
        selected = self._selected_samples
        targets = selected or self._all_samples
        for button in (self.apply_button, self.restore_button, self.regenerate_button):
            button.setEnabled(bool(targets))
        count = len(targets)
        edited = self._has_draft()
        if not self._current_compound:
            scope = "Select a compound to edit its peak window."
        elif selected:
            scope = (
                f"Applies to {selected[0]}"
                if count == 1
                else f"Applies to {count} selected samples"
            )
        else:
            scope = ""  # all shown samples, the default; the canvas explains an empty grid
        if edited:
            scope = f"{scope}{NOT_APPLIED}" if scope else "Not applied"
        self.scope_label.setText(scope)
        # Primary only while there is an edit to apply; still enabled to re-apply a mixed selection.
        set_style_property(self.apply_button, "variant", "primary" if edited else None)
        self.scope_label.setVisible(bool(scope))
        set_style_property(
            self.scope_label,
            "state",
            "edited" if edited else "selected" if selected else None,
        )
        if selected:
            self.apply_button.setToolTip(self._apply_key_text)
            self.restore_button.setToolTip("Restore the compound's default peak window")
        else:
            self.apply_button.setToolTip(f"Apply to all shown samples ({self._apply_key_text})")
            self.restore_button.setToolTip(
                "Restore all shown samples to the compound's default peak window"
            )
        shown = len(self._all_samples)
        window_edited = self._has_window_draft()
        self.window_scope_label.setText(
            f"Re-extracts all {shown} shown {'sample' if shown == 1 else 'samples'}"
            + (NOT_APPLIED if window_edited else "")
        )
        self.window_scope_label.setVisible(bool(self._current_compound and shown))
        set_style_property(self.window_scope_label, "state", "edited" if window_edited else None)

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
        
        try:
            for sample_name in sample_names:
                key = (compound_name, sample_name)
                try:
                    eics = get_eics_for_compound(
                        compound_name, [sample_name], use_corrected=False
                    )
                except LookupError:
                    self._data_window_bounds.pop(key, None)
                    continue
                if eics and len(eics[0].time) > 0:
                    time_data = eics[0].time
                    self._data_window_bounds[key] = (time_data.min(), time_data.max())
                    logger.debug(
                        f"Refreshed bounds for {sample_name}: "
                        f"[{time_data.min():.3f}, {time_data.max():.3f}]"
                    )
                else:
                    self._data_window_bounds.pop(key, None)
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
                logger.info(
                    f"Checking {len(samples_to_apply)} samples: "
                    f"{len(samples_needing_reload)} need reload"
                )
                
                # Get current RT window value
                tr_window_field = self.findChild(QLineEdit, "tr_window_input")
                current_tr_window = (
                    float(tr_window_field.text()) if tr_window_field and tr_window_field.text() else 0.2
                )

                min_required_window = calculate_minimum_rt_window(
                    loffset, roffset, buffer=DEFAULT_RT_WINDOW_BUFFER
                )
                actual_window = max(current_tr_window, min_required_window)

                logger.info(
                    f"Regenerating {len(samples_needing_reload)} samples with RT window {actual_window:.3f} min"
                )

                pending_rt = None if preserve_sample_rts else retention_time
                self._pending_session_update = PendingRegeneration(
                    compound_name=self._current_compound,
                    retention_time=pending_rt,
                    loffset=loffset,
                    roffset=roffset,
                    sample_names=tuple(samples_to_apply),
                    regenerated_sample_names=tuple(samples_needing_reload),
                )

                regeneration_rts = (
                    sample_rts if preserve_sample_rts else retention_time
                )
                self.data_regeneration_requested.emit(
                    self._current_compound,
                    actual_window,
                    samples_needing_reload,
                    regeneration_rts,
                )
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

        sample_count = len(samples_to_restore)
        if not self._selected_samples:
            target = f"all {sample_count} shown samples"
        elif sample_count == 1:
            target = samples_to_restore[0]
        else:
            target = f"{sample_count} selected samples"
        main_window = self._get_main_window()
        if main_window is not None and main_window._confirm(
            "Reset Peak Window",
            f"Reset {target} to the compound's default peak window?",
            "",
            "Reset Peak Window",
            self,
        ):
            # Reset discards the unapplied edit along with the stored one.
            self._drafts.pop(self._draft_key(), None)
            self._loaded = self._field_texts()
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

            lo_field = self.findChild(QLineEdit, "lo_input")
            ro_field = self.findChild(QLineEdit, "ro_input")
            loffset = _widest_offset(lo_field.text()) if lo_field else None
            roffset = _widest_offset(ro_field.text()) if ro_field else None
            if (
                loffset is not None
                and roffset is not None
                and loffset >= 0
                and roffset >= 0
            ):
                min_required = calculate_minimum_rt_window(
                    loffset, roffset, buffer=DEFAULT_RT_WINDOW_BUFFER
                )
                if tr_window < min_required:
                    tr_window = min_required
                    tr_window_field.setText(self._format_number(tr_window))

        except ValueError:
            self._show_message(
                "warning", "Invalid Input", "tR Window must be a valid number"
            )
            tr_window_field.setFocus()
            return

        rt_field = self.findChild(QLineEdit, "tr_input")
        retention_time = None
        rt_mode = "single"
        if rt_field:
            try:
                rt_mode, retention_time, _rt_range = _parse_rt_text(rt_field.text())
            except ValueError:
                retention_time = None
        if retention_time is None:
            retention_time = self._get_current_retention_time()

        samples_to_affect = self._all_samples if self._all_samples else []
        if not samples_to_affect:
            self._show_message(
                "warning", "No Samples", "No samples available for data regeneration."
            )
            return

        if rt_mode == "range" and len(samples_to_affect) > 1:
            retention_time = {
                sample_name: read_compound_with_session(
                    self._current_compound, sample_name
                ).retention_time
                for sample_name in samples_to_affect
            }

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
