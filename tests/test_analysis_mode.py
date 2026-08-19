import pytest

from manic.models.analysis import (
    AnalysisContext,
    AnalysisMode,
    IonChannel,
    IonRole,
    labelled_channels,
    validate_unlabelled_channels,
)
from manic.ui.channel_labels import channel_legend_label, has_defined_channel


def test_analysis_context_defaults_to_labelled_and_is_immutable():
    context = AnalysisContext()

    assert context.mode is AnalysisMode.LABELLED
    with pytest.raises(AttributeError):
        context.mode = AnalysisMode.UNLABELLED


def test_analysis_mode_coerces_exported_string_values():
    assert AnalysisMode.coerce("LABELLED") is AnalysisMode.LABELLED
    assert AnalysisMode.coerce("unlabelled") is AnalysisMode.UNLABELLED


def test_labelled_channels_preserve_consecutive_isotopologue_order():
    channels = labelled_channels(174.0, 3)

    assert [channel.mz for channel in channels] == [174.0, 175.0, 176.0, 177.0]
    assert [channel.ordinal for channel in channels] == [0, 1, 2, 3]
    assert all(channel.role is IonRole.ISOTOPOLOGUE for channel in channels)


def test_unlabelled_channels_order_quantifier_before_arbitrary_qualifiers():
    channels = validate_unlabelled_channels(
        [
            IonChannel(73.0, IonRole.QUALIFIER, ordinal=2),
            IonChannel(217.0, IonRole.QUANTIFIER),
            IonChannel(147.0, IonRole.QUALIFIER, ordinal=1),
        ]
    )

    assert [channel.mz for channel in channels] == [217.0, 147.0, 73.0]
    assert [channel.role for channel in channels] == [
        IonRole.QUANTIFIER,
        IonRole.QUALIFIER,
        IonRole.QUALIFIER,
    ]


@pytest.mark.parametrize(
    "channels, message",
    [
        (
            [IonChannel(217.0, IonRole.QUALIFIER, ordinal=1)],
            "exactly one quantifier",
        ),
        (
            [IonChannel(217.0, IonRole.QUANTIFIER)],
            "at least one qualifier",
        ),
        (
            [
                IonChannel(217.0, IonRole.QUANTIFIER),
                IonChannel(217.0, IonRole.QUALIFIER, ordinal=1),
            ],
            "must be distinct",
        ),
        (
            [
                IonChannel(217.1, IonRole.QUANTIFIER),
                IonChannel(217.4, IonRole.QUALIFIER, ordinal=1),
            ],
            "distinct nominal masses",
        ),
    ],
)
def test_invalid_unlabelled_channel_definitions_are_rejected(channels, message):
    with pytest.raises(ValueError, match=message):
        validate_unlabelled_channels(channels)


def test_detailed_plot_uses_diagnostic_ion_labels_in_unlabelled_mode():
    class Target:
        is_unlabelled_target = True
        analysis_channels = (
            IonChannel(217.0, IonRole.QUANTIFIER),
            IonChannel(147.0, IonRole.QUALIFIER, ordinal=1),
        )
        channel_count = len(analysis_channels)

    assert channel_legend_label(Target(), 0) == "Q ion m/z 217"
    assert channel_legend_label(Target(), 1) == "V ion 1 m/z 147"


def test_detailed_plot_preserves_isotopologue_labels_in_labelled_mode():
    class Labelled:
        is_unlabelled_target = False
        analysis_channels = labelled_channels(174.0, 3)
        channel_count = len(analysis_channels)

    assert channel_legend_label(Labelled(), 2) == "M+2 m/z 176"


def test_channel_legend_label_rejects_out_of_range_index():
    class Target:
        analysis_channels = (
            IonChannel(217.0, IonRole.QUANTIFIER),
            IonChannel(147.0, IonRole.QUALIFIER, ordinal=1),
        )

    with pytest.raises(IndexError, match="outside 2 analysis channels"):
        channel_legend_label(Target(), 2)


def test_channel_legend_label_requires_a_compound():
    with pytest.raises(TypeError, match="compound is required"):
        channel_legend_label(None, 2)


def test_has_defined_channel_skips_missing_compound_and_extra_traces():
    class Target:
        analysis_channels = (
            IonChannel(217.0, IonRole.QUANTIFIER),
            IonChannel(147.0, IonRole.QUALIFIER, ordinal=1),
        )

    assert has_defined_channel(None, 0) is False
    assert has_defined_channel(Target(), 0) is True
    assert has_defined_channel(Target(), 1) is True
    assert has_defined_channel(Target(), 2) is False
