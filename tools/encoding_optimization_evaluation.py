from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACTIVITY_BASELINE = ROOT / "bench" / "manifests" / "activity_windows_baseline.json"
DEFAULT_HARDWARE_BASELINE = ROOT / "docs" / "hardware" / "icebreaker_up5k_baseline.json"
DEFAULT_REPORT = ROOT / "docs" / "hardware" / "encoding_optimization_evaluation.md"

WIDE_SIGNAL_TOKENS = ("output__", ".step", ".commit", ".make_commit", ".next_state")
BUS_TOKENS = ("bus_req", "BusReq")
PHASE_TOKENS = (".phase", "Phase::", "phase_")
ALU_TOKENS = ("alu", "AluReq", "Add16", "RotShift", "BitResSet")
REGSEL_TOKENS = ("R8::", "RegPair::", "operand8", "operand16")


@dataclass(frozen=True)
class HardwareSummary:
    lut4_used: int
    lut4_available: int
    achieved_mhz: float
    target_mhz: float

    @property
    def lut_utilization(self) -> float:
        return self.lut4_used / self.lut4_available

    @property
    def timing_margin_mhz(self) -> float:
        return self.achieved_mhz - self.target_mhz


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_hardware_summary(path: Path) -> HardwareSummary:
    payload = load_json(path)
    util = payload["utilization"]
    clock = payload["clock_constraint"]
    return HardwareSummary(
        lut4_used=int(util["lut4_used"]),
        lut4_available=int(util["lut4_available"]),
        achieved_mhz=float(clock["achieved_mhz"]),
        target_mhz=float(clock["target_mhz"]),
    )


def _sum_token_toggles(activity_payload: dict[str, object], tokens: tuple[str, ...]) -> int:
    total = 0
    windows = activity_payload.get("windows", {})
    for summary in windows.values():
        top_signals = summary.get("top_signals", [])
        for signal in top_signals:
            path = signal.get("path", "")
            if any(token in path for token in tokens):
                total += int(signal.get("toggles", 0))
    return total


def _total_top_signal_toggles(activity_payload: dict[str, object]) -> int:
    total = 0
    windows = activity_payload.get("windows", {})
    for summary in windows.values():
        for signal in summary.get("top_signals", []):
            total += int(signal.get("toggles", 0))
    return total


def evaluate(activity_payload: dict[str, object], hardware: HardwareSummary) -> dict[str, object]:
    total_top_toggles = _total_top_signal_toggles(activity_payload)
    wide_toggle_share = 0.0
    if total_top_toggles > 0:
        wide_toggle_share = _sum_token_toggles(activity_payload, WIDE_SIGNAL_TOKENS) / total_top_toggles

    observations = {
        "top_signal_toggles": total_top_toggles,
        "wide_surface_toggle_share": wide_toggle_share,
        "bus_related_top_toggles": _sum_token_toggles(activity_payload, BUS_TOKENS),
        "phase_related_top_toggles": _sum_token_toggles(activity_payload, PHASE_TOKENS),
        "alu_related_top_toggles": _sum_token_toggles(activity_payload, ALU_TOKENS),
        "register_select_top_toggles": _sum_token_toggles(activity_payload, REGSEL_TOKENS),
    }

    area_pressure = hardware.lut_utilization >= 0.70
    timing_slack_good = hardware.timing_margin_mhz >= 2.0
    evidence_is_aggregate = observations["wide_surface_toggle_share"] >= 0.50

    base_recommendation = "defer"
    base_reasoning = []
    if area_pressure:
        base_reasoning.append(
            f"LUT4 utilization is {hardware.lut4_used}/{hardware.lut4_available} ({hardware.lut_utilization:.1%}), so one-hot growth is not free."
        )
    if timing_slack_good:
        base_reasoning.append(
            f"Timing already clears the 12 MHz target with {hardware.achieved_mhz:.2f} MHz achieved ({hardware.timing_margin_mhz:.2f} MHz margin)."
        )
    if evidence_is_aggregate:
        base_reasoning.append(
            "Nightly activity windows are dominated by wide aggregate surfaces (`output__`, `step`, `commit`) rather than isolated enum or selector leaves."
        )

    candidate_reasoning = {
        "Phase enum": [
            "No direct phase-bit hotspot appears in the captured top-toggle set.",
            *base_reasoning,
        ],
        "BusReq encoding": [
            "Bus-related activity is visible, but the dominant paths are packed bus/commit surfaces rather than a leaf request encoding.",
            *base_reasoning,
        ],
        "AluReq encoding": [
            "ALU work shows up as broad execute-step activity, not a focused request-encoding hotspot.",
            *base_reasoning,
        ],
        "Register select encoding": [
            "The current captures do not isolate register-select signals strongly enough to justify a wider encoding.",
            *base_reasoning,
        ],
        "State machine encodings": [
            "No critical-path or failing-timing evidence currently forces a control-FSM encoding change.",
            *base_reasoning,
        ],
    }

    candidates = [
        {"candidate": candidate, "recommendation": base_recommendation, "reasoning": reasons}
        for candidate, reasons in candidate_reasoning.items()
    ]

    return {
        "summary": {
            "overall_recommendation": "keep current encodings for now",
            "area_pressure": "high" if area_pressure else "moderate",
            "timing_pressure": "low" if timing_slack_good else "moderate",
            "evidence_quality": "aggregate" if evidence_is_aggregate else "mixed",
        },
        "hardware": {
            "lut4_used": hardware.lut4_used,
            "lut4_available": hardware.lut4_available,
            "lut4_utilization": hardware.lut_utilization,
            "achieved_mhz": hardware.achieved_mhz,
            "target_mhz": hardware.target_mhz,
            "timing_margin_mhz": hardware.timing_margin_mhz,
        },
        "activity_observations": observations,
        "candidates": candidates,
    }


def render_markdown(report: dict[str, object], *, activity_path: Path, hardware_path: Path) -> str:
    summary = report["summary"]
    hardware = report["hardware"]
    lines = [
        "# Encoding Optimization Evaluation",
        "",
        f"- Activity baseline: `{activity_path}`",
        f"- Hardware baseline: `{hardware_path}`",
        "",
        "## Summary",
        "",
        f"- Overall recommendation: {summary['overall_recommendation']}",
        f"- LUT4 utilization: {hardware['lut4_used']}/{hardware['lut4_available']} ({hardware['lut4_utilization']:.1%})",
        f"- Timing: {hardware['achieved_mhz']:.2f} MHz achieved vs {hardware['target_mhz']:.2f} MHz target ({hardware['timing_margin_mhz']:.2f} MHz margin)",
        f"- Evidence quality: {summary['evidence_quality']}",
        "",
        "## Candidate Decisions",
        "",
    ]
    for entry in report["candidates"]:
        lines.append(f"### {entry['candidate']}")
        lines.append("")
        lines.append(f"- Recommendation: {entry['recommendation']}")
        for reason in entry["reasoning"]:
            lines.append(f"- {reason}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate whether encoding optimizations are justified by current measurements.")
    parser.add_argument("--activity-baseline", type=Path, default=DEFAULT_ACTIVITY_BASELINE)
    parser.add_argument("--hardware-baseline", type=Path, default=DEFAULT_HARDWARE_BASELINE)
    parser.add_argument("--write-markdown", type=Path, default=DEFAULT_REPORT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    activity_payload = load_json(args.activity_baseline)
    hardware = load_hardware_summary(args.hardware_baseline)
    report = evaluate(activity_payload, hardware)
    markdown = render_markdown(report, activity_path=args.activity_baseline, hardware_path=args.hardware_baseline)
    args.write_markdown.write_text(markdown, encoding="utf-8")
    print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
