from __future__ import annotations

from pydantic import ValidationError
from PySide6.QtGui import QDoubleValidator, QValidator
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
    section_label,
    set_invalid,
    style_dialog,
    title_label,
    window_title,
)


class _BlankZeroSpinBox(QDoubleSpinBox):
    """Shows its placeholder instead of 0; the value stays 0.0, which validation rejects."""

    def textFromValue(self, value: float) -> str:
        return "" if value == 0 else super().textFromValue(value)

    def valueFromText(self, text: str) -> float:
        return 0.0 if not text.strip() else super().valueFromText(text)

    def validate(self, text: str, pos: int):
        if not text.strip():
            return (QValidator.Acceptable, text, pos)
        return super().validate(text, pos)


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
        self._invalid: QWidget | None = None
        self.validation_message = ""
        unlabelled = self._mode is AnalysisMode.UNLABELLED
        self._make_record = (
            self._build_unlabelled_record if unlabelled else self._build_labelled_record
        )

        self.setWindowTitle(window_title("Add Compound"))
        style_dialog(self)
        self.setModal(True)
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        layout.setSpacing(8)
        layout.addWidget(title_label("Add compound"))

        identity = self._section(layout, "Identity")
        self.compound_name = QLineEdit()
        self.compound_name.setPlaceholderText("Required, e.g. Pyruvate")
        self._row(identity, "Compound name", self.compound_name)
        if not unlabelled:
            self.formula = QLineEdit()
            self.formula.setPlaceholderText("Optional, e.g. C6H12O6 or C6 H12 O6")
            self._row(identity, "Formula", self.formula)

        retention = self._section(layout, "Retention")
        self.retention_time = self._double_spin(required=True)
        self._row(retention, "tR (minutes)", self.retention_time)
        self.loffset = self._double_spin()
        self.roffset = self._double_spin()
        self._row(
            retention,
            "Integration offsets",
            self._inline(("Left", self.loffset), ("Right", self.roffset)),
            "Minutes before (left) and after (right) tR that bound the peak.",
            error_for=(self.loffset, self.roffset),
        )

        if unlabelled:
            self.rt_window = self._optional_float_edit("Optional, defaults to the larger offset")
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

        layout.addSpacing(8)
        self._general_error = error_label()
        layout.addWidget(self._general_error)
        layout.addStretch()
        buttons, _add = button_box("Add compound")
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def record(self) -> CompoundRow | UnlabelledCompoundRecord | None:
        return self._record

    def build_record(self) -> CompoundRow | UnlabelledCompoundRecord:
        return self._make_record()

    def _on_ok(self) -> None:
        self._clear_errors()
        try:
            record = self.build_record()
        except (ValueError, ValidationError, TypeError) as exc:
            self._show_error(*self._locate_error(exc))
            return
        if record.retention_time <= 0:
            self._show_error("tR (minutes) must be greater than 0.", self.retention_time)
            return
        if isinstance(record, CompoundRow) and record.mass0 <= 0:
            self._show_error("Mass0 (m/z) must be greater than 0.", self.mass0)
            return
        if record.compound_name in self._taken_names:
            self._show_error(
                str(duplicate_name_error(record.compound_name)), self.compound_name
            )
            return
        self._record = record
        self.accept()

    def _locate_error(self, exc: Exception) -> tuple[str, QWidget | None]:
        message, field = str(exc), None
        if isinstance(exc, ValidationError) and exc.errors():
            first = exc.errors()[0]
            loc = first.get("loc") or ()
            message = first.get("msg", message).removeprefix("Value error, ")
            field = getattr(self, str(loc[0]), None) if loc else None
        if message == "compound_name is blank":
            return "Enter a compound name.", self.compound_name
        if field is None and self._mode is AnalysisMode.UNLABELLED:
            field = self._ion_field_for(message)
        return message, field if isinstance(field, QWidget) else None

    def _ion_field_for(self, message: str) -> QWidget | None:
        if "positive" in message:
            for field in (self.quantifier_mz, self.qualifier1_mz):
                if field.value() <= 0:
                    return field
            return self.qualifier2_mz
        if "distinct" in message:
            return self.qualifier1_mz
        if "tolerance" in message:
            for field in (self.qualifier1_tolerance, self.qualifier2_tolerance):
                if field.text().strip().startswith("-"):
                    return field
        return None

    def _show_error(self, message: str, field: QWidget | None = None) -> None:
        self.validation_message = message
        label = self._errors.get(field, self._general_error)
        label.setText(message)
        label.show()
        if field is None:
            return
        set_invalid(field, True)
        self._invalid = field
        field.setFocus()
        select_all = getattr(field, "selectAll", None)
        if select_all is not None:
            select_all()

    def _clear_errors(self, *_args) -> None:
        if not self.validation_message:
            return
        self.validation_message = ""
        for label in {*self._errors.values(), self._general_error}:
            label.hide()
        if self._invalid is not None:
            set_invalid(self._invalid, False)
            self._invalid = None

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
        if hint:
            column.addWidget(hint_label(hint))
        error = error_label()
        column.addWidget(error)
        for target in error_for or (field,):
            self._errors[target] = error
            self._watch(target)
        form_row(form, text, container)

    def _watch(self, field: QLineEdit | QDoubleSpinBox | QSpinBox) -> None:
        field.textChanged.connect(self._clear_errors)

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
        self.mass0 = self._double_spin(required=True)
        self._row(mass, "Mass0 (m/z)", self.mass0, "m/z of the unlabelled (M+0) ion.")

        self.label_type = QLineEdit()
        self.label_type.setText("C")
        self.label_atoms = self._int_spin()
        self._row(
            mass,
            "Label",
            self._inline(("Element", self.label_type), ("Atoms", self.label_atoms)),
            "The labelled element and how many of its atoms can carry it.",
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

        self.quantifier_mz = self._double_spin(required=True)
        self.qualifier1_mz = self._double_spin(required=True)
        self.qualifier1_ratio = self._optional_float_edit()
        self.qualifier1_tolerance = self._optional_float_edit()
        self.qualifier2_mz = self._optional_float_edit()
        self.qualifier2_ratio = self._optional_float_edit()
        self.qualifier2_tolerance = self._optional_float_edit()

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
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
        error = error_label()
        for row, (text, fields) in enumerate(rows, start=1):
            grid.addWidget(QLabel(text), row, 0)
            for column, field in enumerate(fields, start=1):
                grid.addWidget(field, row, column)
                self._errors[field] = error
                self._watch(field)
        layout.addLayout(grid)
        notes = QVBoxLayout()
        notes.setContentsMargins(FORM_LABEL_WIDTH + 16, 0, 0, 0)
        notes.setSpacing(4)
        notes.addWidget(error)
        notes.addWidget(
            hint_label(
                "Provide two qualifier ions, each with an expected ratio and a "
                "tolerance (a fraction of the ratio, 0.25 = ±25%). Blank fields are "
                "accepted but leave identity QC unassessed."
            )
        )
        layout.addLayout(notes)

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

    @staticmethod
    def _double_spin(required: bool = False) -> QDoubleSpinBox:
        box = _BlankZeroSpinBox() if required else QDoubleSpinBox()
        box.setDecimals(4)
        box.setRange(0.0, 1_000_000.0)
        box.setValue(0.0)
        box.setButtonSymbols(QDoubleSpinBox.NoButtons)
        if required:
            box.lineEdit().setPlaceholderText("Required")
        return box

    @staticmethod
    def _int_spin() -> QSpinBox:
        box = QSpinBox()
        box.setRange(0, 100)
        box.setValue(0)
        box.setButtonSymbols(QSpinBox.NoButtons)
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
