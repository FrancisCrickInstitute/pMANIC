from types import SimpleNamespace

import pytest

from manic.io.data_provider import DataProvider
from manic.models.analysis import IonChannel, IonRole
from manic.validation.unlabelled_identity import (
    IdentityAssessmentSet,
    IdentityQcResult,
    IdentitySampleAssessment,
    IdentityStatus,
    QualifierRatioResult,
    QualifierStatus,
    assess_identity,
    qualifier_pair,
)


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


def _qion() -> IonChannel:
    return IonChannel(217.0, IonRole.QUANTIFIER)


def _v1(*, expected: float | None = 0.4, tolerance: float | None = 0.25) -> IonChannel:
    return IonChannel(
        147.0,
        IonRole.QUALIFIER,
        ordinal=1,
        expected_ratio=expected,
        ratio_tolerance=tolerance,
    )


def _v2(*, expected: float | None = 0.2, tolerance: float | None = 0.25) -> IonChannel:
    return IonChannel(
        73.0,
        IonRole.QUALIFIER,
        ordinal=2,
        expected_ratio=expected,
        ratio_tolerance=tolerance,
    )


def _qc(
    channels: tuple[IonChannel, ...],
    *,
    status: IdentityStatus,
    passed: tuple[bool | None, ...],
    observed: tuple[float | None, ...] | None = None,
) -> IdentityQcResult:
    qualifiers = [channel for channel in channels if channel.role is IonRole.QUALIFIER]
    ratios = tuple(
        QualifierRatioResult(
            channel,
            None if observed is None else observed[index],
            passed[index],
        )
        for index, channel in enumerate(qualifiers)
    )
    return IdentityQcResult(
        status=status,
        quantifier_area=0.0 if status is IdentityStatus.NOT_DETECTED else 100.0,
        observed_rt=None if status is IdentityStatus.NOT_DETECTED else 12.0,
        rt_error=None,
        rt_passed=None if status is IdentityStatus.NOT_DETECTED else True,
        qualifier_ratios=ratios,
        reasons=(),
    )


def test_qualifier_pair_q_v1_pass_leaves_v2_absent():
    channels = (_qion(), _v1())
    pair = qualifier_pair(
        channels,
        _qc(channels, status=IdentityStatus.SUPPORTED, passed=(True,), observed=(0.41,)),
    )

    assert pair.v1.status is QualifierStatus.VALIDATED
    assert pair.v1.channel is channels[1]
    assert pair.v1.ratio is not None
    assert pair.v1.ratio.passed is True
    assert "observed 0.410" in pair.v1.detail
    assert pair.v2.status is QualifierStatus.ABSENT
    assert pair.v2.channel is None
    assert pair.v2.detail == "not in the method"


def test_qualifier_pair_q_v2_fail_leaves_v1_absent():
    channels = (_qion(), _v2())
    pair = qualifier_pair(
        channels,
        _qc(
            channels,
            status=IdentityStatus.REVIEW_REQUIRED,
            passed=(False,),
            observed=(0.80,),
        ),
    )

    assert pair.v1.status is QualifierStatus.ABSENT
    assert pair.v1.detail == "not in the method"
    assert pair.v2.status is QualifierStatus.FAILED
    assert pair.v2.channel is channels[1]
    assert pair.v2.channel.ordinal == 2
    assert "observed 0.800" in pair.v2.detail


def test_qualifier_pair_q_v1_v2_mixed_pass_and_fail():
    channels = (_qion(), _v1(), _v2())
    pair = qualifier_pair(
        channels,
        _qc(
            channels,
            status=IdentityStatus.REVIEW_REQUIRED,
            passed=(True, False),
            observed=(0.41, 0.80),
        ),
    )

    assert pair.v1.status is QualifierStatus.VALIDATED
    assert pair.v2.status is QualifierStatus.FAILED
    assert [item.ordinal for item in pair] == [1, 2]
    assert pair.for_ordinal(1) is pair.v1
    assert pair.for_ordinal(2) is pair.v2


def test_qualifier_pair_missing_expected_ratio_is_not_assessed():
    channels = (_qion(), _v1(expected=None, tolerance=None))
    pair = qualifier_pair(
        channels,
        _qc(
            channels,
            status=IdentityStatus.NOT_ASSESSED,
            passed=(None,),
            observed=(0.40,),
        ),
    )

    assert pair.v1.status is QualifierStatus.NOT_ASSESSED
    assert pair.v1.detail == "expected ratio or tolerance is missing"
    assert pair.v2.status is QualifierStatus.ABSENT


def test_qualifier_pair_q_not_detected_is_not_assessed():
    channels = (_qion(), _v1(), _v2())
    pair = qualifier_pair(
        channels,
        _qc(
            channels,
            status=IdentityStatus.NOT_DETECTED,
            passed=(None, None),
            observed=(None, None),
        ),
    )

    assert pair.v1.status is QualifierStatus.NOT_ASSESSED
    assert pair.v2.status is QualifierStatus.NOT_ASSESSED
    assert pair.v1.detail == "Q ion was not detected; ratio was not assessed"
    assert pair.v2.detail == "Q ion was not detected; ratio was not assessed"


def test_qualifier_pair_provider_exception_is_unavailable():
    channels = (_qion(), _v1())
    pair = qualifier_pair(channels, None, error="EIC file is missing")

    assert pair.v1.status is QualifierStatus.UNAVAILABLE
    assert pair.v1.channel is channels[1]
    assert pair.v1.ratio is None
    assert pair.v1.detail == "EIC file is missing"
    assert pair.v2.status is QualifierStatus.ABSENT
    assert pair.v2.detail == "not in the method"


def test_identity_assessment_set_indexes_samples_and_rejects_duplicates():
    channels = (_qion(), _v1())
    qc = _qc(channels, status=IdentityStatus.SUPPORTED, passed=(True,), observed=(0.41,))
    snapshot = IdentityAssessmentSet(
        "Target",
        channels,
        (
            IdentitySampleAssessment("S1", qc, qualifier_pair(channels, qc)),
            IdentitySampleAssessment("S2", None, qualifier_pair(channels, None, error="boom"), "boom"),
        ),
    )

    assert snapshot.for_sample("S1").qualifiers.v1.status is QualifierStatus.VALIDATED
    assert snapshot.for_sample("S2").qualifiers.v1.status is QualifierStatus.UNAVAILABLE
    with pytest.raises(KeyError, match="S3"):
        snapshot.for_sample("S3")
    with pytest.raises(ValueError, match="duplicate"):
        IdentityAssessmentSet(
            "Target",
            channels,
            (
                IdentitySampleAssessment("S1", qc, qualifier_pair(channels, qc)),
                IdentitySampleAssessment("S1", qc, qualifier_pair(channels, qc)),
            ),
        )


def test_qualifier_pair_indexes_by_ordinal_not_list_position():
    channels = (_qion(), _v2())
    pair = qualifier_pair(
        channels,
        _qc(channels, status=IdentityStatus.SUPPORTED, passed=(True,), observed=(0.21,)),
    )

    assert pair.v1.status is QualifierStatus.ABSENT
    assert pair.v2.status is QualifierStatus.VALIDATED
    assert pair.v2.channel is channels[1]


def test_assess_unlabelled_identities_keeps_sample_failures_in_the_snapshot(
    monkeypatch,
):
    channels = (_qion(), _v1())
    compound = SimpleNamespace(
        is_unlabelled_target=True,
        analysis_channels=channels,
    )
    qc = _qc(channels, status=IdentityStatus.SUPPORTED, passed=(True,), observed=(0.41,))

    def fake_read(name, sample=None):
        if name != "Target":
            raise LookupError(name)
        return compound

    monkeypatch.setattr(
        "manic.io.compound_reader.read_compound_with_session", fake_read
    )

    provider = DataProvider()

    def fake_assess(sample_name, compound_name):
        if sample_name == "broken":
            raise RuntimeError("EIC file is missing")
        return qc

    monkeypatch.setattr(provider, "assess_unlabelled_identity", fake_assess)

    snapshot = provider.assess_unlabelled_identities("Target", ["S1", "broken"])

    assert snapshot.compound_name == "Target"
    assert snapshot.channels == channels
    assert snapshot.for_sample("S1").qualifiers.v1.status is QualifierStatus.VALIDATED
    assert snapshot.for_sample("broken").error == "EIC file is missing"
    assert snapshot.for_sample("broken").qualifiers.v1.status is QualifierStatus.UNAVAILABLE
    assert snapshot.for_sample("broken").qualifiers.v2.status is QualifierStatus.ABSENT


def test_assess_unlabelled_identities_raises_when_compound_is_missing(monkeypatch):
    monkeypatch.setattr(
        "manic.io.compound_reader.read_compound_with_session",
        lambda *_args: (_ for _ in ()).throw(LookupError("Missing")),
    )
    with pytest.raises(LookupError, match="Missing"):
        DataProvider().assess_unlabelled_identities("Missing", ["S1"])
