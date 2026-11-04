from PySide6.QtGui import QKeySequence

from manic.models.analysis import AnalysisMode

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
