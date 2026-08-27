"""Shared legend labels for EIC channel traces."""


def has_defined_channel(compound, channel_index: int) -> bool:
    """True when ``channel_index`` names a real analysis channel."""
    return (
        compound is not None
        and 0 <= channel_index < len(compound.analysis_channels)
    )


def channel_legend_label(compound, channel_index: int) -> str:
    """Return the name of one analysis channel for a plot legend.

    Uses ``IonChannel.label``. A missing compound or an index with no
    matching ion is a caller error, not an isotopologue name.
    """
    if compound is None:
        raise TypeError("compound is required")
    channels = compound.analysis_channels
    if channel_index < 0 or channel_index >= len(channels):
        raise IndexError(
            f"channel_index {channel_index} is outside "
            f"{len(channels)} analysis channels"
        )
    return channels[channel_index].label
