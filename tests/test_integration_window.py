import pytest

from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.ui.integration_window_widget import IntegrationWindow


def test_apply_window_states_that_it_re_extracts_every_shown_sample(qapp, monkeypatch):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES ('Alanine', 1.0, 0.1, 0.1, 217.0, 0)"
        )
    integration = IntegrationWindow(AnalysisMode.LABELLED)
    monkeypatch.setattr(
        integration, "_show_message", lambda *a, **k: pytest.fail(f"message box: {a}")
    )
    requests = []
    integration.data_regeneration_requested.connect(lambda *args: requests.append(args))
    shown = ["S1", "S2", "S3"]
    try:
        integration.populate_fields_from_plots("Alanine", [], shown)
        assert integration.window_scope_label.text() == "Re-extracts all 3 shown samples"

        integration.populate_fields_from_plots("Alanine", ["S2"], shown)
        assert integration.scope_label.text() == "Applies to S2"
        assert integration.apply_button.text() == "Apply"
        assert integration.window_scope_label.text() == "Re-extracts all 3 shown samples"

        integration.tr_window_edit.setText("0.5")
        integration.regenerate_button.click()
        assert requests == [("Alanine", 0.5, ["S1", "S2", "S3"], 1.0)]
    finally:
        integration.deleteLater()
