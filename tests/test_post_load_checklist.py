import sys
from pathlib import Path
from unittest import mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTableWidget,
)

from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.models.mm_file_check import MmFileStatus
from manic.ui.main_window import MainWindow
from manic.ui.post_load_checklist_dialog import PostLoadChecklistDialog
from manic.ui.standard_chooser import StandardChooser

from conftest import _make_window

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

LONG_REPORT = [
    MmFileStatus(f"Compound {i}", "*_MM_01*,*_MM_02*", ("Std_MM_01", "Std_MM_02"))
    for i in range(95)
]


def _insert_compound(name: str, mm_files: str | None = None) -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms, mm_files) VALUES (?, 1.0, 0.1, 0.1, 217.0, 0, ?)",
            (name, mm_files),
        )


def _insert_sample(name: str) -> None:
    with database.get_connection() as conn:
        conn.execute("INSERT INTO samples (sample_name) VALUES (?)", (name,))


def _button(dialog: PostLoadChecklistDialog, text: str) -> QPushButton:
    return next(b for b in dialog.buttons.buttons() if b.text() == text)


def _choose_standard(dialog: PostLoadChecklistDialog, typed: str) -> None:
    dialog.standard_picker.showPopup()
    chooser = dialog.standard_picker.findChildren(StandardChooser)[-1]
    QTest.keyClicks(chooser.filter, typed)
    QTest.keyClick(chooser.filter, Qt.Key_Return)


def _standard_shown(window: MainWindow) -> str:
    return window.toolbar.standard.findChild(QLabel, "statusValue").text()


def _close_window(window: MainWindow) -> None:
    if window._post_load_checklist is not None:
        window._post_load_checklist.close()
    if window.documentation_window is not None:
        window.documentation_window.close()
    window.close()


def test_dialog_preselects_current_internal_standard(qapp):
    report = [MmFileStatus("Alanine", None, ())]
    dialog = PostLoadChecklistDialog(
        ["Alanine", "Norvaline"], "Norvaline", report, None
    )
    assert dialog.standard_picker.currentText() == "Norvaline"
    assert dialog.selected_internal_standard() == "Norvaline"
    dialog.close()


def test_dialog_table_sorts_problems_first_and_warns(qapp):
    report = [
        MmFileStatus("Has", "*MM*", ("A", "B", "C", "D")),
        MmFileStatus("None", None, ()),
        MmFileStatus("Miss", "*ZZ*", ()),
    ]
    dialog = PostLoadChecklistDialog(["Has", "None", "Miss"], None, report, None)
    table = dialog.findChild(QTableWidget, "mmFileTable")
    assert table.rowCount() == 3
    assert [table.item(row, 0).text() for row in range(3)] == [
        "None",
        "Miss",
        "Has",
    ]
    assert table.item(0, 1).text() == "Not set"
    assert table.item(0, 2).text() == "No pattern"
    assert table.item(1, 1).text() == "*ZZ*"
    assert table.item(1, 2).text() == "No files matched"
    assert table.item(2, 1).text() == "*MM*"
    assert table.item(2, 2).text() == "4 files: A, B, C"
    filled = [table.item(row, 2).background().style() != Qt.NoBrush for row in range(3)]
    assert filled == [True, True, False]
    dialog.close()


def test_apply_sets_internal_standard_on_toolbar(qapp, empty_db, monkeypatch):
    _insert_compound("Alanine")
    _insert_compound("Norvaline")
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        window.toolbar.update_compound_list(["Alanine", "Norvaline"])
        window.show_post_load_checklist()
        dialog = window.findChild(PostLoadChecklistDialog)
        _choose_standard(dialog, "norv")
        _button(dialog, "Apply").click()
        assert window.toolbar.get_internal_standard() == "Norvaline"
        assert _standard_shown(window) == "Norvaline"
    finally:
        _close_window(window)


def test_continue_without_changes_leaves_internal_standard_unchanged(qapp, empty_db, monkeypatch):
    _insert_compound("Alanine")
    _insert_compound("Norvaline")
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        window.toolbar.update_compound_list(["Alanine", "Norvaline"])
        window.toolbar.on_internal_standard_selected("Alanine")
        window.show_post_load_checklist()
        dialog = window.findChild(PostLoadChecklistDialog)
        _choose_standard(dialog, "norv")
        _button(dialog, "Continue without changes").click()
        assert window.toolbar.get_internal_standard() == "Alanine"
        assert _standard_shown(window) == "Alanine"
    finally:
        _close_window(window)


# 680x640 is the dialog capped on a 150% 1280x800 laptop; 680x540 on an 800x600 screen.


def test_import_ok_opens_checklist_dialog(qapp, empty_db, monkeypatch):
    _insert_compound("Alanine")
    _insert_compound("Citrate", "*MM*")
    _insert_sample("S1_MM")
    _insert_sample("S2")
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    window.progress_dialog = mock.Mock()
    monkeypatch.setattr(window, "on_plot_button", lambda *args, **kwargs: None)
    try:
        window.compound_data_loaded = True
        window._import_ok(2)
        dialog = window._post_load_checklist
        assert dialog is not None
        assert dialog.objectName() == "postLoadChecklistDialog"
        assert dialog.isVisible()
        table = dialog.findChild(QTableWidget, "mmFileTable")
        assert table.item(0, 0).text() == "Alanine"
        assert table.item(0, 1).text() == "Not set"
        assert table.item(1, 0).text() == "Citrate"
        assert table.item(1, 2).text() == "1 file: S1_MM"
        assert window.check_setup_action.isEnabled()
    finally:
        _close_window(window)


def test_guide_link_opens_labelled_user_guide(qapp, empty_db, monkeypatch):
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    _insert_compound("Alanine")
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        window.show_post_load_checklist()
        dialog = window._post_load_checklist
        dialog.user_guide_link.linkActivated.emit("guide")
        viewer = window.documentation_window
        assert viewer is not None
        assert viewer.current_file.name == "01_user_guide.md"
        assert viewer.current_fragment == "step-3-configure-internal-standard"
    finally:
        _close_window(window)


def test_guide_opens_unlabelled_mm_files_heading(qapp, empty_db, monkeypatch):
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    window = _make_window(monkeypatch, AnalysisMode.UNLABELLED)
    try:
        window._open_checklist_guide()
        viewer = window.documentation_window
        assert viewer.current_file.name == "Unlabelled_Targeted_Analysis.md"
        assert viewer.current_fragment == "additional-columns"
    finally:
        _close_window(window)


def test_checklist_guide_fragments_exist_in_rendered_docs():
    markdown = pytest.importorskip("markdown")
    repo = Path(__file__).parent.parent
    converter = markdown.Markdown(extensions=["markdown.extensions.toc"])
    labelled = converter.convert(
        (repo / "docs" / "01_user_guide.md").read_text(encoding="utf-8")
    )
    unlabelled = converter.convert(
        (repo / "docs" / "Unlabelled_Targeted_Analysis.md").read_text(encoding="utf-8")
    )
    assert 'id="step-3-configure-internal-standard"' in labelled
    assert 'id="additional-columns"' in unlabelled


def test_check_setup_action_requires_loaded_data(qapp, empty_db, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        assert window.check_setup_action.isEnabled() is False
        window.compound_data_loaded = True
        window._update_menu_states()
        assert window.check_setup_action.isEnabled() is False
        window.cdf_data_loaded = True
        window._update_menu_states()
        assert window.check_setup_action.isEnabled() is True
    finally:
        _close_window(window)


