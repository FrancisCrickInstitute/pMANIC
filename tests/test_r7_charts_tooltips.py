from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from manic.ui.channel_chips import ChannelChip
from manic.ui.colors import ChannelTraceStyle, label_colors
from manic.ui.plot_tile import PEAK_BADGES, PlotTile
from manic.validation.peak_verdict import PeakVerdict


def test_caption_tooltip_appears_only_when_the_name_is_cut(qapp):
    tile = PlotTile(QWidget())
    tile.set_caption("Sample_05_rt_shift_with_a_long_name")
    try:
        tile.show()
        tile.resize(600, 300)
        qapp.processEvents()
        assert tile.caption.text() == "Sample_05_rt_shift_with_a_long_name"
        assert tile.caption.toolTip() == ""
        tile.resize(90, 300)
        qapp.processEvents()
        assert tile.caption.text() != tile.caption.fullText()
        assert tile.caption.toolTip() == "Sample_05_rt_shift_with_a_long_name"
    finally:
        tile.deleteLater()


def test_chip_tooltip_appears_only_when_the_label_is_cut(qapp):
    chip = ChannelChip("Qualifier ion 1 m/z 147", ChannelTraceStyle(label_colors[0], Qt.SolidLine))
    try:
        chip.show()
        chip.resize(chip.sizeHint())
        qapp.processEvents()
        assert chip.toolTip() == ""
        chip.resize(60, chip.height())
        qapp.processEvents()
        assert chip.toolTip() == "Qualifier ion 1 m/z 147"
    finally:
        chip.deleteLater()


def test_badge_tooltips_add_only_what_the_badge_does_not_say(qapp):
    assert PEAK_BADGES[PeakVerdict.FAIL].tooltip == "Right-click to accept it or mark it as bad."
    assert PEAK_BADGES[PeakVerdict.REJECTED].tooltip == ""
