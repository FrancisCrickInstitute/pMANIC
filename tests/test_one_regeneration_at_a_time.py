import json
import threading
import time
import zlib
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest
from netCDF4 import Dataset
from PySide6.QtCore import QCoreApplication, Qt, QThread
from PySide6.QtWidgets import QDialog, QLineEdit

import manic.ui.add_compound_dialog as add_compound_dialog
import manic.ui.main_window as main_window_module
import manic.utils.workers as workers
from manic.io.compounds_import import CompoundRow
from manic.models import database
from manic.ui.settings_window import ExtractionPage

from conftest import _gaussian, _make_window
from test_mass_tolerance_record import _import


def _write_cdf(path):
    minutes = np.arange(4.0, 8.0, 1 / 60)
    intensity = _gaussian(minutes, 7.0, 0.03, 1e5)
    with Dataset(path, "w") as cdf:
        cdf.createDimension("scan_number", minutes.size)
        cdf.createDimension("point_number", minutes.size)
        variables = {
            "scan_acquisition_time": ("scan_number", minutes * 60),
            "scan_index": ("scan_number", np.arange(minutes.size, dtype=np.int32)),
            "point_count": ("scan_number", np.ones(minutes.size, dtype=np.int32)),
            "total_intensity": ("scan_number", intensity),
            "mass_values": ("point_number", np.full(minutes.size, 100.0)),
            "intensity_values": ("point_number", intensity),
        }
        for name, (dimension, values) in variables.items():
            cdf.createVariable(name, values.dtype, (dimension,))[:] = values


def _seed(tmp_path):
    _write_cdf(tmp_path / "S1.cdf")
    stored_time = np.linspace(4.0, 6.0, 121)
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO samples (sample_name, file_name) VALUES ('S1', ?)",
            (str(tmp_path / "S1.cdf"),),
        )
        for compound in ("A", "B"):
            conn.execute(
                "INSERT INTO compounds (compound_name, retention_time, loffset, "
                "roffset, mass0, label_atoms) VALUES (?, 5.0, 0.1, 0.1, 100.0, 0)",
                (compound,),
            )
            conn.execute(
                "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, "
                "rt_window) VALUES ('S1', ?, ?, ?, 1.0)",
                (
                    compound,
                    zlib.compress(stored_time.tobytes()),
                    zlib.compress(np.zeros_like(stored_time).tobytes()),
                ),
            )


def _apply_tr(window, compound, tr):
    window.toolbar.update_compound_list(["A", "B"], compound)
    integration = window.toolbar.integration
    integration.findChild(QLineEdit, "tr_input").setText(tr)
    integration.apply_button.click()


def _apply(window, tmp_path, monkeypatch, started):
    _apply_tr(window, "B", "7.0")


def _apply_window(window, tmp_path, monkeypatch, started):
    window.toolbar.integration.regenerate_button.click()


def _add_compound(window, tmp_path, monkeypatch, started):
    dialog = SimpleNamespace(
        exec=lambda: QDialog.Accepted,
        record=CompoundRow(compound_name="C", retention_time=7.0, mass0=100.0),
    )
    monkeypatch.setattr(
        add_compound_dialog, "AddCompoundDialog", lambda *a, **k: dialog
    )
    window.show_add_compound_dialog()


def _mass_tolerance(window, tmp_path, monkeypatch, started):
    window.open_settings_window()
    settings = window.settings_window
    [item] = settings.page_list.findItems("Extraction", Qt.MatchExactly)
    settings.page_list.setCurrentItem(item)
    settings.findChild(ExtractionPage).spin.setValue(0.35)
    settings.save_button.click()


def _session_import(window, tmp_path, monkeypatch, started):
    session = tmp_path / "session.json"
    session.write_text(json.dumps({"mass_tolerance": 0.5}))
    started.extend(_import(monkeypatch, window, session))


def _export(window, tmp_path, monkeypatch, started):
    monkeypatch.setattr(
        main_window_module,
        "ExportOptionsDialog",
        lambda *a, **k: started.append(("export",)) or mock.Mock(exec=lambda: 0),
    )
    window.export_data()


@pytest.mark.parametrize(
    "second",
    [_apply, _apply_window, _add_compound, _mass_tolerance, _session_import, _export],
    ids=lambda f: f.__name__.strip("_"),
)
def test_second_regeneration_is_refused_while_one_runs(
    qapp, empty_db, tmp_path, monkeypatch, second
):
    _seed(tmp_path)
    release = threading.Event()
    started = []
    regenerate = workers.regenerate_compound_eics

    def held_regenerate(**kwargs):
        started.append(("regenerate", kwargs["compound_name"]))
        release.wait(10)
        return regenerate(**kwargs)

    monkeypatch.setattr(workers, "regenerate_compound_eics", held_regenerate)
    monkeypatch.setattr(
        workers,
        "regenerate_all_eics_with_mass_tolerance",
        lambda **kwargs: started.append(("reload", kwargs["mass_tol"])) or (0, []),
    )
    window = _make_window(monkeypatch)
    titles = []
    monkeypatch.setattr(
        window,
        "_create_message_box",
        lambda kind, title, *a, **k: titles.append(title) or mock.Mock(),
    )
    window.compound_data_loaded = window.cdf_data_loaded = True
    window._update_menu_states()
    window.toolbar.update_sample_list(["S1"])

    def spin_until(condition, seconds=10):
        deadline = time.monotonic() + seconds
        while not condition() and time.monotonic() < deadline:
            QCoreApplication.processEvents()

    _apply_tr(window, "A", "7.0")
    spin_until(lambda: started)
    window.regen_progress_dialog.close()  # does not stop the worker
    try:
        second(window, tmp_path, monkeypatch, started)
        spin_until(lambda: len(started) > 1, seconds=0.5)

        assert started == [("regenerate", "A")]
        assert titles == ["Operation in progress"]
    finally:
        release.set()
        spin_until(
            lambda: not any(t.isRunning() for t in window.findChildren(QThread))
        )
    spin_until(lambda: window.toolbar.integration._pending_session_update is None)

    with database.get_connection() as conn:
        session = conn.execute(
            "SELECT compound_name, sample_name, retention_time FROM session_activity"
        ).fetchall()
        compounds = conn.execute(
            "SELECT compound_name FROM compounds ORDER BY compound_name"
        ).fetchall()
        x_axis = conn.execute(
            "SELECT x_axis FROM eic WHERE compound_name = 'A' AND deleted = 0"
        ).fetchone()["x_axis"]
    new_time = np.frombuffer(zlib.decompress(x_axis), dtype=np.float64)
    assert [tuple(row) for row in session] == [("A", "S1", 7.0)]
    assert [row[0] for row in compounds] == ["A", "B"]
    assert new_time.min() < 7.0 < new_time.max()
    assert window.toolbar.integration._data_window_bounds[("A", "S1")] == (
        new_time.min(),
        new_time.max(),
    )
    assert window.mass_tolerance == 0.2
    if window.settings_window is not None:
        assert window.settings_window.findChild(ExtractionPage).spin.value() == 0.2
        window.settings_window.close()
    window.close()
