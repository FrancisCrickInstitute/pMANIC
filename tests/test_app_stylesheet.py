from PySide6.QtGui import QColor
from PySide6.QtWidgets import QPushButton

from manic.ui.analysis_mode_dialog import AnalysisModeDialog
from manic.ui.theme import COLORS
from manic.utils.utils import apply_app_stylesheet

STYLED_DEFAULT_BUTTON = QColor(COLORS["accent_fill"])


def _default_button_fill(dialog: AnalysisModeDialog) -> QColor:
    button = next(b for b in dialog.findChildren(QPushButton) if b.isDefault())
    image = button.grab().toImage()
    # Sample the fill beside the label, not the centred text.
    return image.pixelColor(4, image.height() // 2)


def test_parentless_dialog_is_styled_once_stylesheet_is_app_wide(qapp):
    try:
        unstyled = AnalysisModeDialog()
        unstyled.show()
        qapp.processEvents()
        assert _default_button_fill(unstyled) != STYLED_DEFAULT_BUTTON

        apply_app_stylesheet(qapp)
        styled = AnalysisModeDialog()
        styled.show()
        qapp.processEvents()
        assert _default_button_fill(styled) == STYLED_DEFAULT_BUTTON
    finally:
        qapp.setStyleSheet("")


def test_logo_drops_its_white_background_and_inks_in_the_active_text_colour(qapp):
    from manic.ui.logo import LogoLabel
    from manic.utils.utils import apply_color_scheme

    def pixel(label: LogoLabel, x: int, y: int) -> QColor:
        return label.pixmap().toImage().pixelColor(x, y)

    try:
        apply_color_scheme(qapp, False)
        logo = LogoLabel(446)  # the artwork's own height, so pixels map 1:1
        assert pixel(logo, 0, 0).alpha() == 0
        assert pixel(logo, 548, 64).name() == "#1b1f24"
        assert pixel(logo, 83, 167).name() == "#22b573"

        apply_color_scheme(qapp, True)
        assert pixel(logo, 548, 64).name() == "#e6e8eb"
        assert pixel(logo, 83, 167).name() == "#22b573"
    finally:
        apply_color_scheme(qapp, False)
        qapp.setStyleSheet("")
