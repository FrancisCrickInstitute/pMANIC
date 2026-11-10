from manic.ui.recovery_dialog import RecoveryDialog


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


