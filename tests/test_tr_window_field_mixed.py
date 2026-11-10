import numpy as np
import pytest

from manic.io.eic_importer import _compress
from manic.models import database
from manic.ui.integration_window_widget import IntegrationWindow


@pytest.fixture
def window(qapp):
    """S1 holds a 0.8 min extract and S2 a 0.3 min one; S2 is selected."""
    time = np.array([4.8, 5.0, 5.2])
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0) "
            "VALUES ('Glucose', 5.0, 0.1, 0.1, 100.0)"
        )
        for sample, rt_window in (("s1", 0.8), ("s2", 0.3)):
            conn.execute(
                "INSERT INTO samples (sample_name, file_name) VALUES (?, ?)",
                (sample, f"/fake/{sample}.cdf"),
            )
            conn.execute(
                "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
                "VALUES (?, 'Glucose', ?, ?, ?)",
                (sample, _compress(time), _compress(np.ones(3)), rt_window),
            )
    widget = IntegrationWindow()
    widget.populate_fields_from_plots("Glucose", ["s2"], ["s1", "s2"])
    widget.populate_tr_window_field("Glucose")
    widget.emitted, widget.messages = [], []
    widget.data_regeneration_requested.connect(lambda *args: widget.emitted.append(args))
    widget._show_message = lambda *args: widget.messages.append(args)
    return widget


def test_field_shows_the_range_of_shown_samples(window):
    assert window.tr_window_edit.text() == "0.3 - 0.8"


def test_update_with_a_range_keeps_each_sample_window(window):
    window.regenerate_button.click()

    assert window.emitted == []
    assert window.messages == [
        (
            "warning",
            "Different tR Windows",
            "The shown samples hold different tR windows. "
            "Type one window to re-extract them all.",
        )
    ]


def test_apply_with_a_range_reextracts_at_the_sample_window(window):
    window.findChild(type(window.tr_window_edit), "tr_input").setText("5.5")

    window.apply_button.click()

    assert window.emitted == [("Glucose", 0.3, ["s2"], 5.5)]
