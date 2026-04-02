"""Comparison utilities for DUT traces against oracle commits."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any, Iterable

from spec.compare_scopes import CompareField


_UNAVAILABLE = object()


@dataclass(frozen=True)
class FieldDiff:
    field: CompareField
    expected: Any
    actual: Any
    detail: str


@dataclass(frozen=True)
class CompareResult:
    matched: bool
    compared_fields: tuple[CompareField, ...]
    diffs: tuple[FieldDiff, ...]
    first_divergent_field: CompareField | None = None


def compare_commit(dut_trace: Any, oracle_state: Any, scope: Iterable[CompareField]) -> CompareResult:
    ordered_fields = tuple(scope)
    diffs = []
    for field in ordered_fields:
        actual = _extract_field_value(dut_trace, field, side="dut")
        expected = _extract_field_value(oracle_state, field, side="oracle")
        if actual == expected:
            continue
        detail = _format_detail(field=field, expected=expected, actual=actual)
        diffs.append(FieldDiff(field=field, expected=expected, actual=actual, detail=detail))

    return CompareResult(
        matched=not diffs,
        compared_fields=ordered_fields,
        diffs=tuple(diffs),
        first_divergent_field=diffs[0].field if diffs else None,
    )


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _normalize(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_normalize(item) for item in value)
    return value


def _extract_registers(value: Any) -> Any:
    registers = getattr(value, "registers_after", None)
    if registers is not None:
        return _normalize(registers)
    keys = ("a", "f", "b", "c", "d", "e", "hl", "sp", "pc")
    if all(hasattr(value, key) for key in keys):
        return {key: _normalize(getattr(value, key)) for key in keys}
    return _UNAVAILABLE


def _extract_field_value(value: Any, field: CompareField, *, side: str) -> Any:
    if field is CompareField.TargetValue:
        return _normalize(value)
    if field is CompareField.Registers:
        return _extract_registers(value)
    if field is CompareField.Flags:
        registers = getattr(value, "registers_after", None)
        if registers is not None and hasattr(registers, "f"):
            return int(registers.f)
        if hasattr(value, "f"):
            return int(value.f)
        return _UNAVAILABLE
    if field is CompareField.ProgramCounter:
        registers = getattr(value, "registers_after", None)
        if registers is not None and hasattr(registers, "pc"):
            return int(registers.pc)
        if hasattr(value, "pc"):
            return int(value.pc)
        if hasattr(value, "pc_before"):
            return int(value.pc_before)
        return _UNAVAILABLE
    if field is CompareField.StackPointer:
        registers = getattr(value, "registers_after", None)
        if registers is not None and hasattr(registers, "sp"):
            return int(registers.sp)
        if hasattr(value, "sp"):
            return int(value.sp)
        return _UNAVAILABLE
    if field is CompareField.ImeState:
        for name in ("ime_enabled", "ime_state", "ime"):
            if hasattr(value, name):
                return bool(getattr(value, name))
        return _UNAVAILABLE
    if field is CompareField.BusRequest:
        if hasattr(value, "bus_request"):
            return _normalize(getattr(value, "bus_request"))
        return _UNAVAILABLE
    if field is CompareField.BusResponse:
        if hasattr(value, "bus_response"):
            return _normalize(getattr(value, "bus_response"))
        if hasattr(value, "bus_read_data"):
            return {"kind": "data", "data": int(getattr(value, "bus_read_data"))}
        return _UNAVAILABLE
    if field is CompareField.CheckpointTag:
        if hasattr(value, "label"):
            return getattr(value, "label")
        return _UNAVAILABLE
    if field is CompareField.IoTouch and side == "dut" and hasattr(value, "irq_pending"):
        return {"irq_pending": int(getattr(value, "irq_pending"))}
    return _UNAVAILABLE


def _format_detail(*, field: CompareField, expected: Any, actual: Any) -> str:
    if expected is _UNAVAILABLE:
        return f"{field.value}: unavailable on oracle"
    if actual is _UNAVAILABLE:
        return f"{field.value}: unavailable on dut"
    return f"{field.value}: expected={expected!r} actual={actual!r}"
