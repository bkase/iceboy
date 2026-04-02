from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any


def _as_mapping(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise TypeError(f"Unsupported comparison value: {type(value)!r}")


def format_register_diff(expected: Any, actual: Any) -> str:
    expected_map = _as_mapping(expected)
    actual_map = _as_mapping(actual)
    lines = []
    for key in sorted(expected_map):
        if key not in actual_map:
            lines.append(f"{key}: missing in actual")
            continue
        if expected_map[key] != actual_map[key]:
            lines.append(f"{key}: expected={expected_map[key]!r} actual={actual_map[key]!r}")
    return "\n".join(lines) if lines else "no register differences"


def assert_registers_match(expected: Any, actual: Any, scope: str) -> None:
    diff = format_register_diff(expected, actual)
    if diff != "no register differences":
        raise AssertionError(f"{scope} register mismatch\n{diff}")


def assert_commit_trace_match(expected: Any, actual: Any, scope: str) -> None:
    expected_map = _as_mapping(expected)
    actual_map = _as_mapping(actual)
    mismatches = []
    for key, expected_value in expected_map.items():
        actual_value = actual_map.get(key, "<missing>")
        if expected_value != actual_value:
            mismatches.append(f"{key}: expected={expected_value!r} actual={actual_value!r}")
    if mismatches:
        raise AssertionError(f"{scope} commit trace mismatch\n" + "\n".join(mismatches))
