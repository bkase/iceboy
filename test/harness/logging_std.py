from __future__ import annotations

import json
from argparse import ArgumentParser, Namespace
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Mapping


LOG_LEVEL_RANK = {
    "QUIET": 0,
    "NORMAL": 1,
    "VERBOSE": 2,
    "TRACE": 3,
}

EVENT_LEVEL = {
    "SUITE": "NORMAL",
    "CASE": "NORMAL",
    "STEP": "NORMAL",
    "CHECK": "NORMAL",
    "PASS": "NORMAL",
    "FAIL": "QUIET",
    "CONTEXT": "QUIET",
    "SUMMARY": "QUIET",
}

COLOR_CODES = {
    "PASS": "\033[0;32m",
    "FAIL": "\033[0;31m",
    "SUMMARY": "\033[0;33m",
}
COLOR_RESET = "\033[0m"


@dataclass(frozen=True)
class FailureArtifacts:
    divergent_field: str | None = None
    waveform_path: str | Path | None = None
    replay_capsule: str | Path | None = None
    instruction_context: str | None = None
    expected: str | None = None
    actual: str | None = None


def add_logging_args(parser: ArgumentParser) -> ArgumentParser:
    parser.add_argument(
        "--log-level",
        choices=tuple(LOG_LEVEL_RANK),
        default="NORMAL",
        help="Logging verbosity for test diagnostics.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-parseable JSON log lines.",
    )
    return parser


def logger_from_args(
    args: Namespace,
    *,
    suite_name: str,
    stream: IO[str],
    case_name: str | None = None,
    color: bool | None = None,
) -> "TestLogger":
    return TestLogger(
        suite_name=suite_name,
        case_name=case_name,
        stream=stream,
        level=str(args.log_level),
        json_mode=bool(args.json),
        color=color,
    )


class TestLogger:
    def __init__(
        self,
        *,
        suite_name: str,
        stream: IO[str],
        case_name: str | None = None,
        level: str = "NORMAL",
        json_mode: bool = False,
        color: bool | None = None,
    ) -> None:
        if level not in LOG_LEVEL_RANK:
            raise ValueError(f"Unsupported log level: {level}")
        self.suite_name = suite_name
        self.case_name = case_name
        self.stream = stream
        self.level = level
        self.json_mode = json_mode
        self.color = self._resolve_color(color)

    def _resolve_color(self, color: bool | None) -> bool:
        if color is not None:
            return color
        if self.json_mode:
            return False
        isatty = getattr(self.stream, "isatty", None)
        return bool(isatty and isatty())

    def bind_case(self, case_name: str) -> "TestLogger":
        bound = TestLogger(
            suite_name=self.suite_name,
            case_name=case_name,
            stream=self.stream,
            level=self.level,
            json_mode=self.json_mode,
            color=self.color,
        )
        bound.case(case_name)
        return bound

    def suite(self) -> None:
        self._emit("SUITE", self.suite_name)

    def case(self, case_name: str) -> None:
        self.case_name = case_name
        self._emit("CASE", case_name)

    def step(self, message: str) -> None:
        self._emit("STEP", message)

    def check(self, label: str, *, expected: object, actual: object) -> bool:
        ok = expected == actual
        detail = f"{label}: expected={expected} actual={actual} {'OK' if ok else 'FAIL'}"
        self._emit("CHECK", detail if ok else detail, force=not ok)
        return ok

    def context(self, label: str, value: object) -> None:
        self._emit("CONTEXT", f"{label}: {value}", force=True)

    def pass_case(self, duration_s: float) -> None:
        case_name = self.case_name or self.suite_name
        self._emit("PASS", f"{case_name} ({duration_s:.3f}s)")

    def fail_case(
        self,
        message: str,
        *,
        duration_s: float | None = None,
        contexts: Mapping[str, object] | None = None,
        artifacts: FailureArtifacts | None = None,
    ) -> None:
        case_name = self.case_name or self.suite_name
        suffix = f" ({duration_s:.3f}s)" if duration_s is not None else ""
        self._emit("FAIL", f"{case_name} -- {message}{suffix}", force=True)
        for label, value in (contexts or {}).items():
            self.context(label, value)
        if artifacts is not None:
            for label, value in asdict(artifacts).items():
                if value is not None:
                    self.context(label, value)

    def summary(self, *, passed: int, failed: int, duration_s: float) -> None:
        total = passed + failed
        self._emit(
            "SUMMARY",
            f"{self.suite_name}: {passed}/{total} passed, {failed} failed ({duration_s:.2f}s)",
            force=True,
        )

    def _emit(self, event: str, message: str, *, force: bool = False) -> None:
        if not force and LOG_LEVEL_RANK[self.level] < LOG_LEVEL_RANK[EVENT_LEVEL[event]]:
            return
        if self.json_mode:
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "event": event.lower(),
                "suite": self.suite_name,
                "case": self.case_name,
                "message": message,
            }
            self.stream.write(json.dumps(payload) + "\n")
            return

        label = f"[{event}]"
        if self.color and event in COLOR_CODES:
            label = f"{COLOR_CODES[event]}{label}{COLOR_RESET}"
        self.stream.write(f"{label} {message}\n")
