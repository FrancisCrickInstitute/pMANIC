import pytest

from manic.models.analysis import (
    AnalysisContext,
    AnalysisMode,
    IonChannel,
    IonRole,
    labelled_channels,
    validate_unlabelled_channels,
)
from manic.ui.channel_labels import channel_legend_label


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
        channel_count = 3

    assert channel_legend_label(Labelled(), 2) == "M+2"
