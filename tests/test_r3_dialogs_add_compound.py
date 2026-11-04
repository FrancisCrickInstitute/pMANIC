from __future__ import annotations

from itertools import combinations

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
)

from manic.models.analysis import AnalysisMode
from manic.ui.add_compound_dialog import AddCompoundDialog


def _flagged(dialog: AddCompoundDialog) -> set[str]:
    names = (
        "compound_name",
        "retention_time",
        "mass0",
        "quantifier_mz",
        "qualifier1_mz",
        "loffset",
    )
    return {
        name
        for name in names
        if hasattr(dialog, name) and getattr(dialog, name).property("invalid") is True
    }


def test_empty_labelled_submit_flags_every_required_field(qapp):
    dialog = AddCompoundDialog(analysis_mode=AnalysisMode.LABELLED)
    dialog.show()
    dialog._on_ok()
    assert dialog.record is None
    assert dialog.validation_message.splitlines() == [
        "Enter a compound name.",
        "tR (minutes) must be greater than 0.",
        "Mass0 (m/z) must be greater than 0.",
    ]
    assert _flagged(dialog) == {"compound_name", "retention_time", "mass0"}
    assert dialog.focusWidget() is dialog.compound_name
    dialog.close()


def test_empty_unlabelled_submit_flags_every_required_field(qapp):
    dialog = AddCompoundDialog(analysis_mode=AnalysisMode.UNLABELLED)
    dialog.show()
    dialog._on_ok()
    assert dialog.record is None
    assert dialog.validation_message.splitlines() == [
        "Enter a compound name.",
        "tR (minutes) must be greater than 0.",
        "Quantifier ion m/z must be greater than 0.",
        "Qualifier ion 1 m/z must be greater than 0.",
    ]
    assert _flagged(dialog) == {
        "compound_name",
        "retention_time",
        "quantifier_mz",
        "qualifier1_mz",
    }
    dialog.close()


def test_editing_one_field_clears_only_its_own_error(qapp):
    dialog = AddCompoundDialog(analysis_mode=AnalysisMode.UNLABELLED)
    dialog._on_ok()
    dialog.quantifier_mz.setValue(273.0)
    assert _flagged(dialog) == {"compound_name", "retention_time", "qualifier1_mz"}
    assert "Quantifier ion m/z must be greater than 0." not in dialog.validation_message
    assert "Qualifier ion 1 m/z must be greater than 0." in dialog.validation_message


def test_duplicate_name_is_reported_with_missing_fields(qapp):
    dialog = AddCompoundDialog(
        analysis_mode=AnalysisMode.LABELLED, taken_names={"Alanine"}
    )
    dialog.compound_name.setText("Alanine")
    dialog._on_ok()
    lines = dialog.validation_message.splitlines()
    assert "already exists" in lines[0]
    assert lines[1:] == [
        "tR (minutes) must be greater than 0.",
        "Mass0 (m/z) must be greater than 0.",
    ]


def test_cross_field_ion_error_flags_the_ions_and_clears_on_edit(qapp):
    dialog = AddCompoundDialog(analysis_mode=AnalysisMode.UNLABELLED)
    dialog.compound_name.setText("Citrate")
    dialog.retention_time.setValue(12.4)
    dialog.quantifier_mz.setValue(147.0)
    dialog.qualifier1_mz.setValue(147.0)
    dialog._on_ok()
    assert dialog.validation_message == (
        "Quantifier and qualifier m/z values must be distinct"
    )
    assert {"quantifier_mz", "qualifier1_mz"} <= _flagged(dialog)
    dialog.quantifier_mz.setValue(273.0)
    assert dialog.validation_message == ""
    assert _flagged(dialog) == set()


def test_offsets_and_counts_start_blank_and_build_as_zero(qapp):
    dialog = AddCompoundDialog(analysis_mode=AnalysisMode.LABELLED)
    for field in (
        dialog.loffset,
        dialog.roffset,
        dialog.label_atoms,
        dialog.tbdms,
        dialog.meox,
        dialog.me,
    ):
        assert field.text() == ""
        assert field.lineEdit().placeholderText() == "0"
    dialog.compound_name.setText("Alanine")
    dialog.retention_time.setValue(3.2)
    dialog.mass0.setValue(116.0)
    record = dialog.build_record()
    assert (record.loffset, record.roffset) == (0.0, 0.0)
    assert (record.label_atoms, record.tbdms, record.meox, record.me) == (0, 0, 0, 0)


def _overlapping_fields(form) -> list[tuple[str, str]]:
    rects: list[tuple[str, QRect]] = []
    for widget in form.findChildren(QLabel) + form.findChildren(QLineEdit):
        if not widget.isVisible() or isinstance(widget.parent(), QAbstractSpinBox):
            continue
        rects.append((widget.text(), QRect(widget.mapTo(form, QPoint()), widget.size())))
    for spin in form.findChildren(QAbstractSpinBox):
        rects.append(("spin box", QRect(spin.mapTo(form, QPoint()), spin.size())))
    return [(a, b) for (a, ra), (b, rb) in combinations(rects, 2) if ra.intersects(rb)]


@pytest.mark.parametrize("mode", list(AnalysisMode))
def test_form_never_overlaps_and_scrolls_on_a_short_screen(qapp, mode):
    dialog = AddCompoundDialog(analysis_mode=mode)
    dialog.show()
    dialog._on_ok()
    qapp.processEvents()
    form = dialog.findChild(QScrollArea).widget()
    assert _overlapping_fields(form) == []

    dialog.resize(640, 420)
    qapp.processEvents()
    assert _overlapping_fields(form) == []
    assert dialog.findChild(QScrollArea).verticalScrollBar().maximum() > 0
    add = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Add compound")
    assert dialog.rect().contains(QRect(add.mapTo(dialog, QPoint()), add.size()))
    assert not form.isAncestorOf(add)
    dialog.close()
