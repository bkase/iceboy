from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.actions.generators import SeededEventScript


BUTTON_BIT_ORDER = tuple(reversed(("up", "down", "left", "right", "a", "b", "start", "select")))


def encode_joypad_buttons(buttons: object) -> int:
    mask = 0
    for bit, name in enumerate(BUTTON_BIT_ORDER):
        mask |= int(bool(getattr(buttons, name))) << bit
    return mask & 0xFF


def compile_joypad_schedule(
    action_script_path: str | Path,
    *,
    frame_count: int | None = None,
) -> list[int]:
    script = SeededEventScript.from_action_script(action_script_path)
    commit_indices = [event.commit_index for event in script.events if event.commit_index is not None]
    if frame_count is None:
        frame_count = (max(commit_indices) + 1) if commit_indices else 0
    if frame_count < 0:
        raise ValueError("frame_count must be non-negative")

    current_mask = 0
    schedule: list[int] = []
    for frame_index in range(frame_count):
        for event in script.events_for_commit(frame_index):
            kind = type(event).__name__
            if kind != "JoypadButtonsEvent":
                raise ValueError(f"Unsupported scripted event for joypad schedule export: {kind}")
            current_mask = encode_joypad_buttons(event.joyp_buttons)
        schedule.append(current_mask)
    return schedule


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a commit-indexed joypad action script to frame masks.")
    parser.add_argument("--action-script", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--frame-count", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    schedule = compile_joypad_schedule(args.action_script, frame_count=args.frame_count)
    args.output.write_text("".join(f"0x{mask:02X}\n" for mask in schedule), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
