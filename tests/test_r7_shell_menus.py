import re
from pathlib import Path

from PySide6.QtWidgets import QMenu

from manic.models.analysis import AnalysisMode
from manic.ui import theme
from manic.ui.left_toolbar import Toolbar

from conftest import _make_window


def test_show_all_samples_is_listed_once_in_the_menu_bar(qapp, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        action = window.show_all_samples_action
        assert action in window.review_menu.actions()
        assert action not in window.view_menu.actions()
        # The canvas button stays as the recovery path when no plot is left.
        assert window.show_all_samples_button.text() == "Show all samples"
    finally:
        window.close()


def test_internal_standard_menu_ticks_with_the_app_checkmark_in_text_colour(qapp):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    try:
        toolbar.update_compound_list(["Alanine", "Glycine"])
        toolbar._show_internal_standard_menu()
        menu = toolbar.standard.findChildren(QMenu)[-1]
        image = Path(re.search(r'url\("([^"]+)"\)', menu.styleSheet()).group(1))
        assert f'fill="{theme.color("text").name()}"' in image.read_text()
        menu.close()
    finally:
        toolbar.deleteLater()
