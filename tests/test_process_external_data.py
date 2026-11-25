from manic.ui.update_old_data_dialog import UpdateOldDataDialog


def test_standard_is_chosen_from_the_compounds_file(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QFileDialog

    from manic.ui.standard_chooser import StandardChooser

    path = tmp_path / "compounds.csv"
    path.write_text(
        "name,tr,mass0,loffset,roffset,labelatoms,formula,intstdamount,amountinstdmix\n"
        "Alanine,5,116,0.1,0.1,3,C3H7NO2,,\n"
        "scyllo-Ins,9,318,0.1,0.1,6,C6H12O6,1.5,2\n"
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
    compounds.write_text(
        "name,tr,mass0,loffset,roffset,labelatoms,formula\nAlanine,5,116,0.1,0.1,3,C3H7NO2\n"
    )
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


def test_compound_list_rows_are_checked_like_a_compound_list_import(tmp_path):
    """A row the import would refuse is refused here too, never skipped."""
    import pytest

    from manic.io.legacy_rebuild import _read_compounds_as_dicts

    header = "name,tr,mass0,loffset,roffset,labelatoms,formula\n"
    path = tmp_path / "compounds.csv"
    path.write_text(header + "Ala,1,116,0.1,0.1,2,C3H7NO2\n,,,,,,\nIS,2,318,0.1,0.1,0,\n")
    # A blank-name row is spacing, as in the import.
    assert [c["compound_name"] for c in _read_compounds_as_dicts(str(path))] == ["Ala", "IS"]

    path.write_text(header + "Ala,1,116,0.1,0.1,2,\nGly,1,x,0.1,0.1,1,C2H5NO2\n")
    with pytest.raises(ValueError) as refused:
        _read_compounds_as_dicts(str(path))
    assert "row 2 (Ala): a labelled compound needs a formula" in str(refused.value)
    assert "row 3 (Gly)" in str(refused.value)


def _write_custom_raw_values(path, rows):
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "Raw Values"
    for row in rows:
        sheet.append(row)
    book.save(path)


def test_raw_values_reader_rejects_isotope_gap_duplicate_and_non_numeric(tmp_path):
    import pytest

    from manic.io.legacy_raw_values_reader import (
        RawValuesFormatError,
        read_raw_values_workbook,
    )

    gap_xlsx = tmp_path / "gap.xlsx"
    _write_custom_raw_values(
        gap_xlsx,
        [
            ["Compound Name", None, "Alanine", "Alanine"],
            ["Mass", None, 116, 118],
            ["Isotope", None, 0, 2],
            ["tR", None, 5.0, 5.0],
            [None, "Sample_01", 1000, 5],
        ],
    )
    with pytest.raises(RawValuesFormatError, match="Alanine.*gap.*M\\+1"):
        read_raw_values_workbook(str(gap_xlsx))

    dup_xlsx = tmp_path / "dup.xlsx"
    _write_custom_raw_values(
        dup_xlsx,
        [
            ["Compound Name", None, "Alanine", "Alanine", "Alanine", "Alanine"],
            ["Mass", None, 116, 117, 117, 118],
            ["Isotope", None, 0, 1, 1, 2],
            ["tR", None, 5.0, 5.0, 5.0, 5.0],
            [None, "Sample_01", 1000, 50, 99, 5],
        ],
    )
    with pytest.raises(RawValuesFormatError, match="Alanine.*duplicate.*M\\+1"):
        read_raw_values_workbook(str(dup_xlsx))

    bad_cell_xlsx = tmp_path / "bad_cell.xlsx"
    _write_custom_raw_values(
        bad_cell_xlsx,
        [
            ["Compound Name", None, "Alanine", "Alanine"],
            ["Mass", None, 116, 117],
            ["Isotope", None, 0, 1],
            ["tR", None, 5.0, 5.0],
            [None, "Sample_01", 1000, "not-a-number"],
        ],
    )
    with pytest.raises(RawValuesFormatError, match="Alanine.*Sample_01"):
        read_raw_values_workbook(str(bad_cell_xlsx))


def test_update_old_data_dialog_shows_specific_raw_values_format_error(
    qapp, tmp_path, monkeypatch
):
    compounds = tmp_path / "compounds.csv"
    compounds.write_text(
        "name,tr,mass0,loffset,roffset,labelatoms,formula\nAlanine,5,116,0.1,0.1,2,C3H7NO2\n"
    )
    gap_xlsx = tmp_path / "gap.xlsx"
    _write_custom_raw_values(
        gap_xlsx,
        [
            ["Compound Name", None, "Alanine", "Alanine"],
            ["Mass", None, 116, 118],
            ["Isotope", None, 0, 2],
            ["tR", None, 5.0, 5.0],
            [None, "Sample_01", 1000, 5],
        ],
    )
    dialog = UpdateOldDataDialog()
    dialog.show()
    _pick(monkeypatch, dialog, compounds, gap_xlsx)
    assert not dialog._ok_button.isEnabled()
    assert dialog._raw_error.isVisible()
    assert "Alanine" in dialog._raw_error.text()
    dialog.close()


def test_rebuild_refuses_uncorrectable_compound_before_writing(tmp_path):
    import pytest

    from manic.io.legacy_rebuild import rebuild_export_from_files

    compounds = tmp_path / "compounds.csv"
    compounds.write_text(
        "name,tr,mass0,loffset,roffset,labelatoms,formula\nSeleno,5,116,0.1,0.1,1,C1Se1\n"
    )
    raw = tmp_path / "raw.xlsx"
    _write_custom_raw_values(
        raw,
        [
            ["Compound Name", None, "Seleno", "Seleno"],
            ["Mass", None, 116, 117],
            ["Isotope", None, 0, 1],
            ["tR", None, 5.0, 5.0],
            [None, "Sample_01", 1000, 10],
        ],
    )
    out = tmp_path / "out.xlsx"
    with pytest.raises(ValueError, match="Seleno"):
        rebuild_export_from_files(str(compounds), str(raw), str(out))
    assert not out.exists()
