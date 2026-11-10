import openpyxl
import pytest
from PySide6.QtWidgets import QDialog

import manic.ui.main_window as main_window_module
from manic.io.eic_importer import regenerate_all_eics_with_mass_tolerance
from manic.models.database import get_connection
from manic.ui.export_options_dialog import ExportOptionsDialog

from conftest import _make_window
from test_restore_after_mass_tolerance_change import _write_cdf


@pytest.mark.parametrize("accept", [False, True], ids=["declined", "accepted"])
def test_export_with_a_stale_sample_asks_before_writing(
    qapp, tmp_path, monkeypatch, accept
):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, mass0, "
            "label_atoms, formula) VALUES ('Pyruvate', 5.0, 100.0, 1, 'C6H12O3NSi')"
        )
        for sample in ("s1", "s2"):
            _write_cdf(tmp_path / f"{sample}.cdf")
            conn.execute(
                "INSERT INTO samples (sample_name, file_name) VALUES (?, ?)",
                (sample, str(tmp_path / f"{sample}.cdf")),
            )
    regenerate_all_eics_with_mass_tolerance(0.2)
    (tmp_path / "s2.cdf").rename(tmp_path / "s2.moved")
    regenerate_all_eics_with_mass_tolerance(0.3)

    out = tmp_path / "out.xlsx"
    window = _make_window(monkeypatch)
    locations = []
    monkeypatch.setattr(ExportOptionsDialog, "exec", lambda d: QDialog.Accepted)
    monkeypatch.setattr(
        main_window_module.QFileDialog,
        "getSaveFileName",
        lambda *a, **k: locations.append(out) or (str(out), ""),
    )
    monkeypatch.setattr(window, "_confirm", lambda *a, **k: accept)
    try:
        window.export_data()
        if window._export_thread is not None:
            assert window._export_thread.wait(30000)
        qapp.processEvents()

        if accept:
            raw = openpyxl.load_workbook(out)["Raw Values"]
            assert [raw["B5"].value, raw["B6"].value] == ["s1", "s2"]
        else:
            assert locations == []
            assert not out.exists()
    finally:
        window.close()
