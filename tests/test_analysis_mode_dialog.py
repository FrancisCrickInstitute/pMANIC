import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from manic.ui.analysis_mode_dialog import AnalysisModeDialog

LABELLED_DESCRIPTION = (
    "For stable-isotope tracing: M+0, M+1 and later isotopologues are "
    "measured and corrected for natural isotope abundance."
)
UNLABELLED_DESCRIPTION = (
    "For targeted GC-MS profiling: one quantifier ion provides the response "
    "and qualifier ions check retention and ion-ratio consistency."
)


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_mode_dialog_shows_only_a_description_per_mode(qapp):
    dialog = AnalysisModeDialog()

    assert [label.text() for label in dialog.findChildren(QLabel)] == [
        "What type of analysis are you performing?",
        LABELLED_DESCRIPTION,
        UNLABELLED_DESCRIPTION,
    ]
    mode_buttons = [
        button
        for button in dialog.findChildren(QPushButton)
        if button.text() not in {"Cancel", "&Cancel"}
    ]
    assert [button.text() for button in mode_buttons] == [
        "Labelled isotope-tracing analysis",
        "Unlabelled targeted analysis",
    ]
    assert [button.toolTip() for button in mode_buttons] == ["", ""]
