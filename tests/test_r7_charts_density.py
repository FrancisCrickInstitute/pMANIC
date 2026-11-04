from manic.ui.plot_tile import DENSITY_MIN_TILE, grid_columns


def _shape(density, width, height, count=30):
    min_w, min_h = DENSITY_MIN_TILE[density]
    return grid_columns(count, width, height, min_width=min_w, min_height=min_h)


def test_compact_fits_a_laptop_grid_that_comfortable_scrolls(qapp):
    # The grid viewport of a 1512x949 window with the sidebar open.
    compact = _shape("compact", 1180, 790)
    comfortable = _shape("comfortable", 1180, 790)
    assert compact[1] == 0, "compact shows all 30 tiles without scrolling"
    assert comfortable[1] > 0, "comfortable keeps larger tiles and scrolls"
    assert compact[0] > comfortable[0]


def test_compact_still_fits_at_the_small_laptop_size(qapp):
    # 1280x800 at 150% leaves about 700x520 for the grid.
    assert _shape("compact", 700, 520, count=11)[1] == 0
