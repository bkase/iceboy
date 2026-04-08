from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "bench" / "manifests" / "activity_windows.yaml"
DEFAULT_ARTIFACT_ROOT = ROOT / "bench" / "artifacts" / "activity_capture"
DEFAULT_BASELINE = ROOT / "bench" / "manifests" / "activity_windows_baseline.json"
DEFAULT_FST2VCD = ROOT / "build" / "oss-cad-suite" / "bin" / "fst2vcd"


@dataclass(frozen=True)
class WindowSpec:
    name: str
    description: str
    run: str
    command: tuple[str, ...]
    wave_glob: str


@dataclass(frozen=True)
class SignalActivity:
    path: str
    width: int
    toggles: int
    t0_ps: int
    t1_ps: int
    tx_ps: int
    tz_ps: int


@dataclass(frozen=True)
class WindowSummary:
    name: str
    description: str
    source_fst: str
    source_vcd: str
    duration_ps: int
    signal_count: int
    named_signal_count: int
    reportable_signal_count: int
    total_toggles: int
    named_total_toggles: int
    reportable_total_toggles: int
    top_signals: tuple[SignalActivity, ...]


@dataclass
class MutableSignal:
    path: str
    width: int
    current_value: str | None = None
    last_change_ps: int = 0
    toggles: int = 0
    t0_ps: int = 0
    t1_ps: int = 0
    tx_ps: int = 0
    tz_ps: int = 0

    def observe(self, value: str, at_ps: int) -> None:
        if self.current_value is not None:
            self._accumulate(at_ps)
            if value != self.current_value:
                self.toggles += 1
        self.current_value = value
        self.last_change_ps = at_ps

    def finish(self, end_ps: int) -> SignalActivity:
        self._accumulate(end_ps)
        return SignalActivity(
            path=self.path,
            width=self.width,
            toggles=self.toggles,
            t0_ps=self.t0_ps,
            t1_ps=self.t1_ps,
            tx_ps=self.tx_ps,
            tz_ps=self.tz_ps,
        )

    def _accumulate(self, end_ps: int) -> None:
        if self.current_value is None or end_ps <= self.last_change_ps:
            return
        delta = end_ps - self.last_change_ps
        klass = classify_value(self.current_value)
        if klass == "0":
            self.t0_ps += delta
        elif klass == "1":
            self.t1_ps += delta
        elif klass == "z":
            self.tz_ps += delta
        else:
            self.tx_ps += delta
        self.last_change_ps = end_ps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture representative activity windows and emit SAIF summaries.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--fst2vcd", type=Path, default=DEFAULT_FST2VCD)
    parser.add_argument("--swim-bin", default="swim")
    parser.add_argument("--window", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-baseline", type=Path, help="Write the stable summary baseline to this path.")
    return parser


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_manifest(path: Path) -> list[WindowSpec]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw_windows = payload.get("windows", []) if isinstance(payload, dict) else []
    windows: list[WindowSpec] = []
    for item in raw_windows:
        if not isinstance(item, dict):
            continue
        windows.append(
            WindowSpec(
                name=str(item["name"]),
                description=str(item["description"]),
                run=str(item["run"]),
                command=tuple(str(part) for part in item["command"]),
                wave_glob=str(item["wave_glob"]),
            )
        )
    return windows


def classify_value(value: str) -> str:
    text = value.strip().lower()
    if not text:
        return "x"
    if "z" in text:
        return "z"
    if "x" in text:
        return "x"
    if set(text) <= {"0"}:
        return "0"
    if set(text) <= {"1"}:
        return "1"
    return "x"


def normalize_value(raw: str, *, width: int) -> str:
    text = raw.strip().lower()
    if not text:
        return "x" * max(width, 1)
    if width <= 1:
        return text[-1]
    if len(text) >= width:
        return text[-width:]
    return text.rjust(width, text[0])


def parse_vcd_activity(path: Path) -> tuple[int, list[SignalActivity]]:
    scope: list[str] = []
    symbols: dict[str, MutableSignal] = {}
    current_time_ps = 0
    in_dumpvars = False

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("$scope"):
                parts = line.split()
                if len(parts) >= 3:
                    scope.append(parts[2])
                continue
            if line.startswith("$upscope"):
                if scope:
                    scope.pop()
                continue
            if line.startswith("$var"):
                parts = line.split()
                if len(parts) >= 5:
                    width = int(parts[2])
                    symbol = parts[3]
                    name = parts[4]
                    path_name = ".".join(scope + [name])
                    symbols[symbol] = MutableSignal(path=path_name, width=width)
                continue
            if line == "$dumpvars":
                in_dumpvars = True
                continue
            if line == "$end":
                in_dumpvars = False
                continue
            if line.startswith("#"):
                current_time_ps = int(line[1:])
                continue
            if line.startswith("$"):
                continue
            if line[0] in "01xXzZ":
                symbol = line[1:]
                signal = symbols.get(symbol)
                if signal is None:
                    continue
                signal.observe(normalize_value(line[0], width=signal.width), current_time_ps)
                continue
            if line[0] in "bB":
                parts = line.split()
                if len(parts) != 2:
                    continue
                value = parts[0][1:]
                symbol = parts[1]
                signal = symbols.get(symbol)
                if signal is None:
                    continue
                signal.observe(normalize_value(value, width=signal.width), current_time_ps)
                continue
            if in_dumpvars:
                continue

    return current_time_ps, sorted((signal.finish(current_time_ps) for signal in symbols.values()), key=lambda item: item.path)


def is_named_signal(path: str) -> bool:
    return not path.split(".")[-1].startswith("_e_")


def is_reportable_signal(path: str) -> bool:
    leaf = path.split(".")[-1]
    if not is_named_signal(path):
        return False
    if leaf.startswith("clk") or leaf.startswith("rst"):
        return False
    if leaf.endswith("clk_i") or leaf.endswith("rst_i"):
        return False
    return True


def write_saif(path: Path, *, window_name: str, duration_ps: int, signals: Iterable[SignalActivity]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "(SAIFILE",
        '  (SAIFVERSION "2.0")',
        '  (DIRECTION "backward")',
        '  (DESIGN "iceboy")',
        f'  (DATE "{datetime.now(timezone.utc).isoformat()}")',
        '  (VENDOR "iceboy")',
        '  (PROGRAM_NAME "tools/activity_capture.py")',
        "  (TIMESCALE 1 ps)",
        f"  (DURATION {duration_ps})",
        f"  (INSTANCE {window_name}",
    ]
    for signal in signals:
        leaf = signal.path.split(".")[-1]
        lines.extend(
            [
                "    (NET",
                f"      ({leaf}",
                f"        (T0 {signal.t0_ps})",
                f"        (T1 {signal.t1_ps})",
                f"        (TX {signal.tx_ps})",
                f"        (TZ {signal.tz_ps})",
                f"        (TC {signal.toggles})",
                "        (IG 0)",
                "      )",
                "    )",
            ]
        )
    lines.extend(["  )", ")"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_window(spec: WindowSpec, *, fst_path: Path, vcd_path: Path) -> WindowSummary:
    duration_ps, signals = parse_vcd_activity(vcd_path)
    named = [signal for signal in signals if is_named_signal(signal.path)]
    reportable = [signal for signal in signals if is_reportable_signal(signal.path)]
    top = tuple(sorted(reportable, key=lambda item: (-item.toggles, item.path))[:20])
    return WindowSummary(
        name=spec.name,
        description=spec.description,
        source_fst=display_path(fst_path),
        source_vcd=display_path(vcd_path),
        duration_ps=duration_ps,
        signal_count=len(signals),
        named_signal_count=len(named),
        reportable_signal_count=len(reportable),
        total_toggles=sum(signal.toggles for signal in signals),
        named_total_toggles=sum(signal.toggles for signal in named),
        reportable_total_toggles=sum(signal.toggles for signal in reportable),
        top_signals=top,
    )


def stable_baseline_payload(summaries: Iterable[WindowSummary]) -> dict[str, object]:
    windows: dict[str, object] = {}
    for summary in summaries:
        windows[summary.name] = {
            "description": summary.description,
            "duration_ps": summary.duration_ps,
            "reportable_signal_count": summary.reportable_signal_count,
            "reportable_total_toggles": summary.reportable_total_toggles,
            "top_signals": [asdict(signal) for signal in summary.top_signals],
        }
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "windows": windows}


def comparison_payload(current: dict[str, object], baseline_path: Path) -> dict[str, object]:
    if not baseline_path.is_file():
        return {"status": "missing_baseline", "baseline": display_path(baseline_path)}
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    comparisons: dict[str, object] = {}
    current_windows = current.get("windows", {})
    baseline_windows = baseline.get("windows", {})
    for name, current_window in current_windows.items():
        previous = baseline_windows.get(name)
        if previous is None:
            comparisons[name] = {"status": "missing_window"}
            continue
        previous_total = int(previous.get("reportable_total_toggles", 0))
        current_total = int(current_window.get("reportable_total_toggles", 0))
        comparisons[name] = {
            "status": "compared",
            "delta_reportable_total_toggles": current_total - previous_total,
            "baseline_reportable_total_toggles": previous_total,
            "current_reportable_total_toggles": current_total,
        }
    return {
        "status": "compared",
        "baseline": display_path(baseline_path),
        "windows": comparisons,
    }


def convert_fst_to_vcd(*, fst_path: Path, vcd_path: Path, fst2vcd: Path) -> None:
    subprocess.run([str(fst2vcd), "-f", str(fst_path), "-o", str(vcd_path)], cwd=ROOT, check=True)


def latest_wave(glob_pattern: str) -> Path:
    matches = sorted(ROOT.glob(glob_pattern), key=lambda item: item.stat().st_mtime)
    if not matches:
        raise FileNotFoundError(f"no waveform matched {glob_pattern}")
    return matches[-1]


def write_window_artifacts(*, summary: WindowSummary, saif_path: Path, summary_path: Path) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                **asdict(summary),
                "top_signals": [asdict(signal) for signal in summary.top_signals],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    write_saif(
        saif_path,
        window_name=summary.name,
        duration_ps=summary.duration_ps,
        signals=summary.top_signals,
    )


def write_report(*, artifact_root: Path, summaries: list[WindowSummary], baseline: Path) -> None:
    artifact_root.mkdir(parents=True, exist_ok=True)
    stable = stable_baseline_payload(summaries)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_count": len(summaries),
        "windows": {
            summary.name: {
                "description": summary.description,
                "duration_ps": summary.duration_ps,
                "reportable_signal_count": summary.reportable_signal_count,
                "reportable_total_toggles": summary.reportable_total_toggles,
                "top_signals": [asdict(signal) for signal in summary.top_signals],
            }
            for summary in summaries
        },
        "comparison": comparison_payload(stable, baseline),
    }
    (artifact_root / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Activity Capture Report", ""]
    for summary in summaries:
        lines.extend(
            [
                f"## {summary.name}",
                summary.description,
                f"- duration_ps: `{summary.duration_ps}`",
                f"- reportable_signal_count: `{summary.reportable_signal_count}`",
                f"- reportable_total_toggles: `{summary.reportable_total_toggles}`",
                f"- source_fst: `{summary.source_fst}`",
                "",
                "| signal | width | toggles |",
                "| --- | ---: | ---: |",
            ]
        )
        for signal in summary.top_signals:
            lines.append(f"| `{signal.path}` | `{signal.width}` | `{signal.toggles}` |")
        lines.append("")
    (artifact_root / "report.md").write_text("\n".join(lines), encoding="utf-8")


def resolved_command(command: tuple[str, ...], *, swim_bin: str) -> tuple[str, ...]:
    if command and command[0] == "swim":
        return (swim_bin, *command[1:])
    return command


def run_window_commands(windows: list[WindowSpec], *, dry_run: bool, swim_bin: str) -> None:
    executed: dict[str, tuple[str, ...]] = {}
    for spec in windows:
        if spec.run in executed:
            continue
        command = resolved_command(spec.command, swim_bin=swim_bin)
        executed[spec.run] = command
        pretty = shlex.join(command)
        print(f"[RUN] {spec.run}: {pretty}")
        if dry_run:
            continue
        env = os.environ.copy()
        env["PATH"] = f"/opt/homebrew/bin:{env.get('PATH', '')}"
        env["ICEBOY_WAVES"] = "1"
        env.setdefault("ICEBOY_WAVES_ON_FAILURE", "1")
        subprocess.run(list(command), cwd=ROOT, env=env, check=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    windows = load_manifest(args.manifest)
    if args.window:
        requested = set(args.window)
        windows = [window for window in windows if window.name in requested]
    if not windows:
        raise SystemExit("no activity windows selected")

    run_window_commands(windows, dry_run=args.dry_run, swim_bin=args.swim_bin)

    if args.dry_run:
        for spec in windows:
            print(f"[WAVE] {spec.name}: {spec.wave_glob}")
        return 0

    args.artifact_root.mkdir(parents=True, exist_ok=True)
    summaries: list[WindowSummary] = []
    for spec in windows:
        fst_path = latest_wave(spec.wave_glob)
        window_root = args.artifact_root / spec.name
        window_root.mkdir(parents=True, exist_ok=True)
        vcd_path = window_root / f"{spec.name}.vcd"
        saif_path = window_root / f"{spec.name}.saif"
        summary_path = window_root / "summary.json"
        convert_fst_to_vcd(fst_path=fst_path, vcd_path=vcd_path, fst2vcd=args.fst2vcd)
        summary = summarize_window(spec, fst_path=fst_path, vcd_path=vcd_path)
        write_window_artifacts(summary=summary, saif_path=saif_path, summary_path=summary_path)
        summaries.append(summary)
        print(f"[CAPTURE] {spec.name}: toggles={summary.reportable_total_toggles} signals={summary.reportable_signal_count}")

    write_report(artifact_root=args.artifact_root, summaries=summaries, baseline=args.baseline)
    if args.write_baseline is not None:
        args.write_baseline.write_text(
            json.dumps(stable_baseline_payload(summaries), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"[BASELINE] wrote {display_path(args.write_baseline)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
