import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QLabel, QPushButton

from manic.ui import theme
from manic.ui.analysis_mode_dialog import AnalysisModeDialog
from manic.ui.dialog_kit import status_icon
from manic.ui.update_old_data_dialog import UpdateOldDataDialog
from manic.utils.utils import apply_app_stylesheet, apply_color_scheme


@pytest.fixture
def restore_light_scheme(qapp):
    yield
    apply_color_scheme(qapp, False)
    qapp.setStyleSheet("")


def _dialog_fill(dialog: AnalysisModeDialog) -> str:
    return dialog.grab().toImage().pixelColor(2, 2).name()


def _best_contrast(image: QImage, against: QColor) -> float:
    """The strongest contrast any pixel of ``image`` makes with ``against``."""
    return max(
        theme.contrast(image.pixelColor(x, y), against)
        for x in range(image.width())
        for y in range(image.height())
    )


def test_parentless_dialog_is_styled_once_stylesheet_is_app_wide(qapp, restore_light_scheme):
    unstyled = AnalysisModeDialog()
    unstyled.show()
    qapp.processEvents()
    assert _dialog_fill(unstyled) != "#ffffff"

    apply_app_stylesheet(qapp)
    apply_color_scheme(qapp, False)
    styled = AnalysisModeDialog()
    styled.show()
    qapp.processEvents()
    assert _dialog_fill(styled) == "#ffffff"

    apply_color_scheme(qapp, True)
    dark = AnalysisModeDialog()
    dark.show()
    qapp.processEvents()
    assert _dialog_fill(dark) == "#232529"
    for dialog in (unstyled, styled, dark):
        dialog.close()


@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
def test_rendered_text_focus_rings_and_status_marks_reach_wcag_contrast_in_both_schemes(
    qapp, restore_light_scheme, dark
):
    apply_color_scheme(qapp, dark)

    for variant in ("primary", "danger"):
        for pressed in (False, True):
            button = QPushButton("Apply")
            button.setProperty("variant", variant)
            button.resize(120, 28)
            button.show()
            button.setDown(pressed)
            qapp.processEvents()
            image = button.grab().toImage()
            button.close()
            fill = image.pixelColor(6, image.height() // 2)
            label = _best_contrast(image.copy(30, 6, 60, 16), fill)
            assert label >= 4.5, (variant, pressed, fill.name(), label)
    # Offscreen Qt never paints :hover, so the hover fills are checked as the stylesheet sets them.
    for hover_fill in ("accent_fill_hover", "danger_fill_hover"):
        assert theme.contrast(theme.color("on_accent"), theme.color(hover_fill)) >= 4.5, hover_fill

    # Small secondary text, as a real dialog draws it.
    dialog = UpdateOldDataDialog()
    dialog.show()
    qapp.processEvents()
    hint = next(label for label in dialog.findChildren(QLabel) if label.text().startswith("Lists"))
    image = dialog.grab(QRect(hint.mapTo(dialog, QPoint(0, 0)), hint.size())).toImage()
    ground = image.pixelColor(image.width() - 2, image.height() // 2)
    assert _best_contrast(image, ground) >= 4.5, ground.name()
    # The read-only path field's "No file selected" placeholder.
    image = dialog.c_edit.grab().toImage()
    dialog.close()
    ground = image.pixelColor(image.width() - 6, image.height() // 2)
    placeholder = image.copy(4, 4, 120, image.height() - 8)
    assert _best_contrast(placeholder, ground) >= 4.5, ground.name()

    # Focus rings and status-icon marks are non-text, so 3:1.
    button = QPushButton("Apply")
    button.resize(120, 28)
    button.show()
    button.activateWindow()
    button.setFocus(Qt.OtherFocusReason)
    qapp.processEvents()
    image = button.grab().toImage()
    button.close()
    ring = image.pixelColor(60, 0)
    assert theme.contrast(ring, image.pixelColor(60, 3)) >= 3, ring.name()

    for passed in (True, False):
        icon = status_icon(passed).pixmap(28, 28).toImage()
        disc = icon.pixelColor(4, 14)
        assert _best_contrast(icon.copy(6, 6, 16, 16), disc) >= 3, passed
