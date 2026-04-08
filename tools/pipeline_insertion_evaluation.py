from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HARDWARE_BASELINE = ROOT / "docs" / "hardware" / "icebreaker_up5k_baseline.json"
DEFAULT_REPORT = ROOT / "docs" / "hardware" / "pipeline_insertion_evaluation.md"

CRITICAL_HEADER = "Info: Critical path report for clock"
MAX_FREQ_RE = re.compile(r"Max frequency for clock '.*?': ([0-9.]+) MHz \(PASS at ([0-9.]+) MHz\)")


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def nextpnr_log_path(baseline: dict[str, object]) -> Path:
    return Path(str(baseline["artifacts"]["nextpnr_log"]))


def extract_primary_clock_critical_path(log_text: str) -> list[str]:
    lines = log_text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if CRITICAL_HEADER in line and "posedge -> posedge" in line:
            start = index
            break
    if start is None:
        return []

    collected: list[str] = []
    for line in lines[start:]:
        if collected and line.startswith("Info: Critical path report for cross-domain path"):
            break
        collected.append(line)
    return collected


def classify_path(lines: list[str]) -> str:
    text = "\n".join(lines)
    if any(token in text for token in ("decode", "operand", "alu", "flags")):
        return "cpu_datapath"
    if any(token in text for token in ("ppu", "fetcher", "mixer", "scanout", "pixel")):
        return "ppu_pixel_path"
    if any(token in text for token in ("membus", "joypad", "wram_spram", "oam_ebr", "hram_ebr", "bus_read_data_reg")):
        return "bus_peripheral_readback"
    return "unclassified"


def evaluate(baseline: dict[str, object], critical_path_lines: list[str]) -> dict[str, object]:
    clock = baseline["clock_constraint"]
    achieved_mhz = float(clock["achieved_mhz"])
    target_mhz = float(clock["target_mhz"])
    margin_mhz = achieved_mhz - target_mhz
    cluster = classify_path(critical_path_lines)

    if achieved_mhz > target_mhz:
        overall = "keep current latency; no pipeline insertion recommended"
    else:
        overall = "revisit candidate datapaths"

    candidates = [
        {
            "candidate": "decode -> operand select -> ALU -> flag pack",
            "recommendation": "defer",
            "reasoning": [
                f"Recorded fmax is {achieved_mhz:.2f} MHz against a {target_mhz:.2f} MHz target ({margin_mhz:.2f} MHz margin).",
                (
                    "Observed critical-path cluster is `cpu_datapath`, but the measured slack does not justify execute-stage latency changes yet."
                    if cluster == "cpu_datapath"
                    else f"Observed critical-path cluster is `{cluster}`, not the CPU execute datapath."
                ),
            ],
        },
        {
            "candidate": "pixel fetch -> shade/merge -> output",
            "recommendation": "defer",
            "reasoning": [
                "The recorded timing report does not put a PPU pixel pipeline on the top path.",
                f"Observed critical-path cluster is `{cluster}`.",
            ],
        },
        {
            "candidate": "cartridge/PPU address pipelines",
            "recommendation": "defer",
            "reasoning": [
                "The current top path is a broad bus/peripheral readback chain, not a clean request/response leaf where latency can be inserted safely.",
                "Adding a register here would change visible memory timing before the architecture has a dedicated latency contract.",
            ],
        },
    ]

    return {
        "summary": {
            "overall_recommendation": overall,
            "achieved_mhz": achieved_mhz,
            "target_mhz": target_mhz,
            "timing_margin_mhz": margin_mhz,
            "critical_path_cluster": cluster,
        },
        "critical_path_lines": critical_path_lines,
        "candidates": candidates,
    }


def render_markdown(report: dict[str, object], *, hardware_baseline_path: Path, nextpnr_log: Path) -> str:
    summary = report["summary"]
    lines = [
        "# Pipeline Insertion Evaluation",
        "",
        f"- Hardware baseline: `{hardware_baseline_path}`",
        f"- nextpnr log: `{nextpnr_log}`",
        "",
        "## Summary",
        "",
        f"- Overall recommendation: {summary['overall_recommendation']}",
        f"- Achieved fmax: {summary['achieved_mhz']:.2f} MHz",
        f"- Target fmax: {summary['target_mhz']:.2f} MHz",
        f"- Timing margin: {summary['timing_margin_mhz']:.2f} MHz",
        f"- Classified critical-path cluster: `{summary['critical_path_cluster']}`",
        "",
        "## Candidate Decisions",
        "",
    ]
    for candidate in report["candidates"]:
        lines.append(f"### {candidate['candidate']}")
        lines.append("")
        lines.append(f"- Recommendation: {candidate['recommendation']}")
        for reason in candidate["reasoning"]:
            lines.append(f"- {reason}")
        lines.append("")
    lines.append("## Critical Path Excerpt")
    lines.append("")
    lines.append("```text")
    lines.extend(report["critical_path_lines"][:40])
    lines.append("```")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate whether any measured critical path justifies pipeline insertion.")
    parser.add_argument("--hardware-baseline", type=Path, default=DEFAULT_HARDWARE_BASELINE)
    parser.add_argument("--write-markdown", type=Path, default=DEFAULT_REPORT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    baseline = load_json(args.hardware_baseline)
    log_path = nextpnr_log_path(baseline)
    critical_path_lines = extract_primary_clock_critical_path(log_path.read_text(encoding="utf-8"))
    report = evaluate(baseline, critical_path_lines)
    markdown = render_markdown(report, hardware_baseline_path=args.hardware_baseline, nextpnr_log=log_path)
    args.write_markdown.write_text(markdown, encoding="utf-8")
    print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
