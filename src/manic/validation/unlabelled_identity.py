from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Iterator, Literal, Mapping, Sequence

import numpy as np

from manic.models.analysis import IonChannel, IonRole


class IdentityStatus(StrEnum):
    SUPPORTED = "supported"
    REVIEW_REQUIRED = "review_required"
    NOT_DETECTED = "not_detected"
    NOT_ASSESSED = "not_assessed"


@dataclass(frozen=True, slots=True)
class QualifierRatioResult:
    channel: IonChannel
    observed_ratio: float | None
    passed: bool | None


@dataclass(frozen=True, slots=True)
class IdentityQcResult:
    status: IdentityStatus
    quantifier_area: float
    observed_rt: float | None
    rt_error: float | None
    rt_passed: bool | None
    qualifier_ratios: tuple[QualifierRatioResult, ...]
    reasons: tuple[str, ...]


class QualifierStatus(StrEnum):
    ABSENT = "absent"
    VALIDATED = "validated"
    FAILED = "failed"
    NOT_ASSESSED = "not_assessed"
    UNAVAILABLE = "unavailable"


QualifierOrdinal = Literal[1, 2]


def _format_ratio(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"


def _format_tolerance(tolerance: float | None, expected: float | None) -> str:
    if tolerance is None:
        return "—"
    if expected in (None, 0):
        return f"±{tolerance:g}"
    return f"±{tolerance:.0%}"


def _ratio_detail(ratio: QualifierRatioResult) -> str:
    channel = ratio.channel
    expected = channel.expected_ratio
    label = f"V{channel.ordinal}" if channel.ordinal else "V"
    return (
        f"{label}  expected {_format_ratio(expected)}  "
        f"{_format_tolerance(channel.ratio_tolerance, expected)}  "
        f"observed {_format_ratio(ratio.observed_ratio)}"
    )


@dataclass(frozen=True, slots=True)
class QualifierAssessment:
    ordinal: QualifierOrdinal
    status: QualifierStatus
    channel: IonChannel | None
    ratio: QualifierRatioResult | None
    detail: str

    @classmethod
    def absent(cls, ordinal: QualifierOrdinal) -> QualifierAssessment:
        return cls(
            ordinal=ordinal,
            status=QualifierStatus.ABSENT,
            channel=None,
            ratio=None,
            detail="not in the method",
        )

    @classmethod
    def unavailable(
        cls,
        ordinal: QualifierOrdinal,
        channel: IonChannel,
        error: str,
    ) -> QualifierAssessment:
        return cls(
            ordinal=ordinal,
            status=QualifierStatus.UNAVAILABLE,
            channel=channel,
            ratio=None,
            detail=error or "Could not compute identity",
        )

    @classmethod
    def from_ratio(
        cls,
        ordinal: QualifierOrdinal,
        ratio: QualifierRatioResult,
        qc: IdentityQcResult,
    ) -> QualifierAssessment:
        if ratio.passed is True:
            status = QualifierStatus.VALIDATED
            detail = _ratio_detail(ratio)
        elif ratio.passed is False:
            status = QualifierStatus.FAILED
            detail = _ratio_detail(ratio)
        elif qc.status is IdentityStatus.NOT_DETECTED:
            status = QualifierStatus.NOT_ASSESSED
            detail = "Q ion was not detected; ratio was not assessed"
        else:
            status = QualifierStatus.NOT_ASSESSED
            detail = "expected ratio or tolerance is missing"
        return cls(
            ordinal=ordinal,
            status=status,
            channel=ratio.channel,
            ratio=ratio,
            detail=detail,
        )


@dataclass(frozen=True, slots=True)
class QualifierPair:
    v1: QualifierAssessment
    v2: QualifierAssessment

    def __iter__(self) -> Iterator[QualifierAssessment]:
        yield self.v1
        yield self.v2

    def for_ordinal(self, ordinal: QualifierOrdinal) -> QualifierAssessment:
        if ordinal == 1:
            return self.v1
        if ordinal == 2:
            return self.v2
        raise ValueError(f"Qualifier ordinal must be 1 or 2, got {ordinal!r}")


@dataclass(frozen=True, slots=True)
class IdentitySampleAssessment:
    sample_name: str
    qc: IdentityQcResult | None
    qualifiers: QualifierPair
    error: str | None = None


@dataclass(frozen=True, slots=True)
class IdentityAssessmentSet:
    compound_name: str
    channels: tuple[IonChannel, ...]
    samples: tuple[IdentitySampleAssessment, ...]
    _by_sample: Mapping[str, IdentitySampleAssessment] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        names = [sample.sample_name for sample in self.samples]
        if len(names) != len(set(names)):
            raise ValueError("Identity snapshot contains duplicate sample names")
        object.__setattr__(
            self,
            "_by_sample",
            MappingProxyType({sample.sample_name: sample for sample in self.samples}),
        )

    def for_sample(self, sample_name: str) -> IdentitySampleAssessment:
        try:
            return self._by_sample[sample_name]
        except KeyError as exc:
            raise KeyError(
                f"{sample_name!r} is not in the identity snapshot for "
                f"{self.compound_name!r}"
            ) from exc


def qualifier_pair(
    channels: Sequence[IonChannel],
    qc: IdentityQcResult | None,
    *,
    error: str | None = None,
) -> QualifierPair:
    channels_by_ordinal = {
        channel.ordinal: channel
        for channel in channels
        if channel.role is IonRole.QUALIFIER
    }
    ratios_by_ordinal = {
        ratio.channel.ordinal: ratio
        for ratio in (qc.qualifier_ratios if qc is not None else ())
    }

    def _slot(ordinal: QualifierOrdinal) -> QualifierAssessment:
        channel = channels_by_ordinal.get(ordinal)
        if channel is None:
            return QualifierAssessment.absent(ordinal)
        if error is not None:
            return QualifierAssessment.unavailable(ordinal, channel, error)
        ratio = ratios_by_ordinal.get(ordinal)
        if ratio is None:
            return QualifierAssessment.unavailable(
                ordinal,
                channel,
                "Identity result did not include this qualifier",
            )
        return QualifierAssessment.from_ratio(ordinal, ratio, qc)

    return QualifierPair(v1=_slot(1), v2=_slot(2))


def _ratio_passes(observed: float, expected: float, tolerance: float) -> bool:
    """Compare qualifier/QIon ratios using a fractional tolerance."""

    allowed_error = tolerance if expected == 0 else abs(expected) * tolerance
    return abs(observed - expected) <= allowed_error


def quantifier_apex_time(
    time: Sequence[float],
    intensity: Sequence[float] | np.ndarray,
    channel_count: int,
    *,
    expected_rt: float | None = None,
    loffset: float | None = None,
    roffset: float | None = None,
) -> float | None:
    """Return the quantifier apex inside the integration window."""

    time_array = np.asarray(time, dtype=np.float64)
    intensity_array = np.asarray(intensity, dtype=np.float64)
    if time_array.size == 0 or intensity_array.size == 0:
        return None
    try:
        matrix = intensity_array.reshape(max(1, int(channel_count)), time_array.size)
    except ValueError:
        return None

    mask = np.ones(time_array.size, dtype=bool)
    if expected_rt is not None and loffset is not None and roffset is not None:
        mask = (
            (time_array >= float(expected_rt) - float(loffset))
            & (time_array <= float(expected_rt) + float(roffset))
        )
    if not np.any(mask):
        return None

    candidate_indices = np.flatnonzero(mask)
    apex_index = candidate_indices[int(np.argmax(matrix[0, mask]))]
    if matrix[0, apex_index] <= 0:
        return None
    return float(time_array[apex_index])


def assess_identity(
    areas: Sequence[float],
    channels: Sequence[IonChannel],
    *,
    expected_rt: float | None,
    observed_rt: float | None,
    rt_tolerance: float | None,
    quantifier_floor: float = 0.0,
) -> IdentityQcResult:
    """Assess targeted identity without claiming library-spectrum confirmation."""

    channels_tuple = tuple(channels)
    if not channels_tuple or channels_tuple[0].role is not IonRole.QUANTIFIER:
        raise ValueError("The first analysis channel must be the quantifier ion")
    if len(areas) != len(channels_tuple):
        raise ValueError("Area and channel counts do not match")

    quantifier_area = float(areas[0])
    if quantifier_area <= quantifier_floor:
        return IdentityQcResult(
            status=IdentityStatus.NOT_DETECTED,
            quantifier_area=quantifier_area,
            observed_rt=observed_rt,
            rt_error=None,
            rt_passed=None,
            qualifier_ratios=tuple(
                QualifierRatioResult(channel, None, None)
                for channel in channels_tuple[1:]
            ),
            reasons=("Q ion was not detected above the assessment floor",),
        )

    reasons: list[str] = []
    rt_error: float | None = None
    rt_passed: bool | None = None
    if (
        expected_rt is not None
        and observed_rt is not None
        and rt_tolerance is not None
    ):
        rt_error = float(observed_rt) - float(expected_rt)
        rt_passed = abs(rt_error) <= float(rt_tolerance)
        if not rt_passed:
            reasons.append(
                f"Retention-time error {rt_error:+.3f} min exceeds "
                f"±{float(rt_tolerance):.3f} min"
            )

    ratio_results: list[QualifierRatioResult] = []
    for index, channel in enumerate(channels_tuple[1:], start=1):
        observed_ratio = float(areas[index]) / quantifier_area
        passed: bool | None = None
        if (
            channel.expected_ratio is not None
            and channel.ratio_tolerance is not None
        ):
            passed = _ratio_passes(
                observed_ratio,
                float(channel.expected_ratio),
                float(channel.ratio_tolerance),
            )
            if not passed:
                reasons.append(
                    f"V ion {channel.ordinal} ratio {observed_ratio:.3f} "
                    f"is outside {channel.expected_ratio:.3f} "
                    f"±{channel.ratio_tolerance:.0%}"
                )
        ratio_results.append(
            QualifierRatioResult(channel, observed_ratio, passed)
        )

    assessed = rt_passed is not None and all(
        result.passed is not None for result in ratio_results
    )
    failed = rt_passed is False or any(
        result.passed is False for result in ratio_results
    )
    if failed:
        status = IdentityStatus.REVIEW_REQUIRED
    elif assessed:
        status = IdentityStatus.SUPPORTED
    else:
        status = IdentityStatus.NOT_ASSESSED
        reasons.append(
            "Identity references are incomplete; signal is reported without confirmation"
        )

    return IdentityQcResult(
        status=status,
        quantifier_area=quantifier_area,
        observed_rt=observed_rt,
        rt_error=rt_error,
        rt_passed=rt_passed,
        qualifier_ratios=tuple(ratio_results),
        reasons=tuple(reasons),
    )
