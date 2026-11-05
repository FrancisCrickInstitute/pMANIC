from manic.ui import compound_recovery_dialog, sample_recovery_dialog
from manic.ui.compound_recovery_dialog import CompoundRecoveryDialog
from manic.ui.sample_recovery_dialog import SampleRecoveryDialog


def test_compound_recovery_restores_selected_names(qapp, monkeypatch):
    restored = []
    monkeypatch.setattr(
        compound_recovery_dialog, "get_deleted_compounds", lambda: ["Citrate", "Malate"]
    )
    monkeypatch.setattr(
        compound_recovery_dialog,
        "restore_compounds",
        lambda names: restored.extend(names) or len(names),
    )
    dialog = CompoundRecoveryDialog()
    emitted = []
    dialog.compounds_restored.connect(emitted.append)
    assert dialog.windowTitle() == "Recover Deleted Compounds — MANIC"
    assert not dialog.restore_btn.isEnabled()

    dialog.item_list.item(1).setSelected(True)
    assert dialog.restore_btn.isEnabled()
    assert dialog.status_label.text() == "1 of 2 selected"
    dialog.restore_btn.click()

    assert restored == ["Malate"]
    assert emitted == [["Malate"]]
    assert dialog.result() == CompoundRecoveryDialog.Accepted


def test_sample_recovery_shows_empty_state(qapp, monkeypatch):
    monkeypatch.setattr(sample_recovery_dialog, "get_deleted_samples", lambda: [])
    dialog = SampleRecoveryDialog()
    assert dialog.item_list.count() == 0
    assert dialog.title.text() == "No deleted samples"
    for widget in (dialog.item_list, dialog.status_label):
        assert widget.isHidden()
    visible = [b.text() for b in dialog.buttons.buttons() if not b.isHidden()]
    assert visible == ["Close"]


def test_sample_recovery_fits_its_names_without_a_void(qapp, monkeypatch):
    names = ["Bio_001", "Bio_002", "Bio_003"]
    monkeypatch.setattr(sample_recovery_dialog, "get_deleted_samples", lambda: names)
    dialog = SampleRecoveryDialog()
    dialog.show()
    qapp.processEvents()
    try:
        last = dialog.item_list.visualItemRect(dialog.item_list.item(2))
        assert last.bottom() <= dialog.item_list.viewport().height()
        # A fixed 480 px used to leave most of the dialog empty under a few names.
        assert dialog.height() < 300
    finally:
        dialog.close()
