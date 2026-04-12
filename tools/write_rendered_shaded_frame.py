from __future__ import annotations

import argparse
from pathlib import Path

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.pyboy.oracle import capture_rendered_frame_dmg_shades
from bench.pyboy.oracle import capture_checkpoint_frame_dmg_shades


def _parse_frame_batches(text: str) -> tuple[int, ...]:
    values = tuple(int(token, 10) for token in text.split(",") if token.strip())
    if not values:
        raise ValueError("frame batch list must not be empty")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--output-raw", required=True, type=Path)
    parser.add_argument("--frame-batches", default="84")
    parser.add_argument("--sym", type=Path, default=None)
    parser.add_argument("--checkpoint-label", default="__checkpoint_scene_ready")
    parser.add_argument("--settle-rendered-frames", type=int, default=2)
    args = parser.parse_args()

    if args.sym is None:
        data = capture_rendered_frame_dmg_shades(
            args.rom,
            frame_batches=_parse_frame_batches(args.frame_batches),
        )
    else:
        data = capture_checkpoint_frame_dmg_shades(
            args.rom,
            sym_path=args.sym,
            checkpoint_label=args.checkpoint_label,
            settle_rendered_frames=args.settle_rendered_frames,
        )
    args.output_raw.write_bytes(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
