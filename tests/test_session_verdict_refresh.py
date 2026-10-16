import zlib

import numpy as np
from PySide6.QtWidgets import QMessageBox

from manic.models import database
from manic.models.session_activity import SessionActivityService

from conftest import _gaussian, _make_window

TIME = np.linspace(4.0, 6.0, 401)
SAMPLES = ["S1", "S2"]


def _seed(target_rt: float) -> None:
    with database.get_connection() as conn:
        for name, rt in (("IS", 5.0), ("T", target_rt)):
            conn.execute(
                "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, "
                "label_atoms, int_std_amount) VALUES (?, ?, 0.1, 0.1, 100.0, 0, 1.0)",
                (name, rt),
            )
        for sample in SAMPLES:
            conn.execute(
                "INSERT INTO samples (sample_name, file_name) VALUES (?, ?)",
                (sample, f"/fake/{sample}.cdf"),
            )
            for name, height in (("IS", 1e5), ("T", 1e4)):
                conn.execute(
                    "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
                    "VALUES (?, ?, ?, ?, 0.5)",
                    (
                        sample,
                        name,
                        zlib.compress(TIME.tobytes()),
                        zlib.compress(_gaussian(TIME, 5.0, 0.03, height).tobytes()),
                    ),
                )


def _window(monkeypatch):
    window = _make_window(monkeypatch)
    window.compound_data_loaded = window.cdf_data_loaded = True
    window.toolbar.update_sample_list(SAMPLES)
    window.toolbar.update_compound_list(["IS", "T"], "T")
    window.toolbar.on_internal_standard_selected("IS")
    return window


def _tile_verdicts(window) -> dict[str, str]:
    return {
        plot.sample_name: plot.parent().verdict.value
        for plot in window.graph_view._current_plots
    }


def _navigate_back(window) -> None:
    window.toolbar.update_compound_list(["IS", "T"], "IS")
    window.toolbar.update_compound_list(["IS", "T"], "T")


def test_reset_paints_verdicts_for_the_default_window(qapp, monkeypatch):
    _seed(target_rt=5.7)
    SessionActivityService.update_session_data("T", SAMPLES, 5.0, 0.1, 0.1)
    window = _window(monkeypatch)
    assert _tile_verdicts(window) == {"S1": "pass", "S2": "pass"}

    integration = window.toolbar.integration
    monkeypatch.setattr(integration, "_show_message", lambda *_a: QMessageBox.Yes)
    integration.restore_button.click()

    assert _tile_verdicts(window) == {"S1": "fail", "S2": "fail"}
    _navigate_back(window)
    assert _tile_verdicts(window) == {"S1": "fail", "S2": "fail"}
