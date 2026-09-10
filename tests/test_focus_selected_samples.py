import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from manic.models import database
from manic.models.analysis import AnalysisContext, AnalysisMode
from manic.ui.left_toolbar import Toolbar
from manic.ui.main_window import MainWindow

SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def empty_db(tmp_path, monkeypatch):
    db_path = tmp_path / "focus.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    with database.get_connection() as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return db_path


class FakeSelectable:
    def __init__(self, sample: str):
        self.sample_name = sample
        self.compound_name = "Alanine"
        self.is_selected = False

    def set_selected(self, selected: bool) -> None:
        self.is_selected = selected


def _make_window(monkeypatch) -> MainWindow:
    monkeypatch.setattr(MainWindow, "_check_for_updates", lambda self: None)
    return MainWindow(AnalysisContext(AnalysisMode.LABELLED))


def _install_plot_stub(window: MainWindow) -> None:
    def stub(compound_name, samples):
        if not compound_name or compound_name.startswith("- No"):
            return
        if not samples or any(sample.startswith("- No") for sample in samples):
            return
        view = window.graph_view
        view._current_compound = compound_name
        view._current_samples = list(samples)
        view._selected_plots.clear()
        view._current_plots = [FakeSelectable(name) for name in samples]
        window.toolbar.integration.populate_fields_from_plots(
            compound_name, [], samples
        )

    window.on_plot_button = stub


def test_set_selected_samples_emits_samples_selected_once(qapp):
    toolbar = Toolbar()
    toolbar.update_sample_list(["S1", "S2", "S3"])
    seen: list[list[str]] = []
    toolbar.samples_selected.connect(seen.append)
    toolbar.set_selected_samples(["S2", "S1", "missing"])
    assert seen == [["S1", "S2"]]
    toolbar.set_selected_samples(["nope"])
    assert seen == [["S1", "S2"]]
    toolbar.deleteLater()


def test_focus_selected_then_show_all(qapp, empty_db, monkeypatch):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES ('Alanine', 1.0, 0.1, 0.1, 217.0, 0)"
        )
    window = _make_window(monkeypatch)
    _install_plot_stub(window)
    try:
        window.toolbar.update_compound_list(["Alanine"])
        window.toolbar.update_sample_list(["S1", "S2", "S3"])
        window.graph_view.select_samples(["S1", "S2"])
        window.graph_view.focus_selected_requested.emit(["S1", "S2"])
        assert window.toolbar.get_selected_samples() == ["S1", "S2"]
        assert window.graph_view.get_current_samples() == ["S1", "S2"]
        assert window.graph_view.get_selected_samples() == ["S1", "S2"]
        assert window.toolbar.integration.title() == "Selected Plots: 2 samples"

        window.graph_view.show_all_samples_requested.emit()
        assert window.toolbar.get_selected_samples() == ["S1", "S2", "S3"]
        assert window.graph_view.get_current_samples() == ["S1", "S2", "S3"]
        assert window.graph_view.get_selected_samples() == []
        assert window.toolbar.integration.title() == "Selected Plots: All"
    finally:
        window.close()
