"""Shared legend labels for EIC channel traces."""


def channel_legend_label(compound, channel_index: int) -> str:
    """Return a mode-appropriate name for an analytical channel.

    Unlabelled targets use quantifier/qualifier ion names. Labelled
    compounds keep the historical M+n isotopologue naming.
    """
    if (
        compound is not None
        and getattr(compound, "is_unlabelled_target", False)
        and channel_index < getattr(compound, "channel_count", 0)
    ):
        return compound.analysis_channels[channel_index].label
    return f"M+{channel_index}"
