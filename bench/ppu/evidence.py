from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Generic, Iterable, TypeVar


T = TypeVar("T")


class _StringEnum(str, Enum):
    pass


class EvidenceSourceKind(_StringEnum):
    PAN_DOCS = "PanDocs"
    MOONEYE_TEST = "MooneyeTest"
    MEALYBUG_TEST = "MealybugTest"
    HARDWARE_CAPTURE = "HardwareCapture"
    HYPOTHESIS = "Hypothesis"


class EvidenceConfidence(_StringEnum):
    EXACT = "Exact"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    UNKNOWN = "Unknown"


class EvidenceRuleStrength(_StringEnum):
    ARCHITECTURAL = "Architectural"
    EMPIRICAL = "Empirical"
    INFERRED = "Inferred"


class CompareSurface(_StringEnum):
    DOT_COMMIT = "DotCommit"
    SCANLINE_SUMMARY = "ScanlineSummary"
    FRAME_HASH = "FrameHash"
    REFERENCE_IMAGE = "ReferenceImage"


@dataclass(frozen=True)
class EvidenceTag:
    source_kind: EvidenceSourceKind
    confidence: EvidenceConfidence
    rule_strength: EvidenceRuleStrength
    affected_surface: CompareSurface
    note: str

    def __post_init__(self) -> None:
        if not self.note.strip():
            raise ValueError("EvidenceTag.note must be non-empty")


class ExpectedSemantics(ABC, Generic[T]):
    @abstractmethod
    def matches(self, actual: T) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class Exact(ExpectedSemantics[T]):
    value: T

    def matches(self, actual: T) -> bool:
        return actual == self.value


@dataclass(frozen=True)
class OneOf(ExpectedSemantics[T]):
    options: tuple[T, ...]

    def __init__(self, options: Iterable[T]) -> None:
        normalized = tuple(options)
        if not normalized:
            raise ValueError("OneOf requires at least one option")
        object.__setattr__(self, "options", normalized)

    def matches(self, actual: T) -> bool:
        return actual in self.options


@dataclass(frozen=True)
class MaskedBits(ExpectedSemantics[int]):
    value: int
    mask: int

    def __post_init__(self) -> None:
        if self.value < 0 or self.mask < 0:
            raise ValueError("MaskedBits requires non-negative value and mask")

    def matches(self, actual: int) -> bool:
        return (actual & self.mask) == (self.value & self.mask)


@dataclass(frozen=True)
class DontCare(ExpectedSemantics[T]):
    def matches(self, actual: T) -> bool:
        return True


@dataclass(frozen=True)
class Hypothesis(ExpectedSemantics[T]):
    value: T

    def matches(self, actual: T) -> bool:
        return actual == self.value


__all__ = [
    "CompareSurface",
    "DontCare",
    "EvidenceConfidence",
    "EvidenceRuleStrength",
    "EvidenceSourceKind",
    "EvidenceTag",
    "Exact",
    "ExpectedSemantics",
    "Hypothesis",
    "MaskedBits",
    "OneOf",
]
