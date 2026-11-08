from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QApplication, QToolTip

from manic.ui.recovery_dialog import RecoveryDialog


def _samples(names):
    return RecoveryDialog("sample", lambda: names, lambda _names: 0)


def test_compound_recovery_restores_selected_names(qapp):
    restored = []
    dialog = RecoveryDialog(
        "compound", lambda: ["Citrate", "Malate"], lambda names: restored.extend(names) or len(names)
    )
    emitted = []
    dialog.restored.connect(emitted.append)
    assert dialog.windowTitle() == "Recover Deleted Compounds — MANIC"
    assert not dialog.restore_btn.isEnabled()

    dialog.item_list.item(1).setSelected(True)
    assert dialog.restore_btn.isEnabled()
    assert dialog.status_label.text() == "1 of 2 selected"
    dialog.restore_btn.click()

    assert restored == ["Malate"]
    assert emitted == [["Malate"]]
    assert dialog.result() == RecoveryDialog.Accepted


def test_sample_recovery_shows_empty_state(qapp):
    dialog = _samples([])
    assert dialog.item_list.count() == 0
    assert dialog.title.text() == "No deleted samples"
    for widget in (dialog.item_list, dialog.status_label):
        assert widget.isHidden()
    visible = [b.text() for b in dialog.buttons.buttons() if not b.isHidden()]
    assert visible == ["Close"]


def test_sample_recovery_fits_its_names_without_a_void(qapp):
    dialog = _samples(["Bio_001", "Bio_002", "Bio_003"])
    dialog.show()
    qapp.processEvents()
    try:
        last = dialog.item_list.visualItemRect(dialog.item_list.item(2))
        assert last.bottom() <= dialog.item_list.viewport().height()
        # A fixed 480 px used to leave most of the dialog empty under a few names.
        assert dialog.height() < 300
    finally:
        dialog.close()


def test_recovery_keeps_long_names_apart_and_shows_them_in_full_on_hover(qapp):
    names = [
        f"2026-10-28_GCMS_StableIsotope_Experiment_17_Batch04_Replicate_00{i}_Rerun_02"
        for i in (1, 2)
    ]
    dialog = _samples(names)
    dialog.show()
    qapp.processEvents()
    try:
        items = dialog.item_list
        assert not items.horizontalScrollBar().isVisible()
        point = items.visualItemRect(items.item(1)).topLeft() + QPoint(20, 5)
        QApplication.sendEvent(
            items.viewport(), QHelpEvent(QEvent.ToolTip, point, items.viewport().mapToGlobal(point))
        )
        assert QToolTip.text() == names[1]
        QToolTip.hideText()
        items.item(0).setSelected(True)
        items.item(1).setSelected(True)
        assert dialog.status_label.text() == "2 of 2 selected"
    finally:
        dialog.close()
