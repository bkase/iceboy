from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Sequence


class PpuCompareScope(str, Enum):
    DotCommit = "dot_commit"
    ScanlineSummary = "scanline_summary"
    FrameHash = "frame_hash"


@dataclass(frozen=True)
class OracleComparisonResult:
    matched: bool
    scope: PpuCompareScope
    first_bad_index: int | None
    field_path: str | None
    expected: Any
    actual: Any
    last_matching_index: int | None


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _normalize(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _first_diff(expected: Any, actual: Any, prefix: str = "") -> tuple[str | None, Any, Any]:
    expected = _normalize(expected)
    actual = _normalize(actual)
    if expected == actual:
        return (None, None, None)
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            child_prefix = f"{prefix}.{key}" if prefix else key
            if key not in expected:
                return (child_prefix, None, actual[key])
            if key not in actual:
                return (child_prefix, expected[key], None)
            path, child_expected, child_actual = _first_diff(expected[key], actual[key], child_prefix)
            if path is not None:
                return (path, child_expected, child_actual)
    if isinstance(expected, list) and isinstance(actual, list):
        for index, (left, right) in enumerate(zip(expected, actual)):
            child_prefix = f"{prefix}[{index}]"
            path, child_expected, child_actual = _first_diff(left, right, child_prefix)
            if path is not None:
                return (path, child_expected, child_actual)
        if len(expected) != len(actual):
            return (f"{prefix}.length" if prefix else "length", len(expected), len(actual))
    return (prefix or "value", expected, actual)


def compare_oracle_streams(
    expected_name: str,
    expected_stream: Sequence[Any],
    actual_name: str,
    actual_stream: Sequence[Any],
    scope: PpuCompareScope,
) -> OracleComparisonResult:
    last_matching_index = None
    for index, (expected, actual) in enumerate(zip(expected_stream, actual_stream)):
        path, expected_value, actual_value = _first_diff(expected, actual)
        if path is not None:
            return OracleComparisonResult(
                matched=False,
                scope=scope,
                first_bad_index=index,
                field_path=path,
                expected={expected_name: expected_value},
                actual={actual_name: actual_value},
                last_matching_index=last_matching_index,
            )
        last_matching_index = index

    if len(expected_stream) != len(actual_stream):
        return OracleComparisonResult(
            matched=False,
            scope=scope,
            first_bad_index=min(len(expected_stream), len(actual_stream)),
            field_path="length",
            expected={expected_name: len(expected_stream)},
            actual={actual_name: len(actual_stream)},
            last_matching_index=last_matching_index,
        )

    return OracleComparisonResult(
        matched=True,
        scope=scope,
        first_bad_index=None,
        field_path=None,
        expected=None,
        actual=None,
        last_matching_index=last_matching_index,
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Compare two serialized oracle streams.")
    parser.add_argument("expected")
    parser.add_argument("actual")
    parser.add_argument("--scope", choices=[scope.value for scope in PpuCompareScope], default=PpuCompareScope.DotCommit.value)
    args = parser.parse_args()

    expected = json.loads(Path(args.expected).read_text(encoding="utf-8"))
    actual = json.loads(Path(args.actual).read_text(encoding="utf-8"))
    result = compare_oracle_streams("expected", expected, "actual", actual, PpuCompareScope(args.scope))
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0 if result.matched else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
