import pytest
from PySide6.QtGui import QColor

from manic.ui import theme
from manic.ui.plot_tile import _TONES, TileBadge, tile_tint


@pytest.mark.parametrize("scheme", [theme.LIGHT, theme.DARK], ids=["light", "dark"])
@pytest.mark.parametrize("tone", ["danger", "warning"])
def test_problem_badges_read_as_pills_on_their_tinted_card(scheme, tone):
    fg, bg = (QColor(scheme[token]) for token in _TONES[tone])
    tint = QColor(scheme[tile_tint([TileBadge("x", tone, "")])])
    assert bg != tint
    assert theme.contrast(fg, bg) >= 4.5
