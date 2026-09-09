import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QPushButton

from manic.ui.analysis_mode_dialog import AnalysisModeDialog
from manic.utils.utils import apply_app_stylesheet

STYLED_DEFAULT_BUTTON = QColor("#0d6efd")


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app
    app.setStyleSheet("")


def _default_button_fill(dialog: AnalysisModeDialog) -> QColor:
    button = next(b for b in dialog.findChildren(QPushButton) if b.isDefault())
    image = button.grab().toImage()
    return image.pixelColor(image.width() // 2, image.height() // 2)


def test_parentless_dialog_is_styled_once_stylesheet_is_app_wide(qapp):
    unstyled = AnalysisModeDialog()
    unstyled.show()
    qapp.processEvents()
    assert _default_button_fill(unstyled) != STYLED_DEFAULT_BUTTON

    apply_app_stylesheet(qapp)
    styled = AnalysisModeDialog()
    styled.show()
    qapp.processEvents()
    assert _default_button_fill(styled) == STYLED_DEFAULT_BUTTON
