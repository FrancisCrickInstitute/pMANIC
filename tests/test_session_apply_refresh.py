import zlib

import numpy as np
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QLineEdit

from conftest import _gaussian, _make_window
from manic.io.compound_reader import read_compound_with_session
from manic.models import database

SAMPLES = ["S1", "S2"]


def _seed(compounds):
    time = np.linspace(4.0, 6.0, 401)
    peak = _gaussian(time, 5.0, 0.03, 1e5)
    with database.get_connection() as conn:
        for compound in compounds:
            conn.execute(
                "INSERT INTO compounds (compound_name, retention_time, loffset, "
                "roffset, mass0, label_atoms, deconvolution_level) "
                "VALUES (?, 5.0, 0.1, 0.1, 100.0, 0, 'off')",
                (compound,),
            )
            for sample in SAMPLES:
                conn.execute(
                    "INSERT OR IGNORE INTO samples (sample_name, file_name) "
                    "VALUES (?, ?)",
                    (sample, f"/fake/{sample}.cdf"),
                )
                conn.execute(
                    "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, "
                    "rt_window) VALUES (?, ?, ?, ?, 0.5)",
                    (
                        sample,
                        compound,
                        zlib.compress(time.tobytes()),
                        zlib.compress(peak.tobytes()),
                    ),
                )


def _window(monkeypatch, compounds):
    window = _make_window(monkeypatch)
    window.compound_data_loaded = window.cdf_data_loaded = True
    window.toolbar.update_sample_list(SAMPLES)
    window.toolbar.update_compound_list(compounds, compounds[0])
    return window


def _drain_events():
    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec()


def _apply_tr(window, tr):
    integration = window.toolbar.integration
    integration.findChild(QLineEdit, "tr_input").setText(tr)
    integration.apply_button.click()


def test_apply_then_compound_switch_edits_only_shown_compound(qapp, monkeypatch):
    _seed(["A", "B"])
    window = _window(monkeypatch, ["A", "B"])

    _apply_tr(window, "5.01")
    window.toolbar.update_compound_list(["A", "B"], "B")
    _drain_events()
    _apply_tr(window, "5.02")

    tr = {c: read_compound_with_session(c, "S1").retention_time for c in "AB"}
    assert tr == {"A": 5.01, "B": 5.02}


def test_apply_refreshes_fields_and_charts_once(qapp, monkeypatch):
    _seed(["A"])
    window = _window(monkeypatch, ["A"])
    calls = []
    integration = window.toolbar.integration
    populate = integration.populate_fields_from_plots
    refresh_charts = window._refresh_mode_charts
    monkeypatch.setattr(
        integration,
        "populate_fields_from_plots",
        lambda *a, **k: calls.append("fields") or populate(*a, **k),
    )
    monkeypatch.setattr(
        window,
        "_refresh_mode_charts",
        lambda *a, **k: calls.append("charts") or refresh_charts(*a, **k),
    )

    _apply_tr(window, "5.01")
    _drain_events()

    assert sorted(calls) == ["charts", "fields"]
