from __future__ import annotations

import argparse
from pathlib import Path

import yaml


BUTTON_BITS = {
    "right": 0,
    "left": 1,
    "up": 2,
    "down": 3,
    "a": 4,
    "b": 5,
    "select": 6,
    "start": 7,
}


def _parse_frame_range(text: str) -> tuple[int, int]:
    parts = [part.strip() for part in text.split("..", 1)]
    if len(parts) != 2:
        raise ValueError(f"invalid frame range {text!r}")
    start = int(parts[0], 10)
    end = int(parts[1], 10)
    if start < 0 or end < start:
        raise ValueError(f"invalid frame range {text!r}")
    return start, end


def _button_mask(buttons: list[str]) -> int:
    mask = 0
    for button in buttons:
        key = button.strip().lower()
        if key not in BUTTON_BITS:
            raise ValueError(f"unsupported button {button!r}")
        mask |= 1 << BUTTON_BITS[key]
    return mask


def export_walk_script(script_path: Path, output_path: Path) -> tuple[int, int]:
    payload = yaml.safe_load(script_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("walk script must decode to a mapping")
    fps = int(payload.get("fps", 60))
    duration_frames = int(payload["duration_frames"])
    sequence = payload["sequence"]
    if not isinstance(sequence, list) or not sequence:
        raise ValueError("walk script sequence must be a non-empty list")

    lines = [f"fps={fps}", f"duration_frames={duration_frames}"]
    covered_until = 0
    for entry in sequence:
        if not isinstance(entry, dict):
            raise ValueError("sequence entries must be mappings")
        start, end = _parse_frame_range(str(entry["frames"]))
        if start != covered_until:
            raise ValueError(f"frame coverage must be contiguous: expected {covered_until}, got {start}")
        mask = _button_mask(list(entry.get("buttons", [])))
        lines.append(f"{start} {end} {mask}")
        covered_until = end

    if covered_until != duration_frames:
        raise ValueError(f"sequence ends at {covered_until}, expected {duration_frames}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return fps, duration_frames


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    fps, duration_frames = export_walk_script(args.script, args.output)
    print(f"exported walk schedule fps={fps} duration_frames={duration_frames} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
