from __future__ import annotations

from pydantic import ValidationError
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator, QValidator
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from manic.io.compounds_import import (
    CompoundRow,
    UnlabelledCompoundRecord,
    duplicate_name_error,
)
from manic.models.analysis import (
    AnalysisMode,
    IonChannel,
    IonRole,
    validate_unlabelled_channels,
)
from manic.ui.dialog_kit import (
    FORM_LABEL_WIDTH,
    MARGIN,
    SECTION_SPACING,
    button_box,
    error_label,
    form_layout,
    form_row,
    hint_label,
    resize_to_screen,
    section_label,
    style_dialog,
    title_label,
    window_title,
)
from manic.ui.theme import set_style_property


class _BlankZero:
    """Shows the placeholder for a blank field and reads it back as 0; a typed 0 stays."""

    def textFromValue(self, value):
        if value == 0 and not self.lineEdit().text().strip():
            return ""
        return super().textFromValue(value)

    def valueFromText(self, text: str):
        return 0 if not text.strip() else super().valueFromText(text)

    def validate(self, text: str, pos: int):
        if not text.strip():
            return (QValidator.Acceptable, text, pos)
        return super().validate(text, pos)


class _BlankZeroSpinBox(_BlankZero, QDoubleSpinBox):
    pass


class _BlankZeroIntSpinBox(_BlankZero, QSpinBox):
    pass


class AddCompoundDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        analysis_mode: AnalysisMode | str = AnalysisMode.LABELLED,
        taken_names: frozenset[str] | set[str] = frozenset(),
    ):
        super().__init__(parent)
        self._mode = AnalysisMode.coerce(analysis_mode)
        self._taken_names = frozenset(taken_names)
        self._record: CompoundRow | UnlabelledCompoundRecord | None = None
        self._errors: dict[QWidget, QLabel] = {}
        self._placeholders: dict[QLineEdit, str] = {}
        # Each problem names the fields it flags; editing any of them clears it.
        self._problems: list[tuple[tuple[QWidget, ...], str]] = []
        self.validation_message = ""
        unlabelled = self._mode is AnalysisMode.UNLABELLED
        self._make_record = (
            self._build_unlabelled_record if unlabelled else self._build_labelled_record
        )

        self.setWindowTitle(window_title("Add Compound"))
        style_dialog(self)
        self.setModal(True)
        self.setMinimumWidth(600)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        outer.setSpacing(8)
        outer.addWidget(title_label("Add compound"))

        form = QWidget()
        layout = QVBoxLayout(form)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)

        identity = self._section(layout, "Identity")
        self.compound_name = QLineEdit()
        self.compound_name.setPlaceholderText("Required, e.g. Pyruvate")
        self._row(identity, "Compound name", self.compound_name)
        if not unlabelled:
            self.formula = QLineEdit()
            self.formula.setPlaceholderText("Optional, e.g. C6H12O6 or C6 H12 O6")
            self._row(identity, "Formula", self.formula)

        retention = self._section(layout, "Retention")
        self.retention_time = self._double_spin("Required")
        self._row(retention, "tR (minutes)", self.retention_time)
        self.loffset = self._double_spin()
        self.roffset = self._double_spin()
        self._row(
            retention,
            "Integration offsets (min)",
            self._inline(("Left", self.loffset), ("Right", self.roffset)),
            error_for=(self.loffset, self.roffset),
        )

        if unlabelled:
            self.rt_window = self._optional_float_edit()
            self._row(
                retention,
                "tR window",
                self.rt_window,
                "Leave blank to use the larger of the left and right offsets.",
            )
            self._add_unlabelled_fields(layout)
        else:
            self._add_labelled_fields(layout)

        standards = self._section(layout, "Standards")
        self.amount_in_std_mix = self._optional_float_edit()
        self._row(standards, "Amount in std mix", self.amount_in_std_mix)
        self.int_std_amount = self._optional_float_edit()
        self._row(standards, "Int std amount", self.int_std_amount)
        self.mm_files = QLineEdit()
        self.mm_files.setPlaceholderText("Optional, e.g. *MM* or *_STD_*")
        self._row(
            standards,
            "MM files",
            self.mm_files,
            "Standard mixture (MM) sample filename patterns, comma-separated.",
        )

        layout.addStretch()

        scroll = QScrollArea()
        scroll.setObjectName("addCompoundScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(form)
        scroll.viewport().setAutoFillBackground(False)
        form.setAutoFillBackground(False)
        outer.addWidget(scroll, stretch=1)

        self._general_error = error_label()
        outer.addWidget(self._general_error)
        buttons, _add = button_box("Add compound")
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        width = 640
        chrome = self.sizeHint().height() - scroll.sizeHint().height()
        resize_to_screen(self, width, chrome + form.heightForWidth(width - 2 * MARGIN))

    @property
    def record(self) -> CompoundRow | UnlabelledCompoundRecord | None:
        return self._record

    def build_record(self) -> CompoundRow | UnlabelledCompoundRecord:
        return self._make_record()

    def _on_ok(self) -> None:
        problems = self._required_problems()
        if not problems:
            try:
                record = self.build_record()
            except (ValueError, ValidationError, TypeError) as exc:
                problems = [self._locate_error(exc)]
        self._show_problems(problems)
        if not problems:
            self._record = record
            self.accept()

    def _required_problems(self) -> list[tuple[tuple[QWidget, ...], str]]:
        """Every missing or taken required value at once, in form order."""
        problems = []
        name = self.compound_name.text().strip()
        if not name:
            problems.append(((self.compound_name,), "Enter a compound name."))
        elif name in self._taken_names:
            problems.append(((self.compound_name,), str(duplicate_name_error(name))))
        required = [(self.retention_time, "tR (minutes)", "tR")]
        if self._mode is AnalysisMode.UNLABELLED:
            required += [
                (self.quantifier_mz, "Quantifier ion m/z", "the quantifier ion m/z"),
                (self.qualifier1_mz, "Qualifier ion 1 m/z", "the qualifier ion 1 m/z"),
            ]
        else:
            required.append((self.mass0, "Mass0 (m/z)", "Mass0"))
        for field, label, noun in required:
            if not field.cleanText().strip():
                problems.append(((field,), f"Enter {noun}."))
            elif field.value() <= 0:
                problems.append(((field,), f"{label} must be greater than 0."))
        return problems

    def _locate_error(self, exc: Exception) -> tuple[tuple[QWidget, ...], str]:
        message, field = str(exc), None
        if isinstance(exc, ValidationError) and exc.errors():
            first = exc.errors()[0]
            loc = first.get("loc") or ()
            message = first.get("msg", message).removeprefix("Value error, ")
            field = getattr(self, str(loc[0]), None) if loc else None
        if isinstance(field, QWidget):
            return (field,), message
        if self._mode is AnalysisMode.UNLABELLED:
            return self._ion_fields_for(message), message
        return (), message

    def _ion_fields_for(self, message: str) -> tuple[QWidget, ...]:
        # The quantifier and qualifier 1 m/z are already known to be positive here.
        if "positive" in message:
            return (self.qualifier2_mz,)
        if "distinct" in message:
            return (self.quantifier_mz, self.qualifier1_mz, self.qualifier2_mz)
        if "tolerance" in message:
            return tuple(
                field
                for field in (self.qualifier1_tolerance, self.qualifier2_tolerance)
                if field.text().strip().startswith("-")
            )
        return ()

    def _show_problems(self, problems: list[tuple[tuple[QWidget, ...], str]]) -> None:
        self._problems = problems
        self._render_problems()
        first = next((fields[0] for fields, _ in problems if fields), None)
        if first is None:
            return
        first.setFocus()
        select_all = getattr(first, "selectAll", None)
        if select_all is not None:
            select_all()

    def _render_problems(self) -> None:
        lines: dict[QLabel, list[str]] = {
            label: [] for label in (*self._errors.values(), self._general_error)
        }
        for fields, message in self._problems:
            label = self._errors[fields[0]] if fields else self._general_error
            lines[label].append(message)
        for label, messages in lines.items():
            label.setText("\n".join(messages))
            label.setVisible(bool(messages))
        flagged = {field for fields, _ in self._problems for field in fields}
        for field in self._errors:
            set_style_property(field, "invalid", field in flagged)
            self._show_placeholder(field, field not in flagged)
        self.validation_message = "\n".join(message for _, message in self._problems)

    def _show_placeholder(self, field: QWidget, shown: bool) -> None:
        """Hide a field's placeholder while its inline error says what to enter."""
        edit = field.lineEdit() if hasattr(field, "lineEdit") else field
        if not isinstance(edit, QLineEdit):
            return
        original = self._placeholders.setdefault(edit, edit.placeholderText())
        edit.setPlaceholderText(original if shown else "")

    def _field_edited(self, field: QWidget) -> None:
        kept = [
            (fields, message)
            for fields, message in self._problems
            if fields and field not in fields
        ]
        if len(kept) != len(self._problems):
            self._problems = kept
            self._render_problems()

    def _section(self, layout: QVBoxLayout, title: str) -> QFormLayout:
        layout.addSpacing(SECTION_SPACING - 8)
        layout.addWidget(section_label(title))
        form = form_layout()
        layout.addLayout(form)
        return form

    def _row(
        self,
        form: QFormLayout,
        text: str,
        field: QWidget,
        hint: str | None = None,
        error_for: tuple[QWidget, ...] | None = None,
    ) -> None:
        container = QWidget()
        column = QVBoxLayout(container)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        column.addWidget(field)
        error = error_label()
        column.addWidget(error)
        if hint:
            column.addWidget(hint_label(hint))
        for target in error_for or (field,):
            self._errors[target] = error
            self._watch(target)
        form_row(form, text, container)

    def _watch(self, field: QLineEdit | QDoubleSpinBox | QSpinBox) -> None:
        field.textChanged.connect(lambda *_args: self._field_edited(field))

    @staticmethod
    def _inline(*pairs: tuple[str, QWidget]) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for index, (text, field) in enumerate(pairs):
            if index:
                layout.addSpacing(8)
            caption = hint_label(text)
            caption.setWordWrap(False)
            layout.addWidget(caption)
            layout.addWidget(field, stretch=1)
        return row

    def _add_labelled_fields(self, layout: QVBoxLayout) -> None:
        mass = self._section(layout, "Mass and labelling")
        self.mass0 = self._double_spin("Required")
        self._row(mass, "Mass0 (m/z)", self.mass0, "m/z of the unlabelled (M+0) ion.")

        self.label_type = QLineEdit()
        self.label_type.setText("C")
        self.label_atoms = self._int_spin()
        self._row(
            mass,
            "Label",
            self._inline(("Element", self.label_type), ("Atoms", self.label_atoms)),
            error_for=(self.label_type, self.label_atoms),
        )

        self.tbdms = self._int_spin()
        self.meox = self._int_spin()
        self.me = self._int_spin()
        self._row(
            mass,
            "Derivatisation groups",
            self._inline(("TBDMS", self.tbdms), ("MeOX", self.meox), ("Me", self.me)),
            "Groups added per molecule: TBDMS (tert-butyldimethylsilyl), "
            "MeOX (methoxyamine), Me (methyl).",
            error_for=(self.tbdms, self.meox, self.me),
        )

    def _add_unlabelled_fields(self, layout: QVBoxLayout) -> None:
        layout.addSpacing(SECTION_SPACING - 8)
        layout.addWidget(section_label("Ions"))

        self.quantifier_mz = self._double_spin("Required")
        self.qualifier1_mz = self._double_spin("Required")
        self.qualifier1_ratio = self._optional_float_edit()
        self.qualifier1_tolerance = self._optional_float_edit()
        self.qualifier2_mz = self._optional_float_edit()
        self.qualifier2_ratio = self._optional_float_edit()
        self.qualifier2_tolerance = self._optional_float_edit()

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        # 4px puts an error right under its row; a zero-height spacer row after each
        # error keeps 8px between rows, as in the forms above.
        grid.setVerticalSpacing(4)
        grid.setColumnMinimumWidth(0, FORM_LABEL_WIDTH + 8)
        for column, text in enumerate(("m/z", "Expected ratio", "Tolerance"), start=1):
            grid.addWidget(hint_label(text), 0, column)
            grid.setColumnStretch(column, 1)
        rows = (
            ("Quantifier ion", (self.quantifier_mz,)),
            (
                "Qualifier ion 1",
                (self.qualifier1_mz, self.qualifier1_ratio, self.qualifier1_tolerance),
            ),
            (
                "Qualifier ion 2",
                (self.qualifier2_mz, self.qualifier2_ratio, self.qualifier2_tolerance),
            ),
        )
        for index, (text, fields) in enumerate(rows):
            row = 3 * index + 2
            spacer = QWidget()
            spacer.setFixedHeight(0)
            grid.addWidget(spacer, row - 1, 0)
            grid.addWidget(QLabel(text), row, 0)
            error = error_label()
            grid.addWidget(error, row + 1, 1, 1, 3)
            for column, field in enumerate(fields, start=1):
                grid.addWidget(field, row, column)
                self._errors[field] = error
                self._watch(field)
        layout.addLayout(grid)
        note = hint_label(
            "A qualifier without a ratio and tolerance is left unassessed in "
            "identity QC. Tolerance is a fraction of the ratio (0.25 = ±25%)."
        )
        note.setContentsMargins(FORM_LABEL_WIDTH + 16, 0, 0, 0)
        layout.addWidget(note)

    def _build_labelled_record(self) -> CompoundRow:
        return CompoundRow(
            compound_name=self.compound_name.text(),
            retention_time=self.retention_time.value(),
            mass0=self.mass0.value(),
            loffset=self.loffset.value(),
            roffset=self.roffset.value(),
            label_atoms=self.label_atoms.value(),
            formula=self.formula.text() or None,
            label_type=self.label_type.text() or "C",
            tbdms=self.tbdms.value(),
            meox=self.meox.value(),
            me=self.me.value(),
            amount_in_std_mix=self._optional_float(self.amount_in_std_mix),
            int_std_amount=self._optional_float(self.int_std_amount),
            mm_files=self.mm_files.text().strip() or None,
        )

    def _build_unlabelled_record(self) -> UnlabelledCompoundRecord:
        channels = [
            IonChannel(
                mz=self.quantifier_mz.value(),
                role=IonRole.QUANTIFIER,
                ordinal=0,
            ),
            IonChannel(
                mz=self.qualifier1_mz.value(),
                role=IonRole.QUALIFIER,
                ordinal=1,
                expected_ratio=self._optional_float(self.qualifier1_ratio),
                ratio_tolerance=self._optional_float(self.qualifier1_tolerance),
            ),
        ]
        qualifier2_mz = self._optional_float(self.qualifier2_mz)
        if qualifier2_mz is not None:
            channels.append(
                IonChannel(
                    mz=qualifier2_mz,
                    role=IonRole.QUALIFIER,
                    ordinal=2,
                    expected_ratio=self._optional_float(self.qualifier2_ratio),
                    ratio_tolerance=self._optional_float(self.qualifier2_tolerance),
                )
            )
        name = self.compound_name.text().strip()
        if not name:
            raise ValueError("compound_name is blank")
        validated = validate_unlabelled_channels(channels)
        return UnlabelledCompoundRecord(
            compound_name=name,
            retention_time=self.retention_time.value(),
            loffset=self.loffset.value(),
            roffset=self.roffset.value(),
            rt_window=self._optional_float(self.rt_window),
            amount_in_std_mix=self._optional_float(self.amount_in_std_mix),
            int_std_amount=self._optional_float(self.int_std_amount),
            mm_files=self.mm_files.text().strip() or None,
            channels=validated,
        )

    # Blank reads back as 0 in every spin box. Required fields reject 0; for the
    # offsets and counts, CompoundRow defaults to 0, so blank and 0 mean the same.
    @staticmethod
    def _double_spin(placeholder: str = "0") -> QDoubleSpinBox:
        box = _BlankZeroSpinBox()
        box.setDecimals(4)
        box.setRange(0.0, 1_000_000.0)
        box.setValue(0.0)
        box.setButtonSymbols(QDoubleSpinBox.NoButtons)
        box.lineEdit().setPlaceholderText(placeholder)
        return box

    @staticmethod
    def _int_spin() -> QSpinBox:
        box = _BlankZeroIntSpinBox()
        box.setRange(0, 100)
        box.setValue(0)
        box.setButtonSymbols(QSpinBox.NoButtons)
        box.lineEdit().setPlaceholderText("0")
        return box

    @staticmethod
    def _optional_float_edit(placeholder: str = "Optional") -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        validator = QDoubleValidator()
        validator.setNotation(QDoubleValidator.StandardNotation)
        edit.setValidator(validator)
        return edit

    @staticmethod
    def _optional_float(edit: QLineEdit) -> float | None:
        text = edit.text().strip()
        if not text:
            return None
        return float(text)
