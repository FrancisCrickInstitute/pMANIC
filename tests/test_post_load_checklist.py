import sys
from pathlib import Path
from unittest import mock

import pytest
from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QTableWidget,
)

from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.models.mm_file_check import MmFileStatus
from manic.ui.main_window import MainWindow
from manic.ui.post_load_checklist_dialog import PostLoadChecklistDialog

from conftest import _make_window

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from ui_tour import layout_problems

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


def _long_dialog(tmp_path) -> PostLoadChecklistDialog:
    path = tmp_path / "compounds.csv"
    path.write_text("")
    names = [row.compound_name for row in LONG_REPORT]
    return PostLoadChecklistDialog(
        names, None, LONG_REPORT, None, compound_list_path=str(path)
    )


def _settle() -> None:
    for _ in range(5):
        QApplication.processEvents()


def _button(dialog: PostLoadChecklistDialog, text: str) -> QPushButton:
    return next(b for b in dialog.buttons.buttons() if b.text() == text)


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
    combo = dialog.findChild(QComboBox, "internalStandardCombo")
    assert combo.currentText() == "Norvaline"
    assert dialog.selected_internal_standard() == "Norvaline"
    dialog.close()


def test_unchanged_checklist_offers_one_continue(qapp):
    dialog = PostLoadChecklistDialog(["Alanine"], None, [], None)
    combo = dialog.findChild(QComboBox, "internalStandardCombo")
    assert combo.currentText() == "No internal standard"
    assert dialog.findChild(QLabel, "internalStandardStatus") is None
    visible = [b.text() for b in dialog.buttons.buttons() if not b.isHidden()]
    assert visible == ["Continue"]
    combo.setCurrentText("Alanine")
    assert dialog.selected_internal_standard() == "Alanine"
    visible = [b.text() for b in dialog.buttons.buttons() if not b.isHidden()]
    assert sorted(visible) == ["Apply", "Continue without changes"]
    combo.setCurrentIndex(0)
    visible = [b.text() for b in dialog.buttons.buttons() if not b.isHidden()]
    assert visible == ["Continue"]
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
        combo = dialog.findChild(QComboBox, "internalStandardCombo")
        combo.setCurrentText("Norvaline")
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
        combo = dialog.findChild(QComboBox, "internalStandardCombo")
        combo.setCurrentText("Norvaline")
        _button(dialog, "Continue without changes").click()
        assert window.toolbar.get_internal_standard() == "Alanine"
        assert _standard_shown(window) == "Alanine"
    finally:
        _close_window(window)


def test_checklist_tooltips_only_reveal_hidden_values(qapp):
    long_pattern = "*_MM_standard_mixture_run_01*,*_MM_standard_mixture_run_02*"
    report = [
        MmFileStatus("Short", "*MM*", ("A", "B")),
        MmFileStatus("Many", "*MM*", ("A", "B", "C", "D")),
        MmFileStatus("Long", long_pattern, ("A",)),
    ]
    dialog = PostLoadChecklistDialog(["Short", "Many", "Long"], None, report, None)
    table = dialog.mm_file_table
    tips = {
        table.item(row, 0).text(): [table.item(row, col).toolTip() for col in range(3)]
        for row in range(table.rowCount())
    }
    assert tips["Short"] == ["", "", ""]
    assert tips["Many"] == ["", "", "A\nB\nC\nD"]
    assert tips["Long"] == ["", long_pattern, ""]
    dialog.close()


def test_checklist_names_the_loaded_compound_list_and_opens_it(qapp, tmp_path):
    path = tmp_path / "compounds_v3.xlsx"
    path.write_bytes(b"")
    report = [MmFileStatus("Alanine", None, ())]
    dialog = PostLoadChecklistDialog(
        ["Alanine"], None, report, None, compound_list_path=str(path)
    )
    source = dialog.findChild(QLabel, "compoundListFile")
    assert source.text() == "Compound list: compounds_v3.xlsx"
    assert source.toolTip() == str(path)

    with mock.patch(
        "manic.ui.post_load_checklist_dialog.QDesktopServices.openUrl"
    ) as open_url:
        dialog.findChild(QPushButton, "openCompoundListButton").click()
        dialog.findChild(QPushButton, "showCompoundListFolderButton").click()
    assert [c.args[0] for c in open_url.call_args_list] == [
        QUrl.fromLocalFile(str(path)),
        QUrl.fromLocalFile(str(Path(tmp_path))),
    ]
    dialog.close()


# 680x640 is the dialog capped on a 150% 1280x800 laptop; 680x540 on an 800x600 screen.
@pytest.mark.parametrize("height", [640, 540, 420, 300])
@pytest.mark.parametrize("steps_shown", [False, True])
def test_checklist_text_never_collides_on_a_short_screen(qapp, tmp_path, height, steps_shown):
    dialog = _long_dialog(tmp_path)
    try:
        dialog.show()
        dialog.change_pattern_toggle.setChecked(steps_shown)
        dialog.resize(680, height)
        _settle()
        assert layout_problems(dialog) == []
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons.geometry().bottom() < dialog.height()
        assert not dialog.scroll.isAncestorOf(buttons)
        table = dialog.mm_file_table
        fourth_row_bottom = table.rowViewportPosition(3) + table.rowHeight(3)
        assert fourth_row_bottom <= table.viewport().height()
    finally:
        dialog.close()


def test_change_pattern_steps_open_inline_under_the_compound_list(qapp, tmp_path):
    dialog = _long_dialog(tmp_path)
    try:
        dialog.show()
        dialog.resize(680, 540)
        _settle()
        source = dialog.findChild(QLabel, "compoundListFile")
        assert source.isVisible()
        assert source.text() == "Compound list: compounds.csv"
        assert not dialog.change_pattern_steps.isVisible()

        dialog.change_pattern_toggle.click()
        dialog.resize(680, 540)
        _settle()
        steps = dialog.change_pattern_steps
        assert steps.isVisible()
        assert dialog.user_guide_link.isVisible()
        assert source.isVisible()
        top = steps.mapTo(dialog.scroll.viewport(), steps.rect().topLeft()).y()
        assert 0 <= top
        assert top + steps.height() <= dialog.scroll.viewport().height()

        dialog.change_pattern_toggle.click()
        _settle()
        assert not steps.isVisible()
        assert not dialog.user_guide_link.isVisible()
    finally:
        dialog.close()


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
