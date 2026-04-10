from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.pyboy.oracle import CommitPoint, capture_checkpoint_hook_timings, capture_checkpoint_line_mode_timing
from tools.rom_trace_summary import summarize_rom_trace

DOCUMENTED_MODE3_BASELINE_DOTS = 172


def _hook_stats(captures: list[dict[str, object]], labels: tuple[str, ...]) -> dict[str, dict[str, object]]:
    stats: dict[str, dict[str, object]] = {}
    for label in labels:
        matches = [capture for capture in captures if capture.get("label") == label]
        stats[label] = {
            "count": len(matches),
            "first": matches[0] if matches else None,
            "last": matches[-1] if matches else None,
        }
    return stats


def _native_gap_analysis(native: dict[str, object]) -> dict[str, object]:
    milestones = native.get("milestones", {})
    spans = native.get("spans", {})
    first_object = milestones.get("first_object_scanout") if isinstance(milestones, dict) else None
    first_preview = milestones.get("first_lcdc_preview_write") if isinstance(milestones, dict) else None
    first_write = milestones.get("first_lcdc_write") if isinstance(milestones, dict) else None
    line_summary = milestones.get("line_summary") if isinstance(milestones, dict) else None
    mode3_span = spans.get("mode3") if isinstance(spans, dict) else None
    object_span = spans.get("object_scanout") if isinstance(spans, dict) else None

    def gap(lhs: object, rhs: object) -> int | None:
        if not isinstance(lhs, dict) or not isinstance(rhs, dict):
            return None
        lhs_x = lhs.get("scanout_x")
        rhs_x = rhs.get("scanout_x")
        if lhs_x is None or rhs_x is None:
            return None
        return int(rhs_x) - int(lhs_x)

    return {
        "documented_mode3_baseline_dots": DOCUMENTED_MODE3_BASELINE_DOTS,
        "line_summary_mode3_len": line_summary.get("line_summary_mode3_len") if isinstance(line_summary, dict) else None,
        "line_summary_penalty_dots": (
            int(line_summary.get("line_summary_mode3_len")) - DOCUMENTED_MODE3_BASELINE_DOTS
            if isinstance(line_summary, dict) and line_summary.get("line_summary_mode3_len") is not None
            else None
        ),
        "mode3_scanout_width": mode3_span.get("scanout_width") if isinstance(mode3_span, dict) else None,
        "mode3_cycle_width": mode3_span.get("cycle_width") if isinstance(mode3_span, dict) else None,
        "object_scanout_width": object_span.get("scanout_width") if isinstance(object_span, dict) else None,
        "object_scanout_cycle_width": object_span.get("cycle_width") if isinstance(object_span, dict) else None,
        "preview_write_minus_first_object_x": gap(first_object, first_preview),
        "write_minus_first_object_x": gap(first_object, first_write),
    }


def compare_row_loop_timing(
    *,
    rom_path: Path,
    sym_path: Path,
    trace_path: Path,
    line: int,
    labels: tuple[str, ...],
    write_pc: int,
    checkpoint_label: str = "__checkpoint_scene_ready",
    settle_rendered_frames: int = 2,
) -> dict[str, object]:
    pyboy_hook_points = tuple(
        [CommitPoint(bank=None, addr=label) for label in labels] + [CommitPoint(bank=0, addr=write_pc, label="WriteObjOff")]
    )
    pyboy = capture_checkpoint_hook_timings(
        rom_path,
        sym_path=sym_path,
        hook_points=pyboy_hook_points,
        checkpoint_label=checkpoint_label,
        settle_rendered_frames=settle_rendered_frames,
        target_line=line,
    )
    pyboy_line_timing = capture_checkpoint_line_mode_timing(
        rom_path,
        sym_path=sym_path,
        checkpoint_label=checkpoint_label,
        settle_rendered_frames=settle_rendered_frames,
        target_line=line,
    )
    native = summarize_rom_trace(trace_path, sym_path, line=line, labels=labels)
    pyboy_records = [asdict(capture) for capture in pyboy]
    return {
        "rom_path": str(rom_path),
        "sym_path": str(sym_path),
        "trace_path": str(trace_path),
        "line": line,
        "checkpoint_label": checkpoint_label,
        "settle_rendered_frames": settle_rendered_frames,
        "labels": list(labels),
        "write_pc": f"0x{write_pc:04x}",
        "pyboy": pyboy_records,
        "pyboy_line_timing": asdict(pyboy_line_timing),
        "pyboy_mode3_penalty_dots": pyboy_line_timing.mode3_len_dots - DOCUMENTED_MODE3_BASELINE_DOTS,
        "pyboy_label_stats": _hook_stats(pyboy_records, tuple(label for label in labels) + ("WriteObjOff",)),
        "native": native,
        "native_gap_analysis": _native_gap_analysis(native),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--sym", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--line", required=True, type=int)
    parser.add_argument("--label", action="append", default=[])
    parser.add_argument("--write-pc", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--checkpoint-label", default="__checkpoint_scene_ready")
    parser.add_argument("--settle-rendered-frames", type=int, default=2)
    args = parser.parse_args()

    summary = compare_row_loop_timing(
        rom_path=args.rom,
        sym_path=args.sym,
        trace_path=args.trace,
        line=args.line,
        labels=tuple(args.label),
        write_pc=args.write_pc,
        checkpoint_label=args.checkpoint_label,
        settle_rendered_frames=args.settle_rendered_frames,
    )
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
