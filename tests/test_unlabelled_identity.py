import pytest

from manic.models.analysis import IonChannel, IonRole
from manic.validation.unlabelled_identity import IdentityStatus, assess_identity


@pytest.fixture
def channels():
    return (
        IonChannel(217.0, IonRole.QUANTIFIER),
        IonChannel(
            147.0,
            IonRole.QUALIFIER,
            ordinal=1,
            expected_ratio=0.4,
            ratio_tolerance=0.25,
        ),
        IonChannel(
            73.0,
            IonRole.QUALIFIER,
            ordinal=2,
            expected_ratio=0.2,
            ratio_tolerance=0.25,
        ),
    )


def test_identity_is_supported_when_rt_and_ratios_pass(channels):
    result = assess_identity(
        [100.0, 42.0, 19.0],
        channels,
        expected_rt=12.0,
        observed_rt=12.04,
        rt_tolerance=0.1,
    )

    assert result.status is IdentityStatus.SUPPORTED
    assert result.rt_passed is True
    assert [ratio.observed_ratio for ratio in result.qualifier_ratios] == pytest.approx(
        [0.42, 0.19]
    )
    assert all(ratio.passed for ratio in result.qualifier_ratios)


def test_identity_requires_review_when_any_reference_fails(channels):
    result = assess_identity(
        [100.0, 70.0, 20.0],
        channels,
        expected_rt=12.0,
        observed_rt=12.2,
        rt_tolerance=0.1,
    )

    assert result.status is IdentityStatus.REVIEW_REQUIRED
    assert result.rt_passed is False
    assert result.qualifier_ratios[0].passed is False
    assert len(result.reasons) == 2


def test_identity_is_not_assessed_without_reference_ratios():
    channels = (
        IonChannel(217.0, IonRole.QUANTIFIER),
        IonChannel(147.0, IonRole.QUALIFIER, ordinal=1),
    )

    result = assess_identity(
        [100.0, 40.0],
        channels,
        expected_rt=12.0,
        observed_rt=12.01,
        rt_tolerance=0.1,
    )

    assert result.status is IdentityStatus.NOT_ASSESSED
    assert result.qualifier_ratios[0].observed_ratio == pytest.approx(0.4)
    assert result.qualifier_ratios[0].passed is None


def test_identity_is_not_detected_when_quantifier_is_zero(channels):
    result = assess_identity(
        [0.0, 5.0, 2.0],
        channels,
        expected_rt=12.0,
        observed_rt=12.0,
        rt_tolerance=0.1,
    )

    assert result.status is IdentityStatus.NOT_DETECTED
    assert all(ratio.observed_ratio is None for ratio in result.qualifier_ratios)
