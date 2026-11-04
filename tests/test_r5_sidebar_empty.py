from PySide6.QtCore import Qt

from manic.models import database

from conftest import _make_window


def _fake_plot(window):
    def plot_compound(compound_name, samples, validation_data=None, *, identity=None):
        view = window.graph_view
        view._current_compound = compound_name
        view._current_samples = list(samples)

    return plot_compound


def test_unchecking_every_sample_empties_the_workspace(qapp, empty_db, monkeypatch):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES ('Alanine', 1.0, 0.1, 0.1, 217.0, 0)"
        )
    window = _make_window(monkeypatch)
    monkeypatch.setattr(window.graph_view, "plot_compound", _fake_plot(window))
    monkeypatch.setattr(window, "_peak_verdicts", lambda *a: {})
    monkeypatch.setattr(window, "_identity_snapshot", lambda *a: (None, None))
    monkeypatch.setattr(window, "_refresh_mode_charts", lambda *a, **k: None)
    try:
        window.cdf_data_loaded = True
        window.toolbar.update_compound_list(["Alanine"], "Alanine")
        window.toolbar.update_sample_list(["S1", "S2", "S3"])
        assert window.workspace.currentWidget() is window.graph_view
        assert window.graph_view.get_current_samples() == ["S1", "S2", "S3"]

        for item in window.toolbar.sample_list._real_items():
            item.setCheckState(Qt.CheckState.Unchecked)

        integration = window.toolbar.integration
        assert window.workspace.currentWidget() is window.no_samples_panel
        assert window.graph_view.get_current_samples() == []
        assert window.toolbar.samples_section.summary.full_text() == "0 of 3 shown"
        assert integration.scope_label.text() == "No samples shown. Nothing to apply to."
        assert integration.apply_button.text() == "Apply"
        assert not integration.apply_button.isEnabled()
        assert not integration.regenerate_button.isEnabled()
        assert window.selection_status_label.text() == "No samples shown"

        window.show_all_samples_button.click()
        assert window.workspace.currentWidget() is window.graph_view
        assert window.graph_view.get_current_samples() == ["S1", "S2", "S3"]
        assert integration.apply_button.text() == "Apply to 3 samples"
        assert integration.apply_button.isEnabled()
    finally:
        window.close()
