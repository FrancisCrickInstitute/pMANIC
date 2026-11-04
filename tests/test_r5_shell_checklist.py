from pathlib import Path
from unittest import mock

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QLabel, QPushButton

from manic.models.mm_file_check import MmFileStatus
from manic.ui.post_load_checklist_dialog import PostLoadChecklistDialog

REPORT = [MmFileStatus("Alanine", None, ())]


def _texts(dialog) -> str:
    return "\n".join(label.text() for label in dialog.findChildren(QLabel))


def test_checklist_names_the_loaded_compound_list_and_opens_it(qapp, tmp_path):
    path = tmp_path / "compounds_v3.xlsx"
    path.write_bytes(b"")
    dialog = PostLoadChecklistDialog(
        ["Alanine"], None, REPORT, None, compound_list_path=str(path)
    )
    source = dialog.findChild(QLabel, "compoundListFile")
    assert source.text() == "Compound list: compounds_v3.xlsx"
    assert source.toolTip() == str(path)

    with mock.patch(
        "manic.ui.post_load_checklist_dialog.QDesktopServices.openUrl"
    ) as open_url:
        dialog.findChild(QPushButton, "openCompoundListButton").click()
        dialog.findChild(QPushButton, "showCompoundListFolderButton").click()
    assert [c.args[0] for c in open_url.call_args_list] == [
        QUrl.fromLocalFile(str(path)),
        QUrl.fromLocalFile(str(Path(tmp_path))),
    ]
    dialog.close()


def test_checklist_teaches_the_reload_path_for_existing_compounds(qapp):
    dialog = PostLoadChecklistDialog(["Alanine"], None, REPORT, None)
    text = _texts(dialog)
    assert "Compound list: the file you loaded" in text
    assert dialog.findChild(QPushButton, "openCompoundListButton") is None
    clear = text.index("File → Clear Session")
    reload = text.index("File → Load Compounds/Parameter List")
    add = text.index("File → Add Compound...")
    assert clear < reload < add
    assert "importing a session exported earlier brings its old patterns back" in text
    dialog.close()
