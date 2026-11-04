from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QMenu

from manic.models.analysis import AnalysisMode
from manic.ui.left_toolbar import Toolbar

from conftest import _make_window


def _texts(menu) -> list[str]:
    return [action.text() for action in menu.actions() if action.text()]


def test_baseline_correction_sits_with_the_peak_commands(qapp, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        assert "Baseline Correction" not in _texts(window.view_menu)
        review = _texts(window.review_menu)
        assert review.index("Baseline Correction") > review.index("Curve Fit")
        action = window.baseline_action
        assert action.shortcut() == QKeySequence("Ctrl+Shift+B")

        checkbox = window.toolbar.baseline_checkbox
        checkbox.setChecked(True)
        assert action.isChecked()
        checkbox.setChecked(False)
        assert not action.isChecked()
    finally:
        window.close()


def test_help_menu_and_settings_in_file(qapp, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        titles = [a.text() for a in window.menuBar().actions()]
        assert titles == ["File", "View", "Review", "Help"]
        assert _texts(window.help_menu) == [
            "Documentation",
            "Check Data Setup...",
            "Check for Updates...",
            "About MANIC...",
        ]
        assert window.settings_action in window.file_menu.actions()
        assert window.settings_action.menuRole() == window.settings_action.MenuRole.PreferencesRole
        assert QKeySequence("Ctrl+,") in window.settings_action.shortcuts()
    finally:
        window.close()


def _standard_menu(toolbar):
    toolbar._show_internal_standard_menu()
    menu = toolbar.standard.findChildren(QMenu)[-1]
    checked = [a.text() for a in menu.actions() if a.isChecked()]
    groups = {a.actionGroup() for a in menu.actions() if a.isCheckable()}
    menu.close()
    return checked, groups


def test_internal_standard_menu_checks_the_current_choice(qapp):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    try:
        toolbar.update_compound_list(["Alanine", "Glycine"])
        checked, groups = _standard_menu(toolbar)
        assert checked == ["No Internal Standard"]
        assert len(groups) == 1 and next(iter(groups)).isExclusive()

        toolbar.standard.set_internal_standard("Glycine")
        checked, _groups = _standard_menu(toolbar)
        assert checked == ["Glycine"]
    finally:
        toolbar.deleteLater()
