from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Sequence


class AnalysisMode(StrEnum):
    """Analytical workflow selected when MANIC starts."""

    LABELLED = "labelled"
    UNLABELLED = "unlabelled"

    @classmethod
    def coerce(cls, value: AnalysisMode | str | None) -> AnalysisMode:
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.LABELLED
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:
            raise ValueError(f"Unsupported analysis mode: {value!r}") from exc

    @property
    def display_name(self) -> str:
        return "Labelled" if self is self.LABELLED else "Unlabelled"


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Immutable session-wide analysis configuration."""

    mode: AnalysisMode = AnalysisMode.LABELLED

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", AnalysisMode.coerce(self.mode))


class IonRole(StrEnum):
    QUANTIFIER = "quantifier"
    QUALIFIER = "qualifier"
    ISOTOPOLOGUE = "isotopologue"


@dataclass(frozen=True, slots=True)
class IonChannel:
    mz: float
    role: IonRole
    ordinal: int = 0
    expected_ratio: float | None = None
    ratio_tolerance: float | None = None

    @property
    def label(self) -> str:
        if self.role is IonRole.QUANTIFIER:
            return f"Quantifier m/z {self.mz:g}"
        if self.role is IonRole.QUALIFIER:
            return f"Qualifier {self.ordinal} m/z {self.mz:g}"
        return f"M+{self.ordinal} m/z {self.mz:g}"


def labelled_channels(mass0: float, label_atoms: int) -> tuple[IonChannel, ...]:
    """Build the existing consecutive M+0...M+n channel definition."""

    count = max(0, int(label_atoms or 0)) + 1
    return tuple(
        IonChannel(
            mz=float(mass0) + index,
            role=IonRole.ISOTOPOLOGUE,
            ordinal=index,
        )
        for index in range(count)
    )


def validate_unlabelled_channels(
    channels: Sequence[IonChannel] | Iterable[IonChannel],
) -> tuple[IonChannel, ...]:
    """Return channels in analysis order after validating target-ion roles."""

    ordered = tuple(
        sorted(
            channels,
            key=lambda channel: (
                0 if channel.role is IonRole.QUANTIFIER else 1,
                channel.ordinal,
            ),
        )
    )
    quantifiers = [c for c in ordered if c.role is IonRole.QUANTIFIER]
    qualifiers = [c for c in ordered if c.role is IonRole.QUALIFIER]
    if len(quantifiers) != 1:
        raise ValueError("Unlabelled compounds require exactly one quantifier ion")
    if not qualifiers:
        raise ValueError("Unlabelled compounds require at least one qualifier ion")
    if len({float(c.mz) for c in ordered}) != len(ordered):
        raise ValueError("Quantifier and qualifier m/z values must be distinct")
    for channel in ordered:
        if channel.mz <= 0:
            raise ValueError("Ion m/z values must be positive")
        if channel.ratio_tolerance is not None and channel.ratio_tolerance < 0:
            raise ValueError("Qualifier ratio tolerances cannot be negative")
    return ordered
