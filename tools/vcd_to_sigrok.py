from __future__ import annotations

import argparse
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_SIGNALS = ("LCD_SCK", "LCD_MOSI", "LCD_CS", "LCD_DC")

_TIMESCALE_TO_PS = {
    "s": 1_000_000_000_000,
    "ms": 1_000_000_000,
    "us": 1_000_000,
    "ns": 1_000,
    "ps": 1,
    "fs": 0,
}


@dataclass(frozen=True)
class SignalDef:
    symbol: str
    path: str
    width: int


@dataclass(frozen=True)
class SignalTrace:
    name: str
    path: str
    events: tuple[tuple[int, bool], ...]
    initial: bool


@dataclass(frozen=True)
class Capture:
    samplerate_hz: int
    sample_period_ps: int
    duration_ps: int
    unit_size: int
    traces: tuple[SignalTrace, ...]
    samples: bytes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a logic VCD into a sigrok .sr session.")
    parser.add_argument("--vcd", type=Path, required=True, help="input VCD path")
    parser.add_argument("--out", type=Path, required=True, help="output .sr path")
    parser.add_argument(
        "--signals",
        default=",".join(DEFAULT_SIGNALS),
        help="comma-separated signal names or full VCD paths to export",
    )
    parser.add_argument(
        "--samplerate-hz",
        type=int,
        help="override the inferred output sample rate",
    )
    return parser.parse_args()


def parse_signal_list(raw: str) -> tuple[str, ...]:
    parts = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not parts:
        raise ValueError("at least one signal must be selected")
    return parts


def parse_timescale_to_ps(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        pending = False
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if pending:
                if line == "$end":
                    continue
                return _parse_timescale_token(line)
            if line.startswith("$timescale"):
                body = line[len("$timescale") :].replace("$end", "").strip()
                if body:
                    return _parse_timescale_token(body)
                pending = True
    raise ValueError(f"no $timescale found in {path}")


def _parse_timescale_token(token: str) -> int:
    text = token.replace(" ", "")
    digits = []
    unit_chars = []
    for ch in text:
        if ch.isdigit():
            digits.append(ch)
        else:
            unit_chars.append(ch)
    if not digits or not unit_chars:
        raise ValueError(f"unsupported VCD timescale token: {token!r}")
    magnitude = int("".join(digits))
    unit = "".join(unit_chars).lower()
    scale_ps = _TIMESCALE_TO_PS.get(unit)
    if scale_ps is None:
        raise ValueError(f"unsupported VCD timescale unit: {unit}")
    if scale_ps == 0:
        raise ValueError("femtosecond VCD timescale is not supported")
    return magnitude * scale_ps


def parse_signal_defs(path: Path) -> dict[str, SignalDef]:
    scope: list[str] = []
    defs: dict[str, SignalDef] = {}
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("$scope"):
                parts = line.split()
                if len(parts) >= 4:
                    scope.append(parts[2])
                continue
            if line.startswith("$upscope"):
                if scope:
                    scope.pop()
                continue
            if line.startswith("$var"):
                parts = line.split()
                if len(parts) < 5:
                    continue
                width = int(parts[2])
                symbol = parts[3]
                name = parts[4]
                defs[symbol] = SignalDef(symbol=symbol, path=".".join(scope + [name]), width=width)
                continue
            if line.startswith("$enddefinitions"):
                break
    if not defs:
        raise ValueError(f"no signal definitions found in {path}")
    return defs


def resolve_signals(signal_defs: dict[str, SignalDef], requested: Iterable[str]) -> tuple[SignalDef, ...]:
    defs = tuple(signal_defs.values())
    resolved: list[SignalDef] = []
    for name in requested:
        exact = [item for item in defs if item.path == name]
        if exact:
            candidate = exact[0]
        else:
            leaf_matches = [item for item in defs if item.path.split(".")[-1] == name]
            if len(leaf_matches) != 1:
                suffix_matches = [item for item in defs if item.path.endswith(f".{name}")]
                if len(suffix_matches) == 1:
                    candidate = suffix_matches[0]
                elif len(leaf_matches) > 1:
                    raise ValueError(f"ambiguous signal name {name!r}; use a full VCD path")
                else:
                    raise ValueError(f"signal {name!r} not found in VCD")
            else:
                candidate = leaf_matches[0]
        if candidate.width != 1:
            raise ValueError(f"signal {candidate.path!r} has width {candidate.width}; only 1-bit signals are supported")
        resolved.append(candidate)
    return tuple(resolved)


def parse_signal_traces(path: Path, selected: tuple[SignalDef, ...], *, tick_ps: int) -> tuple[int, tuple[SignalTrace, ...]]:
    selected_by_symbol = {item.symbol: item for item in selected}
    current_time = 0
    end_time = 0
    current_values: dict[str, bool] = {item.symbol: False for item in selected}
    seen_initial: set[str] = set()
    events: dict[str, list[tuple[int, bool]]] = {item.symbol: [] for item in selected}

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                current_time = int(line[1:]) * tick_ps
                end_time = max(end_time, current_time)
                continue
            if line.startswith("$"):
                continue
            if line[0] in "01xXzZ":
                symbol = line[1:]
                item = selected_by_symbol.get(symbol)
                if item is None:
                    continue
                value = line[0] == "1"
            elif line[0] in "bB":
                parts = line.split()
                if len(parts) != 2:
                    continue
                symbol = parts[1]
                item = selected_by_symbol.get(symbol)
                if item is None:
                    continue
                bit_text = parts[0][1:].strip().lower()
                if not bit_text:
                    continue
                value = bit_text[-1] == "1"
            else:
                continue

            previous = current_values[symbol]
            current_values[symbol] = value
            if symbol not in seen_initial:
                seen_initial.add(symbol)
                events[symbol].append((current_time, value))
            elif value != previous:
                events[symbol].append((current_time, value))

    traces = tuple(
        SignalTrace(
            name=item.path.split(".")[-1],
            path=item.path,
            events=tuple(events[item.symbol]),
            initial=events[item.symbol][0][1] if events[item.symbol] else False,
        )
        for item in selected
    )
    return end_time, traces


def infer_sample_period_ps(duration_ps: int, traces: tuple[SignalTrace, ...]) -> int:
    deltas: list[int] = []
    times = sorted({time_ps for trace in traces for time_ps, _ in trace.events if time_ps > 0})
    previous = 0
    for time_ps in times:
        if time_ps > previous:
            deltas.append(time_ps - previous)
        previous = time_ps
    if duration_ps > previous:
        deltas.append(duration_ps - previous)
    positive = [delta for delta in deltas if delta > 0]
    if not positive:
        return 1
    return min(positive)


def samplerate_to_period_ps(samplerate_hz: int) -> int:
    if samplerate_hz <= 0:
        raise ValueError("samplerate must be positive")
    numerator = 1_000_000_000_000
    if numerator % samplerate_hz != 0:
        raise ValueError("samplerate must divide 1e12 exactly to produce an integer picosecond period")
    return numerator // samplerate_hz


def build_samples(traces: tuple[SignalTrace, ...], *, duration_ps: int, sample_period_ps: int) -> tuple[bytes, int]:
    if sample_period_ps <= 0:
        raise ValueError("sample period must be positive")
    unitsize = max(1, math.ceil(len(traces) / 8))
    sample_count = max(1, (duration_ps // sample_period_ps) + 1)
    if sample_count > 25_000_000:
        raise ValueError("capture would exceed 25,000,000 samples; provide a coarser samplerate override")

    indices = [0 for _ in traces]
    values = [trace.initial for trace in traces]
    samples = bytearray(sample_count * unitsize)

    for sample_index in range(sample_count):
        time_ps = sample_index * sample_period_ps
        for signal_index, trace in enumerate(traces):
            while indices[signal_index] + 1 < len(trace.events) and trace.events[indices[signal_index] + 1][0] <= time_ps:
                indices[signal_index] += 1
                values[signal_index] = trace.events[indices[signal_index]][1]
            if values[signal_index]:
                byte_index = signal_index // 8
                bit_index = 7 - (signal_index % 8)
                samples[(sample_index * unitsize) + byte_index] |= 1 << bit_index

    return bytes(samples), unitsize


def infer_samplerate_hz(sample_period_ps: int) -> int:
    if sample_period_ps <= 0:
        raise ValueError("sample period must be positive")
    numerator = 1_000_000_000_000
    if numerator % sample_period_ps != 0:
        raise ValueError("sample period must divide 1e12 exactly to produce an integer samplerate")
    return numerator // sample_period_ps


def format_samplerate_hz(samplerate_hz: int) -> str:
    units = (
        ("GHz", 1_000_000_000),
        ("MHz", 1_000_000),
        ("kHz", 1_000),
        ("Hz", 1),
    )
    for suffix, scale in units:
        if samplerate_hz % scale == 0:
            value = samplerate_hz // scale
            if scale == 1:
                return f"{value} {suffix}"
            if value >= 1:
                return f"{value} {suffix}"
    return f"{samplerate_hz} Hz"


def build_capture(vcd_path: Path, *, requested_signals: tuple[str, ...], samplerate_hz: int | None) -> Capture:
    tick_ps = parse_timescale_to_ps(vcd_path)
    signal_defs = parse_signal_defs(vcd_path)
    selected = resolve_signals(signal_defs, requested_signals)
    duration_ps, traces = parse_signal_traces(vcd_path, selected, tick_ps=tick_ps)
    if samplerate_hz is None:
        sample_period_ps = infer_sample_period_ps(duration_ps, traces)
        samplerate_hz = infer_samplerate_hz(sample_period_ps)
    else:
        sample_period_ps = samplerate_to_period_ps(samplerate_hz)
    samples, unit_size = build_samples(traces, duration_ps=duration_ps, sample_period_ps=sample_period_ps)
    return Capture(
        samplerate_hz=samplerate_hz,
        sample_period_ps=sample_period_ps,
        duration_ps=duration_ps,
        unit_size=unit_size,
        traces=traces,
        samples=samples,
    )


def build_metadata(capture: Capture) -> str:
    lines = [
        "[global]",
        "sigrok version=iceboy-vcd_to_sigrok",
        "",
        "[device 1]",
        "capturefile=logic-1",
        f"total probes={len(capture.traces)}",
        "total analog=0",
        f"samplerate={format_samplerate_hz(capture.samplerate_hz)}",
        f"unitsize={capture.unit_size}",
    ]
    for index, trace in enumerate(capture.traces, start=1):
        lines.append(f"probe{index}={trace.name}")
    lines.append("")
    return "\n".join(lines)


def write_sigrok_session(out_path: Path, capture: Capture) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("version", "2\n")
        archive.writestr("metadata", build_metadata(capture))
        archive.writestr("logic-1", capture.samples)


def main() -> int:
    args = parse_args()
    requested_signals = parse_signal_list(args.signals)
    capture = build_capture(args.vcd, requested_signals=requested_signals, samplerate_hz=args.samplerate_hz)
    write_sigrok_session(args.out, capture)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
