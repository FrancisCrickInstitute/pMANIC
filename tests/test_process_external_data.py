from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QApplication, QToolTip

from manic.ui.update_old_data_dialog import UpdateOldDataDialog


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
    dialog._browse_compounds()
    assert picker.isEnabled()
    assert picker.currentText() == "No internal standard"

    picker.showPopup()
    chooser = picker.findChildren(StandardChooser)[-1]
    rows = [chooser.list.item(r).text() for r in range(chooser.list.count())]
    assert rows == ["No internal standard", "scyllo-Ins", "No amount: exports peak areas", "Alanine"]
    QTest.keyClicks(chooser.filter, "scy")
    QTest.keyClick(chooser.filter, Qt.Key_Return)
    assert picker.currentText() == "scyllo-Ins"
    assert dialog.get_internal_standard() == "scyllo-Ins"
    dialog.close()
