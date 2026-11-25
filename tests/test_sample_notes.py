from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import openpyxl
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from manic.io.changelog_writer import generate_changelog
from manic.io.compound_reader import Compound
from manic.io.data_exporter import DataExporter
from manic.models import database, session_export
from manic.models.analysis import AnalysisMode
from manic.models.sample_note import get_sample_notes, set_sample_note
from manic.ui.graphs import ClickableChartView, GraphView

from conftest import _make_window
from test_labelled_export_fills import _insert_compound, _insert_eic
from test_unlabelled_compounds import _import_targets
from test_unlabelled_compounds import _insert_eic as _insert_unlabelled_eic

TIME = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
MATRIX = [[0, 2, 10, 2, 0, 0, 0], [0, 1, 4, 1, 0, 0, 0]]
MULTI_LINE = "Co-eluting shoulder.\nBaseline drawn by hand.\n\nSee batch 3."


def _labelled_session() -> None:
    """Zeta is first in the compound list, so list order differs from name order."""
    for name in ("Zeta", "Alpha"):
        _insert_compound(name, 1.0, 100.0)
        for sample in ("S2", "S1"):
            _insert_eic(sample, name, TIME, MATRIX)


def _notes_rows(path) -> list[tuple]:
    book = openpyxl.load_workbook(path)  # formulas kept: a formula would show as one
    assert book.sheetnames[-1] == "Notes"
    return [tuple(cell.value for cell in row) for row in book["Notes"].iter_rows()]


def _export(tmp_path, mode=AnalysisMode.LABELLED, name="out.xlsx"):
    path = tmp_path / name
    assert DataExporter(mode).export_to_excel(str(path))
    return path


def test_a_note_is_replaced_and_blank_text_deletes_it(empty_db):
    set_sample_note("Target", "S1", "  first  ")
    set_sample_note("Target", "S1", "second")
    set_sample_note("Other", "S1", "kept")
    assert get_sample_notes("Target") == {("Target", "S1"): "second"}
    set_sample_note("Target", "S1", " \n ")
    assert get_sample_notes() == {("Other", "S1"): "kept"}


def test_labelled_notes_sheet_lists_notes_in_list_order_as_text(empty_db, tmp_path):
    _labelled_session()
    set_sample_note("Alpha", "S1", "=SUM(A1:A9)")
    set_sample_note("Zeta", "S2", MULTI_LINE)
    set_sample_note("Zeta", "S1", "+1 @home -x")
    set_sample_note("Gone", "S1", "no such compound")

    path = _export(tmp_path)
    rows = _notes_rows(path)
    assert rows == [
        ("Compound", "Sample", "Note"),
        ("Zeta", "S1", "+1 @home -x"),
        ("Zeta", "S2", MULTI_LINE),
        ("Alpha", "S1", "=SUM(A1:A9)"),
    ]
    sheet = openpyxl.load_workbook(path)["Notes"]
    assert {cell.data_type for row in sheet.iter_rows() for cell in row} == {"s"}
    assert sheet["C3"].alignment.wrap_text


def test_notes_never_change_another_sheet(empty_db, tmp_path):
    _labelled_session()

    def other_sheets(path):
        book = openpyxl.load_workbook(path)
        return {
            name: [[cell.value for cell in row] for row in book[name].iter_rows()]
            for name in book.sheetnames[:-1]
        }

    without = _export(tmp_path, name="without.xlsx")
    assert _notes_rows(without) == [("Compound", "Sample", "Note")]
    set_sample_note("Zeta", "S1", "=1+1")
    with_notes = other_sheets(_export(tmp_path, name="with.xlsx"))
    assert with_notes == other_sheets(without)
    assert len(with_notes) == 5


def test_a_note_leaves_the_sheet_with_a_deleted_item_and_returns_on_recovery(empty_db, tmp_path):
    _labelled_session()
    set_sample_note("Zeta", "S1", "on a sample")
    set_sample_note("Alpha", "S2", "on a compound")
    database.soft_delete_sample("S1")
    database.soft_delete_compound("Alpha")
    assert _notes_rows(_export(tmp_path, name="deleted.xlsx")) == [("Compound", "Sample", "Note")]

    database.restore_samples(["S1"])
    database.restore_compounds(["Alpha"])
    assert _notes_rows(_export(tmp_path, name="restored.xlsx"))[1:] == [
        ("Zeta", "S1", "on a sample"),
        ("Alpha", "S2", "on a compound"),
    ]


def test_unlabelled_notes_sheet_is_last_and_lists_the_note(empty_db, tmp_path):
    for name in ("Late", "Early"):
        _import_targets(
            tmp_path, name=name, tR=1.0, lOffset=1.1, rOffset=1.1, QIon=217, QualifierIon1=147
        )
        _insert_unlabelled_eic(
            "S1", name, [0.0, 1.0, 2.0], [[0.0, 10.0, 0.0], [0.0, 4.0, 0.0]], rt_window=1.1
        )
    set_sample_note("Early", "S1", "second in the list")
    set_sample_note("Late", "S1", "first in the list")
    path = _export(tmp_path, AnalysisMode.UNLABELLED)
    assert openpyxl.load_workbook(path).sheetnames == [
        "Raw Values", "Abundances", "Qualifier QC", "Notes"
    ]
    assert _notes_rows(path)[1:] == [
        ("Late", "S1", "first in the list"),
        ("Early", "S1", "second in the list"),
    ]


def test_session_export_and_import_round_trip_notes(empty_db, tmp_path):
    _labelled_session()
    set_sample_note("Zeta", "S1", MULTI_LINE)
    assert session_export.export_session_method(str(tmp_path / "method"))
    folder = tmp_path / "manic_session_export"
    method_path = folder / "method.json"
    exported = json.loads(method_path.read_text(encoding="utf-8"))
    assert exported["sample_notes"] == [
        {"compound_name": "Zeta", "sample_name": "S1", "note": MULTI_LINE}
    ]
    changelog = next(folder.glob("changelog_*.md")).read_text(encoding="utf-8")
    assert "## Sample Notes" in changelog
    assert "| Zeta | S1 | Co-eluting shoulder.<br>Baseline drawn by hand.<br><br>See batch 3. |" in changelog

    set_sample_note("Zeta", "S1", "edited after the export")
    set_sample_note("Alpha", "S2", "added after the export")
    ok, _ = session_export.import_session_overrides(str(method_path))
    assert ok
    assert get_sample_notes() == {("Zeta", "S1"): MULTI_LINE}

    # A session file from before notes existed leaves the notes alone.
    del exported["sample_notes"]
    old_path = folder / "old.json"
    old_path.write_text(json.dumps(exported), encoding="utf-8")
    ok, _ = session_export.import_session_overrides(str(old_path))
    assert ok
    assert get_sample_notes() == {("Zeta", "S1"): MULTI_LINE}


def test_data_export_changelog_lists_notes(empty_db, tmp_path):
    _labelled_session()
    set_sample_note("Zeta", "S1", "a | b\r\nc")
    set_sample_note("Alpha", "S2", "deleted compound note")
    database.soft_delete_compound("Alpha")
    generate_changelog(
        str(tmp_path / "export.xlsx"),
        internal_standard=None,
        use_legacy_integration=False,
        mass_tolerance=0.2,
        min_peak_area_ratio=0.005,
        analysis_mode=AnalysisMode.LABELLED,
    )
    changelog = next(tmp_path.glob("changelog_*.md")).read_text(encoding="utf-8")
    assert "## Sample Notes" in changelog
    assert r"| Zeta | S1 | a \| b<br>c |" in changelog
    assert "deleted compound note" not in changelog


@pytest.mark.parametrize("fast_mode", [True, False])
def test_clear_session_removes_notes(empty_db, fast_mode):
    database.init_db()  # adds the TIC and spectrum tables the clear also empties
    set_sample_note("Zeta", "S1", "gone")
    database.clear_database(fast_mode=fast_mode)
    assert get_sample_notes() == {}


# ---------- the grid: menu, inline editor and chip ----------


def _eic(sample: str, compound: str):
    time = np.linspace(6.9, 7.3, 81)
    peak = np.exp(-0.5 * ((time - 7.09) / 0.02) ** 2)
    return SimpleNamespace(
        sample_name=sample, compound_name=compound, time=time, intensity=np.vstack([1e6 * peak])
    )


@pytest.fixture
def plot_data(monkeypatch):
    monkeypatch.setattr(
        "manic.ui.graphs.get_eics_for_compound",
        lambda compound, samples, use_corrected=False: [_eic(s, compound) for s in samples],
    )
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session",
        lambda name, sample=None: Compound(
            compound_name=name, retention_time=7.09, loffset=0.08, roffset=0.035,
            label_atoms=0, mass0=174.0, baseline_correction=0,
        ),
    )


def _close_popups() -> None:
    while (popup := QApplication.activePopupWidget()) is not None:
        popup.close()


@pytest.fixture
def grid(qapp, plot_data):
    view = GraphView()
    view.resize(900, 600)
    view.show()
    view.plot_compound("Cmp", ["A", "B", "C"], {})
    yield view
    _close_popups()
    view.deleteLater()


def _plots(view: GraphView) -> dict[str, ClickableChartView]:
    return {p.sample_name: p for p in view.findChildren(ClickableChartView) if p.isVisibleTo(view)}


def _context_menu(view: GraphView, sample: str) -> dict:
    QTest.mouseClick(_plots(view)[sample].viewport(), Qt.RightButton)
    return {a.text(): a for a in QApplication.activePopupWidget().actions() if a.isVisible()}


def test_enter_saves_shift_enter_breaks_the_line_and_the_chip_shows_the_note(grid):
    menu = _context_menu(grid, "B")
    assert "Remove Note" not in menu and "Edit Note..." not in menu
    menu["Add Note..."].trigger()
    _close_popups()
    editor = grid.note_editor
    assert editor.isVisible() and grid.rect().contains(editor.geometry())
    assert not editor.remove_button.isVisibleTo(editor)

    QTest.keyClicks(editor.text, "shoulder")
    QTest.keyClick(editor.text, Qt.Key_Return, Qt.ShiftModifier)
    QTest.keyClicks(editor.text, "see batch 3")
    assert editor.isVisible()
    QTest.keyClick(editor.text, Qt.Key_Return)

    assert not editor.isVisible()
    assert get_sample_notes() == {("Cmp", "B"): "shoulder\nsee batch 3"}
    tiles = {name: plot.parent() for name, plot in _plots(grid).items()}
    assert tiles["B"].note_chip.isVisibleTo(grid)
    assert tiles["B"].note_chip.preview() == "shoulder see batch 3"
    assert "shoulder\nsee batch 3" in tiles["B"].note_chip.toolTip()
    assert not tiles["A"].note_chip.isVisibleTo(grid)


def test_chip_click_edits_escape_keeps_the_note_and_empty_text_deletes_it(grid):
    plot = _plots(grid)["A"]
    grid.set_note(plot, "first")
    chip = plot.parent().note_chip
    editor = grid.note_editor

    QTest.mouseClick(chip, Qt.LeftButton)
    assert editor.isVisible() and editor.text.toPlainText() == "first"
    assert editor.remove_button.isVisibleTo(editor)
    QTest.keyClicks(editor.text, " and more")
    QTest.keyClick(editor.text, Qt.Key_Escape)
    assert not editor.isVisible()
    assert get_sample_notes() == {("Cmp", "A"): "first"}

    QTest.mouseClick(chip, Qt.LeftButton)
    editor.text.setPlainText("  \n ")
    QTest.mouseClick(editor.save_button, Qt.LeftButton)
    assert get_sample_notes() == {}
    assert not chip.isVisibleTo(grid)


def test_menu_edits_and_removes_only_the_clicked_plots_note(grid):
    plots = _plots(grid)
    grid.set_note(plots["A"], "note a")
    grid.set_note(plots["B"], "note b")
    grid.select_all_plots()

    menu = _context_menu(grid, "A")
    assert "Add Note..." not in menu
    menu["Edit Note..."].trigger()
    _close_popups()
    assert grid.note_editor.text.toPlainText() == "note a"
    QTest.mouseClick(grid.note_editor.remove_button, Qt.LeftButton)
    assert get_sample_notes() == {("Cmp", "B"): "note b"}

    _context_menu(grid, "B")["Remove Note"].trigger()
    assert get_sample_notes() == {}


def test_notes_follow_the_compound_on_screen(grid):
    grid.set_note(_plots(grid)["A"], "on Cmp")
    grid.edit_note(_plots(grid)["A"])
    grid.note_editor.text.setPlainText("updated before switch")
    grid.plot_compound("Other", ["A", "B"], {})
    assert not grid.note_editor.isVisible()
    assert not _plots(grid)["A"].parent().note_chip.isVisibleTo(grid)
    grid.plot_compound("Cmp", ["A", "B"], {})
    assert _plots(grid)["A"].parent().note() == "updated before switch"

    # Clearing text without clicking Save/Remove does not silently delete on switch.
    grid.edit_note(_plots(grid)["A"])
    grid.note_editor.text.setPlainText("")
    grid.plot_compound("Other", ["A", "B"], {})
    assert get_sample_notes("Cmp") == {("Cmp", "A"): "updated before switch"}

    # Clearing the grid (e.g. unchecking samples or deleting another item) preserves a draft.
    grid.plot_compound("Cmp", ["A", "B"], {})
    grid.edit_note(_plots(grid)["A"])
    grid.note_editor.text.setPlainText("kept on clear")
    grid.clear_all_plots()
    assert get_sample_notes("Cmp") == {("Cmp", "A"): "kept on clear"}


def test_closing_note_editor_does_not_steal_focus_from_sibling_and_escape_from_button_cancels(
    qapp, plot_data
):
    from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

    host = QWidget()
    layout = QVBoxLayout(host)
    sibling = QLineEdit()
    view = GraphView()
    layout.addWidget(sibling)
    layout.addWidget(view)
    host.resize(900, 650)
    host.show()
    try:
        view.plot_compound("Cmp", ["A", "B"], {})
        view.select_samples(["A"])
        view.edit_note(_plots(view)["A"])
        view.note_editor.save_button.setFocus()
        QTest.keyClick(view.note_editor.save_button, Qt.Key_Escape)
        assert not view.note_editor.isVisible()
        assert view.get_selected_samples() == ["A"]

        view.edit_note(_plots(view)["A"])
        qapp.processEvents()
        sibling.setFocus()
        assert QApplication.focusWidget() is sibling
        view.plot_compound("Other", ["A", "B"], {})
        assert QApplication.focusWidget() is sibling
    finally:
        host.close()
        host.deleteLater()


def test_review_menu_notes_one_plot_and_refuses_several(qapp, monkeypatch, plot_data):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    view = window.graph_view
    try:
        view.plot_compound("Cmp", ["A", "B"], {})
        window._sync_review_menu()
        assert not window.note_action.isEnabled()

        view.select_samples(["A"])
        window._sync_review_menu()
        assert window.note_action.isEnabled() and window.note_action.text() == "Add Note..."
        assert not window.remove_note_action.isVisible()
        window.note_action.trigger()
        view.note_editor.text.setPlainText("from the menu")
        view.note_editor.save()
        assert get_sample_notes() == {("Cmp", "A"): "from the menu"}
        window._sync_review_menu()
        assert window.note_action.text() == "Edit Note..."
        assert window.remove_note_action.isVisible()

        view.select_samples(["A", "B"])
        window._sync_review_menu()
        assert not window.note_action.isEnabled()
        assert not window.remove_note_action.isVisible()
        window.remove_note_action.trigger()
        assert get_sample_notes() == {("Cmp", "A"): "from the menu"}

        view.select_samples(["A"])
        window._sync_review_menu()
        window.remove_note_action.trigger()
        assert get_sample_notes() == {}

        view.edit_note(_plots(view)["A"])
        view.note_editor.text.setPlainText("pre-import draft")
        window._refresh_after_session_import()
        assert get_sample_notes() == {}
    finally:
        window.close()
        window.deleteLater()


def test_inspect_sample_shows_each_samples_note(qapp, monkeypatch):
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    set_sample_note("Cmp", "S1", MULTI_LINE)
    dialog = DetailedPlotDialog("Cmp", "S1", samples=["S1", "S2"])
    try:
        assert dialog.note_label.text() == MULTI_LINE
        assert dialog.note_box.isVisibleTo(dialog)
        dialog.step_sample(1)
        assert not dialog.note_box.isVisibleTo(dialog)
        dialog.step_sample(-1)
        assert dialog.note_label.text() == MULTI_LINE
        assert dialog.note_box.isVisibleTo(dialog)
    finally:
        dialog.deleteLater()
