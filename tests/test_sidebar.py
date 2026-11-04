from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from manic.models.analysis import AnalysisMode
from manic.ui.left_toolbar import Toolbar
from manic.ui.loaded_data_widget import LoadedDataWidget
from manic.ui.standard_indicator_widget import StandardIndicator


def _press(widget, key) -> None:
    QApplication.sendEvent(widget, QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.NoModifier))


def _toolbar(monkeypatch) -> Toolbar:
    monkeypatch.setattr(
        "manic.ui.left_toolbar.read_compound",
        lambda _name: SimpleNamespace(deconvolution_level="off", baseline_correction=0),
    )
    return Toolbar(AnalysisMode.LABELLED)


def test_internal_standard_row_is_optional_until_chosen(qapp):
    row = StandardIndicator()
    assert row.internal_standard is None
    assert row.value_text() == "None"
    assert row._value.property("state") == "optional"

    row.set_internal_standard("Norvaline")
    assert row.internal_standard == "Norvaline"
    assert row.value_text() == "Norvaline"
    assert row._value.property("state") == "done"

    row.clear_internal_standard()
    assert row.internal_standard is None
    assert row.value_text() == "None"


def test_data_rows_report_load_state_without_counts_or_links(qapp):
    rows = LoadedDataWidget()
    assert rows.compounds_row.value_text() == "Not loaded"
    assert rows.raw_data_row.value_text() == "Not loaded"

    rows.update_status(False, True)
    assert rows.compounds_row.value_text() == ""
    assert rows.compounds_row._state == "done"
    assert rows.raw_data_row.value_text() == "Not loaded"

    # The counts live with Compounds and Samples; loading lives on the canvas and in File.
    rows.update_status(True, True)
    assert rows.raw_data_row._state == "done"
    assert rows.raw_data_row.value_text() == ""


def test_compound_filter_narrows_list_and_enter_picks_first_match(qapp, monkeypatch):
    toolbar = _toolbar(monkeypatch)
    picked = []
    toolbar.compound_selected.connect(picked.append)
    try:
        toolbar.update_label_colours(False, True)
        toolbar.update_compound_list(["Alanine", "Glutamate", "Glycine"])
        assert toolbar.compound_count_label.text() == "3"

        toolbar.compound_filter.setText("gl")
        assert [
            toolbar.compound_list.item(r).text()
            for r in range(3)
            if not toolbar.compound_list.isRowHidden(r)
        ] == ["Glutamate", "Glycine"]
        assert toolbar.compound_count_label.text() == "2 of 3"

        _press(toolbar.compound_filter, Qt.Key_Return)
        assert toolbar.get_selected_compound() == "Glutamate"

        toolbar.step_compound(1)
        assert toolbar.get_selected_compound() == "Glycine"
        toolbar.step_compound(1)
        assert toolbar.get_selected_compound() == "Glycine"
        toolbar.step_compound(-1)
        assert toolbar.get_selected_compound() == "Glutamate"
        assert picked[-3:] == ["Glutamate", "Glycine", "Glutamate"]
    finally:
        toolbar.deleteLater()


def test_sample_header_counts_shown_samples(qapp, monkeypatch):
    toolbar = _toolbar(monkeypatch)
    try:
        toolbar.update_label_colours(True, True)
        toolbar.update_sample_list(["S1", "S2", "S3"])
        assert toolbar.samples_section.summary.full_text() == "3 · all shown"
        toolbar.set_selected_samples(["S2"])
        assert toolbar.samples_section.summary.full_text() == "1 of 3 shown"
    finally:
        toolbar.deleteLater()


def test_inspector_waits_for_raw_data(qapp, monkeypatch):
    toolbar = _toolbar(monkeypatch)
    try:
        assert toolbar.inspector.isHidden()
        toolbar.update_label_colours(True, True)
        assert not toolbar.inspector.isHidden()
    finally:
        toolbar.deleteLater()
