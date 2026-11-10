import logging
from types import SimpleNamespace

import numpy as np
from PySide6.QtWidgets import QLineEdit, QMessageBox

from conftest import _make_window
from manic.models import database
from manic.ui.main_window import MainWindow

FIELDS = ["lo_input", "tr_input", "ro_input"]


def test_deleting_the_shown_compound_does_not_reload_it(qapp, monkeypatch, caplog):
    with database.get_connection() as conn:
        for name, offset in (("Alanine", 0.1), ("Glycine", 0.2)):
            conn.execute(
                "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
                "mass0, label_atoms) VALUES (?, 1.0, ?, 0.1, 217.0, 0)",
                (name, offset),
            )
        for sample in ("S1", "S2"):
            conn.execute("INSERT INTO samples (sample_name) VALUES (?)", (sample,))
    time = np.linspace(0.8, 1.2, 81)

    def eics(compound, samples, **_kwargs):
        return [
            SimpleNamespace(
                sample_name=s, compound_name=compound, time=time, intensity=np.ones((1, 81))
            )
            for s in samples
        ]

    monkeypatch.setattr("manic.ui.graphs.get_eics_for_compound", eics)
    monkeypatch.setattr("manic.ui.integration_window_widget.get_eics_for_compound", eics)
    monkeypatch.setattr(MainWindow, "_refresh_mode_charts", lambda *_a, **_k: None)
    monkeypatch.setattr(QMessageBox, "exec", lambda _self: QMessageBox.StandardButton.Yes)
    window = _make_window(monkeypatch)
    compounds = window.toolbar.compound_list
    integration = window.toolbar.integration
    try:
        window.compound_data_loaded = window.cdf_data_loaded = True
        window.toolbar.update_sample_list(["S1", "S2"])
        window.toolbar.update_compound_list(["Alanine", "Glycine"], "Alanine")
        assert window.graph_view.get_current_compound() == "Alanine"

        caplog.set_level(logging.ERROR)
        compounds._confirm_delete_compound("Alanine")

        assert "Compound not found for Alanine" not in caplog.text
        assert window.graph_view.get_current_compound() == "Glycine"
        assert [integration.findChild(QLineEdit, n).text() for n in FIELDS] == [
            "0.2",
            "1",
            "0.1",
        ]
    finally:
        window.close()
