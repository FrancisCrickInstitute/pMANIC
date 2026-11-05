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
