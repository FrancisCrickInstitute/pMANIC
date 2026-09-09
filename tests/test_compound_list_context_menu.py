import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu

from manic.ui.compound_list_widget import CompoundListWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_right_click_targets_the_compound_under_the_cursor_even_after_scrolling(
    qapp, monkeypatch
):
    widget = CompoundListWidget()
    widget.resize(200, 150)
    widget.show()
    qapp.processEvents()
    widget.update_compounds([f"Compound_{i:02d}" for i in range(40)])
    qapp.processEvents()

    clicked = widget.item(6)
    pos = widget.visualItemRect(clicked).center()
    QTest.mousePress(widget.viewport(), Qt.RightButton, Qt.NoModifier, pos)
    qapp.processEvents()
    assert widget.verticalScrollBar().value() > 0
    assert widget.itemAt(pos) is not clicked

    monkeypatch.setattr(QMenu, "exec_", lambda self, *_args: None)
    emitted = []
    widget.internal_standard_selected.connect(emitted.append)
    widget._show_context_menu(pos)
    menu = widget.findChild(QMenu)
    {a.text(): a for a in menu.actions()}["Select as Internal Standard"].trigger()
    assert emitted == ["Compound_06"]
    widget.deleteLater()
