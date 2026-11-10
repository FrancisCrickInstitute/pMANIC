import time
import zlib
from unittest import mock

import numpy as np
import pytest
from netCDF4 import Dataset
from PySide6.QtCore import QCoreApplication, Qt

import manic.ui.main_window as main_window_module
from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.ui.settings_window import ExtractionPage

from conftest import _make_window


def _raise_on_start(*args, **kwargs):
    raise RuntimeError("no threads left")


def _write_cdf(path):
    with Dataset(path, "w") as cdf:
        cdf.createDimension("scan_number", 3)
        cdf.createDimension("point_number", 6)
        variables = {
            "scan_acquisition_time": ("scan_number", [294.0, 300.0, 306.0]),
            "scan_index": ("scan_number", [0, 2, 4]),
            "point_count": ("scan_number", [2, 2, 2]),
            "total_intensity": ("scan_number", [20.0, 20.0, 20.0]),
            "mass_values": ("point_number", [100.0] * 6),
            "intensity_values": ("point_number", [10.0] * 6),
        }
        for name, (dimension, values) in variables.items():
            cdf.createVariable(name, np.asarray(values).dtype, (dimension,))[:] = values


def _wait_for_reload(window, messages):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not (
        messages and window._running_background_thread() is None
    ):
        QCoreApplication.processEvents()


def _samples(tmp_path, readable):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES ('Alanine', 5.0, 0.2, 0.2, 100.0, 0)"
        )
        conn.execute(
            "INSERT INTO samples (sample_name, file_name) VALUES ('S1', ?)",
            (str(tmp_path / "moved.cdf"),),
        )
        if readable:
            _write_cdf(tmp_path / "S2.cdf")
            conn.execute(
                "INSERT INTO samples (sample_name, file_name) VALUES ('S2', ?)",
                (str(tmp_path / "S2.cdf"),),
            )


@pytest.mark.parametrize(
    "failure, messages_shown, stored_tolerance",
    [
        ("no samples", ["critical"], 0.2),
        ("start raises", ["critical"], 0.2),
        ("no CDF readable", ["critical"], 0.2),
        ("one CDF readable", ["warning"], 0.35),
    ],
)
def test_stored_mass_tolerance_after_a_failed_reload(
    qapp, empty_db, tmp_path, monkeypatch, failure, messages_shown, stored_tolerance
):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    messages = []
    monkeypatch.setattr(
        window,
        "_create_message_box",
        lambda *args: messages.append(args[0]) or mock.Mock(),
    )
    if failure == "start raises":
        monkeypatch.setattr(main_window_module, "MassToleranceReloadWorker", _raise_on_start)
    if failure in ("no CDF readable", "one CDF readable"):
        _samples(tmp_path, readable=failure == "one CDF readable")
    window.cdf_data_loaded = True
    window.open_settings_window()
    settings = window.settings_window
    [item] = settings.page_list.findItems("Extraction", Qt.MatchExactly)
    settings.page_list.setCurrentItem(item)
    page = settings.findChild(ExtractionPage)

    page.spin.setValue(0.35)
    settings.save_button.click()
    _wait_for_reload(window, messages)

    assert messages == messages_shown
    assert window.mass_tolerance == stored_tolerance
    assert page.spin.value() == stored_tolerance
    settings.close()
    window.close()


def test_reload_that_stops_after_rebuilding_a_sample_keeps_the_new_tolerance(
    qapp, empty_db, tmp_path, monkeypatch
):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    messages = []
    monkeypatch.setattr(
        window,
        "_create_message_box",
        lambda *args: messages.append(args[0]) or mock.Mock(),
    )
    rebuilt = tmp_path / "S1.cdf"
    _write_cdf(rebuilt)
    with Dataset(rebuilt, "a") as cdf:
        cdf["mass_values"][:] = [100.75] * 6  # matched by 0.35 Da, not by 0.2 Da
    locked = tmp_path / "locked"
    locked.mkdir()
    _write_cdf(locked / "S2.cdf")
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, mass0, label_atoms) "
            "VALUES ('Alanine', 5.0, 100.0, 0)"
        )
        conn.execute(
            "INSERT INTO samples (sample_name, file_name) VALUES ('S1', ?), ('S2', ?)",
            (str(rebuilt), str(locked / "S2.cdf")),
        )
    window.cdf_data_loaded = True
    locked.chmod(0)
    try:
        window.apply_mass_tolerance(0.35)
        _wait_for_reload(window, messages)
    finally:
        locked.chmod(0o700)

    with database.get_connection() as conn:
        [row] = conn.execute("SELECT y_axis FROM eic WHERE sample_name = 'S1'").fetchall()
    assert np.frombuffer(zlib.decompress(row["y_axis"])).tolist() == [20.0, 20.0, 20.0]
    assert messages == ["critical"]
    assert window.mass_tolerance == 0.35
    window.close()
