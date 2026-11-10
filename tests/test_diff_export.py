import sys
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from diff_export import diff_workbooks, main


def _write(path, value):
    wb = Workbook()
    wb.active.title = "Abundances"
    wb.active.append(["Sample", "Glucose"])
    wb.active.append(["S1", value])
    wb.create_sheet("Raw Values").append(["x", 1])
    wb.save(path)
    return path


def test_identical_exports_pass(tmp_path):
    a = _write(tmp_path / "a.xlsx", 1.25)
    b = _write(tmp_path / "b.xlsx", 1.25)
    assert diff_workbooks(a, b) == []
    assert main([str(a), str(b)]) == 0


def test_changed_cell_is_reported(tmp_path, capsys):
    a = _write(tmp_path / "a.xlsx", 1.25)
    b = _write(tmp_path / "b.xlsx", 1.2500000001)
    assert diff_workbooks(a, b) == ["Abundances!R2C2: 1.25 != 1.2500000001"]
    assert main([str(a), str(b)]) == 1
    assert "Abundances!R2C2" in capsys.readouterr().out
