from manic.ui.standard_indicator_widget import CompoundIndicator, StandardIndicator


def _fill(widget) -> str:
    return widget.styleSheet().split("background-color: ")[1].split(";")[0]


def test_standard_pill_prefixes_the_name(qapp):
    pill = StandardIndicator()
    assert pill.text() == "Int Std: <b>none</b>"
    assert _fill(pill) == "rgba(215, 50, 50, 0.5019607843137255)"

    pill.set_internal_standard("Norvaline")
    assert pill.text() == "Int Std: <b>Norvaline</b>"
    assert pill.internal_standard == "Norvaline"
    assert _fill(pill) == "rgba(102, 215, 102, 0.5019607843137255)"

    pill.clear_internal_standard()
    assert pill.text() == "Int Std: <b>none</b>"
    assert pill.internal_standard is None


def test_compound_pill_is_blue_when_set_and_grey_when_empty(qapp):
    pill = CompoundIndicator()
    assert pill.text() == "Compound: <b>--</b>"
    assert _fill(pill) == "rgba(233, 236, 239, 1.0)"

    pill.set_compound("Glutamate")
    assert pill.text() == "Compound: <b>Glutamate</b>"
    assert _fill(pill) == "rgba(13, 110, 253, 0.3137254901960784)"


def test_long_names_are_elided_to_the_pill_width_with_full_text_in_tooltip(qapp):
    pill = CompoundIndicator()
    name = "Phosphoenolpyruvate-13C3-15N2-very-long"
    pill.set_compound(name)
    pill.show()
    pill.resize(154, 20)
    assert pill.text().endswith("…</b>")
    assert pill.toolTip() == f"Compound: {name}"
    pill.resize(600, 20)
    assert pill.text() == f"Compound: <b>{name}</b>"
