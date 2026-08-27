from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

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
