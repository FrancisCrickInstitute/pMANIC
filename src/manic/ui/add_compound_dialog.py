from __future__ import annotations

from pydantic import ValidationError
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from manic.io.compounds_import import CompoundRow, UnlabelledCompoundRecord
from manic.models.analysis import (
    AnalysisMode,
    IonChannel,
    IonRole,
    validate_unlabelled_channels,
)


_SPIN_STYLE = "background-color: white; color: black;"


def _error_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = first.get("loc") or ()
            msg = first.get("msg", str(exc))
            if loc:
                return f"{loc[0]}: {msg}"
            return msg
    return str(exc)


class AddCompoundDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        analysis_mode: AnalysisMode | str = AnalysisMode.LABELLED,
    ):
        super().__init__(parent)
        self._mode = AnalysisMode.coerce(analysis_mode)
        self._record: CompoundRow | UnlabelledCompoundRecord | None = None
        unlabelled = self._mode is AnalysisMode.UNLABELLED
        self._make_record = (
            self._build_unlabelled_record if unlabelled else self._build_labelled_record
        )

        self.setWindowTitle("Add Compound")
        self.setModal(True)
        self.setMinimumWidth(640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.compound_name = QLineEdit()
        form.addRow("Compound name:", self.compound_name)

        self.retention_time = self._double_spin()
        form.addRow("tR (minutes):", self.retention_time)

        self.loffset = self._double_spin()
        form.addRow("Left offset:", self.loffset)

        self.roffset = self._double_spin()
        form.addRow("Right offset:", self.roffset)

        if unlabelled:
            self._add_unlabelled_fields(form)
        else:
            self._add_labelled_fields(form)

        self.amount_in_std_mix = self._optional_float_edit()
        form.addRow("Amount in std mix:", self.amount_in_std_mix)

        self.int_std_amount = self._optional_float_edit()
        form.addRow("Int std amount:", self.int_std_amount)

        self.mm_files = QLineEdit()
        form.addRow("MM files:", self.mm_files)
        form.addRow("", self._hint("Comma-separated patterns, for example *MM* or *_STD_*."))

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def record(self) -> CompoundRow | UnlabelledCompoundRecord | None:
        return self._record

    def build_record(self) -> CompoundRow | UnlabelledCompoundRecord:
        return self._make_record()

    def _on_ok(self) -> None:
        try:
            self._record = self.build_record()
        except (ValueError, ValidationError, TypeError) as exc:
            self._show_warning(_error_message(exc))
            return
        self.accept()

    def _show_warning(self, message: str) -> None:
        parent = self.parent()
        if parent is not None and hasattr(parent, "_create_message_box"):
            box = parent._create_message_box("warning", "Add Compound", message)
            box.exec()
            return
        QMessageBox.warning(self, "Add Compound", message)

    def _add_labelled_fields(self, form: QFormLayout) -> None:
        self.mass0 = self._double_spin()
        form.addRow("Mass0 (m/z):", self.mass0)

        self.label_atoms = self._int_spin()
        form.addRow("Label atoms:", self.label_atoms)

        self.formula = QLineEdit()
        form.addRow("Formula:", self.formula)
        form.addRow(
            "",
            self._hint("C6H12O6, or space-separated counts such as C6 H12 O6."),
        )

        self.label_type = QLineEdit()
        self.label_type.setText("C")
        form.addRow("Label type:", self.label_type)

        self.tbdms = self._int_spin()
        form.addRow("TBDMS:", self.tbdms)

        self.meox = self._int_spin()
        form.addRow("MeOX:", self.meox)

        self.me = self._int_spin()
        form.addRow("Me:", self.me)

    def _add_unlabelled_fields(self, form: QFormLayout) -> None:
        self.quantifier_mz = self._double_spin()
        form.addRow("Quantifier ion (m/z):", self.quantifier_mz)

        self.qualifier1_mz = self._double_spin()
        form.addRow("Qualifier ion 1 (m/z):", self.qualifier1_mz)

        self.qualifier1_ratio = self._optional_float_edit()
        form.addRow("Qualifier 1 expected ratio:", self.qualifier1_ratio)

        self.qualifier1_tolerance = self._optional_float_edit()
        form.addRow("Qualifier 1 tolerance:", self.qualifier1_tolerance)

        self.qualifier2_mz = self._optional_float_edit()
        form.addRow("Qualifier ion 2 (m/z):", self.qualifier2_mz)

        self.qualifier2_ratio = self._optional_float_edit()
        form.addRow("Qualifier 2 expected ratio:", self.qualifier2_ratio)

        self.qualifier2_tolerance = self._optional_float_edit()
        form.addRow("Qualifier 2 tolerance:", self.qualifier2_tolerance)

        self.rt_window = self._optional_float_edit()
        form.addRow("tR window:", self.rt_window)
        form.addRow(
            "",
            self._hint("Leave blank to use the larger of the left and right offsets."),
        )

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
    def _double_spin() -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setDecimals(4)
        box.setRange(0.0, 1_000_000.0)
        box.setValue(0.0)
        box.setButtonSymbols(QDoubleSpinBox.NoButtons)
        box.setStyleSheet(f"QDoubleSpinBox {{ {_SPIN_STYLE} }}")
        return box

    @staticmethod
    def _int_spin() -> QSpinBox:
        box = QSpinBox()
        box.setRange(0, 100)
        box.setValue(0)
        box.setButtonSymbols(QSpinBox.NoButtons)
        box.setStyleSheet(f"QSpinBox {{ {_SPIN_STYLE} }}")
        return box

    @staticmethod
    def _optional_float_edit() -> QLineEdit:
        edit = QLineEdit()
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

    @staticmethod
    def _hint(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: gray; font-style: italic;")
        return label
