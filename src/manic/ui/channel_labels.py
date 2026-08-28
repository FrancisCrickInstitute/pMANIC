"""Shared legend labels for EIC channel traces."""

from collections.abc import Sequence

from manic.models.analysis import IonChannel


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


def channel_legend_text(compound_name: str, channels: Sequence[IonChannel]) -> str:
    labels = "  ".join(channel.label for channel in channels)
    if not labels:
        return compound_name
    return f"{compound_name}  {labels}"
