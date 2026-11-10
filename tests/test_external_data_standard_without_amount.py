from unittest.mock import Mock

from openpyxl import Workbook, load_workbook


def test_standard_without_amount_in_std_mix_rebuilds_peak_areas(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog, QFileDialog

    from conftest import _make_window
    from manic.ui.standard_chooser import StandardChooser
    from manic.ui.update_old_data_dialog import UpdateOldDataDialog

    compounds = tmp_path / "compounds.csv"
    compounds.write_text(
        "name,tr,mass0,loffset,roffset,labelatoms,amountinstdmix,intstdamount,mmfiles\n"
        "IS,1.0,100,0.1,0.1,0,,2.0,*MM*\n"
        "Ala,2.0,116,0.1,0.1,0,5.0,,*MM*\n"
    )
    raw = tmp_path / "raw_values.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "Raw Values"
    for row in (
        ["Compound Name", None, "IS", "Ala"],
        ["Mass", None, 100, 116],
        ["Isotope", None, 0, 0],
        ["tR", None, 1.0, 2.0],
        [None, "MM_01", 100.0, 50.0],
        [None, "S1", 80.0, 40.0],
    ):
        sheet.append(row)
    book.save(raw)
    out = tmp_path / "out.xlsx"

    def pick_files_and_standard(dialog):
        for browse, path in ((dialog._browse_compounds, compounds), (dialog._browse_raw, raw)):
            monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, p=path, **k: (str(p), ""))
            browse()
        dialog.standard_picker.showPopup()
        chooser = dialog.standard_picker.findChildren(StandardChooser)[-1]
        QTest.keyClicks(chooser.filter, "IS")
        QTest.keyClick(chooser.filter, Qt.Key_Return)
        assert dialog.standard_picker.currentText() == "IS"
        return QDialog.Accepted

    monkeypatch.setattr(UpdateOldDataDialog, "exec", pick_files_and_standard)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    window = _make_window(monkeypatch)
    shown = []
    monkeypatch.setattr(
        window, "_create_message_box", lambda kind, title, text, *a: shown.append((title, text)) or Mock()
    )
    try:
        window.update_old_data()
    finally:
        window.close()

    assert shown == [("Update Complete", f"Export rebuilt successfully to:\n{out}")]
    rows = list(load_workbook(out, read_only=True)["Abundances"].iter_rows(min_row=5, max_row=7, values_only=True))
    assert rows == [
        ("Units", None, "Peak Area", "Peak Area"),
        (None, "MM_01", 100.0, 50.0),
        (None, "S1", 80.0, 40.0),
    ]
