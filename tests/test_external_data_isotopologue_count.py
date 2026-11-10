from types import SimpleNamespace

from openpyxl import Workbook
from PySide6.QtWidgets import QDialog, QFileDialog

from conftest import _make_window
from manic.ui.update_old_data_dialog import UpdateOldDataDialog


def test_rebuild_names_compounds_whose_isotopologue_count_differs(qapp, tmp_path, monkeypatch):
    compounds = tmp_path / "compounds.csv"
    compounds.write_text(
        "name,tr,mass0,loffset,roffset,labelatoms,formula\n"
        "Alanine,5,116,0.1,0.1,3,C3H7NO2\n"
        "Lactate,6,117,0.1,0.1,1,C3H6O3\n"
        "Glycine,7,102,0.1,0.1,1,C2H5NO2\n"
    )
    raw = tmp_path / "export.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "Raw Values"
    for row in (
        ["Compound Name", None, "Alanine", "Alanine", "Lactate", "Lactate", "Glycine", "Glycine", "Glycine"],
        ["Mass", None, 116, 117, 117, 118, 102, 103, 104],
        ["Isotope", None, 0, 1, 0, 1, 0, 1, 2],
        ["tR", None, 5.0, 5.0, 6.0, 6.0, 7.0, 7.0, 7.0],
        [None, "Sample_01", 1000, 50, 800, 40, 600, 30, 3],
    ):
        sheet.append(row)
    book.save(raw)
    out = tmp_path / "rebuilt.xlsx"

    picks = iter([str(compounds), str(raw)])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (next(picks), ""))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))

    def pick_both(dialog):
        dialog._browse_compounds()
        dialog._browse_raw()
        return QDialog.Accepted

    monkeypatch.setattr(UpdateOldDataDialog, "exec", pick_both)
    window = _make_window(monkeypatch)
    messages = []
    monkeypatch.setattr(
        window, "_create_message_box", lambda *args: messages.append(args) or SimpleNamespace(exec=lambda: None)
    )

    window.update_old_data()

    assert messages == [
        (
            "critical",
            "Update Failed",
            "Failed to rebuild export.\n"
            "The Raw Values workbook needs label atoms + 1 isotopologue columns for each compound: "
            "Alanine (expected 4, found 2), Glycine (expected 2, found 3)",
        )
    ]
    assert not out.exists()
