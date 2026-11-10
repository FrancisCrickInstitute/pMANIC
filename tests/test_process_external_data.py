from manic.ui.update_old_data_dialog import UpdateOldDataDialog


def test_standard_is_chosen_from_the_compounds_file(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QFileDialog

    from manic.ui.standard_chooser import StandardChooser

    path = tmp_path / "compounds.csv"
    path.write_text(
        "name,tr,mass0,loffset,roffset,labelatoms,intstdamount,amountinstdmix\n"
        "Alanine,5,116,0.1,0.1,3,,\n"
        "scyllo-Ins,9,318,0.1,0.1,6,1.5,2\n"
    )
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    dialog = UpdateOldDataDialog()
    dialog.show()
    picker = dialog.standard_picker
    assert not picker.isEnabled()
    hint = dialog._standard_hint
    assert hint.isVisible()
    dialog._browse_compounds()
    assert picker.isEnabled()
    assert not hint.isVisible()
    assert picker.currentText() == "No internal standard"

    picker.showPopup()
    chooser = picker.findChildren(StandardChooser)[-1]
    rows = [chooser.list.item(r).text() for r in range(chooser.list.count()) if not chooser.list.isRowHidden(r)]
    assert rows == ["No internal standard", "scyllo-Ins", "No amount: exports peak areas", "Alanine"]
    QTest.keyClicks(chooser.filter, "scy")
    QTest.keyClick(chooser.filter, Qt.Key_Return)
    assert picker.currentText() == "scyllo-Ins"
    assert dialog.get_internal_standard() == "scyllo-Ins"
    dialog.close()


def _raw_values_workbook(path):
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "Raw Values"
    for row in (
        ["Compound Name", None, "Alanine", "Alanine"],
        ["Mass", None, 116, 117],
        ["Isotope", None, 0, 1],
        ["tR", None, 5.0, 5.0],
        [None, "Sample_01", 1000, 50],
    ):
        sheet.append(row)
    book.save(path)


def _pick(monkeypatch, dialog, compounds, raw):
    from PySide6.QtWidgets import QFileDialog

    for browse, path in ((dialog._browse_compounds, compounds), (dialog._browse_raw, raw)):
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, p=path, **k: (str(p), ""))
        browse()


def test_unlabelled_compound_list_is_refused_beside_its_field(qapp, tmp_path, monkeypatch):
    compounds = tmp_path / "compounds.csv"
    compounds.write_text("Name,tR,lOffset,rOffset,tR Window\nAlanine,5.0,0.12,0.12,0.08\n")
    raw = tmp_path / "export.xlsx"
    _raw_values_workbook(raw)
    dialog = UpdateOldDataDialog()
    dialog.show()
    _pick(monkeypatch, dialog, compounds, raw)

    assert not dialog._ok_button.isEnabled()
    assert dialog._compounds_error.isVisible()
    assert dialog._compounds_error.text() == "Needs a labelled compound list, with mass0 and labelAtoms columns."
    assert not dialog._standard_hint.isVisible()
    assert not dialog.standard_picker.isEnabled()
    assert not dialog._raw_error.isVisible()
    dialog.close()


def test_workbook_without_raw_values_is_refused_and_a_valid_pair_is_ready(qapp, tmp_path, monkeypatch):
    from openpyxl import Workbook

    compounds = tmp_path / "compounds.csv"
    compounds.write_text("name,tr,mass0,loffset,roffset,labelatoms\nAlanine,5,116,0.1,0.1,3\n")
    other = tmp_path / "other.xlsx"
    Workbook().save(other)
    dialog = UpdateOldDataDialog()
    dialog.show()
    _pick(monkeypatch, dialog, compounds, other)
    assert not dialog._ok_button.isEnabled()
    assert dialog._raw_error.text() == "Needs a workbook with a MANIC Raw Values sheet."

    raw = tmp_path / "export.xlsx"
    _raw_values_workbook(raw)
    _pick(monkeypatch, dialog, compounds, raw)
    assert dialog._ok_button.isEnabled()
    assert not dialog._raw_error.isVisible()
    assert not dialog._compounds_error.isVisible()
    dialog.close()
