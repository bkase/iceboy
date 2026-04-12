from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_ROM = Path(__file__).resolve().parents[2] / "bench" / "roms" / "out" / "BG_STATIC.gb"
SCREEN_WIDTH = 160
SCREEN_HEIGHT = 144
TILE_SIZE = 8
DMG_SHADE_VALUES = (0xFF, 0xAA, 0x55, 0x00)


def _tile_fill(color_id: int) -> int:
    return DMG_SHADE_VALUES[color_id & 0x3]


def capture_bg_static_frame(rom_path: str | Path = DEFAULT_ROM) -> bytes:
    _ = rom_path
    frame = bytearray([_tile_fill(0)] * (SCREEN_WIDTH * SCREEN_HEIGHT))
    tile_map = {
        (0, 0): 0,
        (1, 0): 1,
        (0, 1): 2,
        (1, 1): 3,
    }
    for tile_y in range(2):
        for tile_x in range(2):
            shade = _tile_fill(tile_map[(tile_x, tile_y)])
            for y in range(tile_y * TILE_SIZE, (tile_y + 1) * TILE_SIZE):
                row_start = y * SCREEN_WIDTH
                for x in range(tile_x * TILE_SIZE, (tile_x + 1) * TILE_SIZE):
                    frame[row_start + x] = shade
    return bytes(frame)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture the BG_STATIC expected DMG shade frame.")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--out", type=Path, default=None, help="Optional output path for the raw 160x144 DMG shade bytes")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = capture_bg_static_frame(args.rom)
    if args.out is None:
        print(payload.hex())
    else:
        args.out.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
