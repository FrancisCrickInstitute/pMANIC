import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit

from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.ui.integration_window_widget import IntegrationWindow


def _caption(label) -> str:
    """A caption as it reads: its non-breaking spaces are spaces."""
    return label.text().replace("\u00a0", " ")


def test_an_unapplied_edit_comes_back_with_its_compound_and_says_so(qapp, monkeypatch):
    with database.get_connection() as conn:
        for name, offset in (("Alanine", 0.1), ("Glycine", 0.2)):
            conn.execute(
                "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
                "mass0, label_atoms) VALUES (?, 1.0, ?, 0.1, 217.0, 0)",
                (name, offset),
            )
        conn.execute("INSERT INTO samples (sample_name) VALUES ('S2')")
    integration = IntegrationWindow(AnalysisMode.LABELLED)
    monkeypatch.setattr(
        integration, "_show_message", lambda *a, **k: pytest.fail(f"message box: {a}")
    )
    monkeypatch.setattr(
        "manic.ui.integration_window_widget.samples_needing_reextraction",
        lambda *a: [],
    )
    left = integration.findChild(QLineEdit, "lo_input")
    shown = ["S1", "S2"]
    try:
        integration.populate_fields_from_plots("Alanine", ["S2"], shown)
        assert integration.apply_button.property("variant") is None
        left.selectAll()
        QTest.keyClicks(left, "0.05")
        assert _caption(integration.scope_label) == "S2 · not applied"
        assert integration.apply_button.property("variant") == "primary"

        integration.populate_fields_from_plots("Glycine", ["S2"], shown)
        assert (left.text(), _caption(integration.scope_label)) == ("0.2", "Applies to S2")

        integration.populate_fields_from_plots("Alanine", ["S2"], shown)
        assert (left.text(), _caption(integration.scope_label)) == (
            "0.05",
            "S2 · not applied",
        )

        # With no selection the edit goes to every shown sample, and says so the same way.
        integration.populate_fields_from_plots("Alanine", [], shown)
        left.selectAll()
        QTest.keyClicks(left, "0.07")
        assert _caption(integration.scope_label) == "All 2 shown · not applied"

        integration.populate_fields_from_plots("Alanine", ["S2"], shown)
        # Applied, the app shows the stored window again: the same value, no longer a draft.
        integration.apply_button.click()
        integration.populate_fields_from_plots("Alanine", ["S2"], shown)
        assert (left.text(), _caption(integration.scope_label)) == ("0.05", "Applies to S2")
    finally:
        integration.deleteLater()


def test_an_unapplied_edit_stays_when_the_same_samples_are_picked_in_another_order(
    qapp, monkeypatch
):
    import numpy as np
    from types import SimpleNamespace

    from conftest import _make_window
    from manic.io.compound_reader import Compound
    from manic.ui.main_window import MainWindow

    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES ('Cmp', 1.0, 0.1, 0.1, 217.0, 0)"
        )
    time = np.linspace(0.8, 1.2, 81)

    def eics(compound, samples, **_kwargs):
        return [
            SimpleNamespace(sample_name=s, compound_name=compound, time=time, intensity=np.ones((1, 81)))
            for s in samples
        ]

    compound = Compound(
        compound_name="Cmp", retention_time=1.0, loffset=0.1, roffset=0.1, mass0=217.0, label_atoms=0
    )
    monkeypatch.setattr("manic.ui.graphs.get_eics_for_compound", eics)
    monkeypatch.setattr("manic.ui.graphs.read_compound_with_session", lambda *_a: compound)
    monkeypatch.setattr("manic.ui.integration_window_widget.get_eics_for_compound", eics)
    monkeypatch.setattr(MainWindow, "_refresh_mode_charts", lambda *_a, **_k: None)
    window = _make_window(monkeypatch)
    try:
        window.resize(1500, 1000)
        window.compound_data_loaded = window.cdf_data_loaded = True
        window.toolbar.update_label_colours(True, True)
        window.toolbar.update_compound_list(["Cmp"])
        window.toolbar.update_sample_list([f"S{i}" for i in range(4)])
        window.show()
        view = window.graph_view
        for plot in reversed(view._current_plots):
            QTest.mouseClick(plot.viewport(), Qt.LeftButton)
        left = window.toolbar.integration.findChild(QLineEdit, "lo_input")
        left.selectAll()
        QTest.keyClicks(left, "0.05")
        view.setFocus()
        QTest.keyClick(view, Qt.Key_A, Qt.ControlModifier)
        assert left.text() == "0.05"
    finally:
        window.close()
