import sys

import pytest
import numpy as np
import shiboken6
from PySide6.QtWidgets import QDialog, QMessageBox

import manic.ui.main_window as main_window_module
from manic.io.eic_importer import regenerate_all_eics_with_mass_tolerance
from manic.io.sample_reader import list_stale_samples
from manic.models.database import get_connection
from manic.processors.eic_processing import get_eics_for_compound
from manic.ui.export_options_dialog import ExportOptionsDialog

from conftest import _make_window
from test_add_compound_selects_after_extraction import _process_events_until
from test_restore_after_mass_tolerance_change import _write_cdf


def _eic_rows(sample):
    with get_connection() as conn:
        return conn.execute(
            "SELECT compound_name, x_axis, y_axis FROM eic WHERE sample_name = ?",
            (sample,),
        ).fetchall()


def _rebuild_from_export_warning(qapp, tmp_path, monkeypatch):
    """s2 misses the change to 0.3 Da; returns the window and the texts of later boxes."""
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

    window = _make_window(monkeypatch)
    window.apply_mass_tolerance(0.3)
    monkeypatch.setattr(ExportOptionsDialog, "exec", lambda d: QDialog.Accepted)
    monkeypatch.setattr(
        main_window_module.QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("asked where to export")),
    )
    later = []

    def click_rebuild(box):
        for button in box.buttons():
            if button.text() == "Rebuild Stale Samples":
                button.click()
                return
        later.append(box.text())
        return QMessageBox.Cancel

    monkeypatch.setattr(QMessageBox, "exec", click_rebuild)
    return window, later


def _run(qapp, window):
    window.export_data()
    thread = getattr(window, "_mass_tol_thread", None)
    if thread is not None:
        _process_events_until(
            lambda: not shiboken6.isValid(thread) or thread.isFinished()
        )
    qapp.processEvents()


def test_rebuild_from_the_export_warning_rebuilds_only_the_stale_sample(
    qapp, tmp_path, monkeypatch
):
    window, later = _rebuild_from_export_warning(qapp, tmp_path, monkeypatch)
    (tmp_path / "s2.moved").rename(tmp_path / "s2.cdf")
    # A full reload would fail on s1 now and mark it stale.
    (tmp_path / "s1.cdf").write_bytes(b"")
    s1_before = _eic_rows("s1")
    try:
        _run(qapp, window)

        m0 = {
            eic.sample_name: np.round(eic.intensity[0], 4).tolist()
            for eic in get_eics_for_compound("Pyruvate", ["s2"])
        }
        assert m0 == {"s2": [11.0, 11.0, 11.0]}
        assert _eic_rows("s1") == s1_before
        assert list_stale_samples() == []
        assert window.mass_tolerance == 0.3
        assert later == []
    finally:
        window.close()


def test_rebuild_with_the_cdf_still_missing_keeps_the_sample_stale(
    qapp, tmp_path, monkeypatch
):
    window, later = _rebuild_from_export_warning(qapp, tmp_path, monkeypatch)
    s2_before = _eic_rows("s2")
    try:
        _run(qapp, window)

        assert list_stale_samples() == ["s2"]
        assert _eic_rows("s2") == s2_before
        assert len(later) == 1 and later[0].endswith(": s2")
    finally:
        window.close()


@pytest.mark.parametrize("earlier_change", [True, False])
def test_failed_rebuild_keeps_the_mass_tolerance(qapp, tmp_path, monkeypatch, earlier_change):
    window, later = _rebuild_from_export_warning(qapp, tmp_path, monkeypatch)
    if not earlier_change:
        window.close()
        window = _make_window(monkeypatch)
        regenerate_all_eics_with_mass_tolerance(0.2, sample_names=["s1"])
    before = window.mass_tolerance
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda typ, val, tb: errors.append(str(val)))

    _run(qapp, window)

    assert window.mass_tolerance == before
    assert errors == []
    assert list_stale_samples() == ["s2"]
    window.close()
