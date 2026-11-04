import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel

from manic.models.mm_file_check import MmFileStatus
from manic.ui.post_load_checklist_dialog import PostLoadChecklistDialog

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from ui_tour import layout_problems

REPORT = [
    MmFileStatus(f"Compound {i}", "*_MM_01*,*_MM_02*", ("Std_MM_01", "Std_MM_02"))
    for i in range(95)
]


def _dialog(tmp_path) -> PostLoadChecklistDialog:
    path = tmp_path / "compounds.csv"
    path.write_text("")
    names = [row.compound_name for row in REPORT]
    return PostLoadChecklistDialog(names, None, REPORT, None, compound_list_path=str(path))


def _settle() -> None:
    for _ in range(5):
        QApplication.processEvents()


# 680x640 is the dialog capped on a 150% 1280x800 laptop; 680x540 on an 800x600 screen.
@pytest.mark.parametrize("height", [640, 540, 420])
@pytest.mark.parametrize("steps_shown", [False, True])
def test_checklist_text_never_collides_on_a_short_screen(qapp, tmp_path, height, steps_shown):
    dialog = _dialog(tmp_path)
    try:
        dialog.show()
        dialog.change_pattern_toggle.setChecked(steps_shown)
        dialog.resize(680, height)
        _settle()
        assert layout_problems(dialog) == []
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons.geometry().bottom() < dialog.height()
        assert not dialog.scroll.isAncestorOf(buttons)
    finally:
        dialog.close()


def test_change_pattern_steps_open_inline_under_the_compound_list(qapp, tmp_path):
    dialog = _dialog(tmp_path)
    try:
        dialog.show()
        _settle()
        source = dialog.findChild(QLabel, "compoundListFile")
        assert source.isVisible()
        assert source.text() == "Compound list: compounds.csv"
        assert dialog.change_pattern_toggle.text() == "▸ How do I change a pattern?"
        assert not dialog.change_pattern_steps.isVisible()

        dialog.change_pattern_toggle.click()
        _settle()
        assert dialog.change_pattern_toggle.text() == "▾ How do I change a pattern?"
        assert dialog.change_pattern_steps.isVisible()
        assert dialog.change_pattern_text.text().startswith("1. Edit the mmfiles cell")
        assert dialog.user_guide_link.isVisible()
        assert source.isVisible()
    finally:
        dialog.close()


def test_mm_table_keeps_four_rows_however_short_the_dialog(qapp, tmp_path):
    dialog = _dialog(tmp_path)
    try:
        table = dialog.mm_file_table
        dialog.show()
        dialog.resize(680, 300)
        _settle()
        rows = table.viewport().height() / table.verticalHeader().defaultSectionSize()
        assert rows >= 4
    finally:
        dialog.close()


def test_opening_the_steps_on_a_short_screen_scrolls_them_into_view(qapp, tmp_path):
    dialog = _dialog(tmp_path)
    try:
        dialog.show()
        dialog.resize(680, 540)
        _settle()
        dialog.change_pattern_toggle.click()
        dialog.resize(680, 540)
        _settle()
        steps = dialog.change_pattern_steps
        top = steps.mapTo(dialog.scroll.viewport(), steps.rect().topLeft()).y()
        assert 0 <= top
        assert top + steps.height() <= dialog.scroll.viewport().height()
    finally:
        dialog.close()
