from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QToolTip

import manic.ui.main_window as main_window_module
from manic.models.analysis import AnalysisMode
from manic.models.mm_file_check import MmFileStatus
from manic.ui.add_compound_dialog import AddCompoundDialog
from manic.ui.export_options_dialog import ExportOptionsDialog
from manic.ui.post_load_checklist_dialog import PostLoadChecklistDialog
from manic.ui.update_old_data_dialog import UpdateOldDataDialog

from conftest import _make_window


def test_checklist_tooltips_only_reveal_hidden_values(qapp):
    long_pattern = "*_MM_standard_mixture_run_01*,*_MM_standard_mixture_run_02*"
    report = [
        MmFileStatus("Short", "*MM*", ("A", "B")),
        MmFileStatus("Many", "*MM*", ("A", "B", "C", "D")),
        MmFileStatus("Long", long_pattern, ("A",)),
    ]
    dialog = PostLoadChecklistDialog(["Short", "Many", "Long"], None, report, None)
    table = dialog.mm_file_table
    tips = {
        table.item(row, 0).text(): [table.item(row, col).toolTip() for col in range(3)]
        for row in range(table.rowCount())
    }
    assert tips["Short"] == ["", "", ""]
    assert tips["Many"] == ["", "", "A\nB\nC\nD"]
    assert tips["Long"] == ["", long_pattern, ""]
    dialog.close()


def test_flagged_field_shows_its_error_instead_of_required(qapp):
    dialog = AddCompoundDialog(analysis_mode=AnalysisMode.UNLABELLED)
    name = dialog.compound_name
    quantifier = dialog.quantifier_mz.lineEdit()
    assert name.placeholderText() == "Required, e.g. Pyruvate"
    assert dialog.rt_window.placeholderText() == "Optional"

    dialog._on_ok()
    assert name.placeholderText() == ""
    assert quantifier.placeholderText() == ""

    name.setText("Pyruvate")
    assert name.placeholderText() == "Required, e.g. Pyruvate"
    assert quantifier.placeholderText() == ""
    dialog.close()


def test_export_asks_for_options_before_the_location(qapp, empty_db, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    calls = []

    def options_exec(dialog):
        calls.append("options")
        assert [b.text() for b in dialog.findChildren(type(dialog.time_radio))] == [
            "Time-based (recommended)",
            "Legacy (MATLAB-compatible unit spacing)",
        ]
        assert dialog.carbon_enrichment_check is not None
        dialog.legacy_radio.setChecked(True)
        return QDialog.Accepted

    def save_name(*_args, **_kwargs):
        calls.append("location")
        return "/tmp/out.xlsx", ""

    monkeypatch.setattr(ExportOptionsDialog, "exec", options_exec)
    monkeypatch.setattr(main_window_module.QFileDialog, "getSaveFileName", save_name)
    monkeypatch.setattr(window, "_show_question_dialog", lambda *a: QMessageBox.No)
    try:
        assert window.use_legacy_integration is False
        window.export_data()
        assert calls == ["options", "location"]
        assert window.use_legacy_integration is True

        calls.clear()
        monkeypatch.setattr(ExportOptionsDialog, "exec", lambda d: calls.append("options") or 0)
        window.export_data()
        assert calls == ["options"]
    finally:
        window.close()


def test_unlabelled_export_has_no_carbon_sheet_option(qapp):
    dialog = ExportOptionsDialog(False, offer_carbon_enrichment=False)
    assert dialog.carbon_enrichment_check is None
    assert dialog.include_carbon_enrichment() is False
    assert dialog.time_radio.isChecked()
    dialog.close()


def _hover(edit) -> str:
    QToolTip.hideText()
    event = QHelpEvent(QEvent.ToolTip, QPoint(4, 4), edit.mapToGlobal(QPoint(4, 4)))
    QApplication.sendEvent(edit, event)
    return QToolTip.text() if QToolTip.isVisible() else ""


def test_path_tooltip_only_when_the_path_does_not_fit(qapp):
    dialog = UpdateOldDataDialog()
    dialog.show()
    edit = dialog.c_edit
    edit.setText("/a.csv")
    assert _hover(edit) == ""
    long_path = "/Users/someone/" + "deeply/nested/" * 12 + "compounds.csv"
    edit.setText(long_path)
    assert _hover(edit) == long_path
    dialog.close()
