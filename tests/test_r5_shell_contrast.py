import pytest
from PySide6.QtGui import QColor

from manic.ui import theme

# (foreground, background) token pairs that carry small text somewhere in the app.
SMALL_TEXT = [
    ("on_accent", "accent_fill"),  # primary button, step number
    ("on_accent", "accent_fill_hover"),
    ("on_accent", "accent_fill_pressed"),
    ("on_accent", "danger_fill"),  # destructive button
    ("on_accent", "danger_fill_hover"),
    ("text", "surface"),
    ("text", "bg"),
    ("text", "accent_soft"),  # selected list rows
    ("text_secondary", "surface"),
    ("text_secondary", "bg"),
    ("text_secondary", "surface_alt"),  # neutral badge, step number
    ("text_secondary", "surface_hover"),
    ("text_secondary", "accent_soft"),
    ("text_tertiary", "surface"),  # section headings, chart meta
    ("text_tertiary", "bg"),
    ("accent", "surface"),  # links, selected caption, status values
    ("accent", "bg"),
    ("accent", "accent_soft"),  # checked toolbar button
    ("danger", "surface"),  # error text
    ("danger", "bg"),
    ("danger", "danger_soft"),  # badge
    ("warning", "surface"),  # pending text
    ("warning", "bg"),
    ("warning", "warning_soft"),
    ("success", "surface"),  # step done
    ("success", "bg"),
    ("success", "success_soft"),
]

SCHEMES = {"light": theme.LIGHT, "dark": theme.DARK}


@pytest.mark.parametrize("scheme", SCHEMES)
def test_small_text_token_pairs_reach_aa(scheme):
    tokens = SCHEMES[scheme]
    low = [
        f"{fg} on {bg}: {ratio:.2f}"
        for fg, bg in SMALL_TEXT
        if (ratio := theme.contrast(QColor(tokens[fg]), QColor(tokens[bg]))) < 4.5
    ]
    assert low == []


@pytest.mark.parametrize("scheme", SCHEMES)
def test_status_icon_marks_and_focus_rings_reach_three_to_one(scheme):
    tokens = SCHEMES[scheme]
    pairs = [("surface", "success"), ("surface", "warning")]
    pairs += [("accent", "surface"), ("accent", "bg")]
    ratios = {p: theme.contrast(QColor(tokens[p[0]]), QColor(tokens[p[1]])) for p in pairs}
    assert {p: r for p, r in ratios.items() if r < 3} == {}


@pytest.mark.parametrize("scheme", SCHEMES)
def test_token_values_are_unique_so_a_scheme_remap_is_unambiguous(scheme):
    values = [v.lower() for v in SCHEMES[scheme].values()]
    assert len(values) == len(set(values))


@pytest.mark.parametrize("variant", ["primary", "danger"])
def test_rendered_filled_buttons_keep_white_labels_at_aa_in_both_schemes(qapp, variant):
    from PySide6.QtWidgets import QPushButton

    from manic.utils.utils import apply_color_scheme

    try:
        for dark in (False, True):
            apply_color_scheme(qapp, dark)
            button = QPushButton("Apply")
            button.setProperty("variant", variant)
            button.resize(120, 28)
            button.show()
            qapp.processEvents()
            image = button.grab().toImage()
            fill = image.pixelColor(6, image.height() // 2)
            button.close()
            assert theme.contrast(theme.color("on_accent"), fill) >= 4.5, (dark, fill.name())
    finally:
        apply_color_scheme(qapp, False)
        qapp.setStyleSheet("")
