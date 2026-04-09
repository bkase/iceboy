from __future__ import annotations

import argparse
import binascii
import struct
import sys
import zlib
from pathlib import Path

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from test.harness.rom_runner import SCREEN_HEIGHT, SCREEN_WIDTH, _decode_png_grayscale, _shade_frame_mismatch


def _rows_from_raw(path: Path, *, width: int, height: int) -> tuple[tuple[int, ...], ...]:
    data = path.read_bytes()
    expected_len = width * height
    if len(data) != expected_len:
        raise ValueError(f"{path} must contain exactly {expected_len} bytes, got {len(data)}")
    return tuple(
        tuple(data[row_start : row_start + width])
        for row_start in range(0, expected_len, width)
    )


def _encode_png_grayscale(rows: tuple[tuple[int, ...], ...]) -> bytes:
    height = len(rows)
    width = len(rows[0]) if rows else 0
    raw = bytearray()
    for row in rows:
        raw.append(0)
        raw.extend(pixel & 0xFF for pixel in row)
    compressed = zlib.compress(bytes(raw))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", ihdr),
            chunk(b"IDAT", compressed),
            chunk(b"IEND", b""),
        )
    )


def compare_shaded_frame(
    *,
    raw_path: Path,
    expected_path: Path,
    output_png: Path | None = None,
    width: int = SCREEN_WIDTH,
    height: int = SCREEN_HEIGHT,
) -> tuple[int, tuple[int, int, int, int] | None]:
    actual = _rows_from_raw(raw_path, width=width, height=height)
    expected = _decode_png_grayscale(expected_path)
    mismatches, first = _shade_frame_mismatch(actual, expected)
    if output_png is not None:
        output_png.write_bytes(_encode_png_grayscale(actual))
    return mismatches, first


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--output-png", type=Path, default=None)
    parser.add_argument("--width", type=int, default=SCREEN_WIDTH)
    parser.add_argument("--height", type=int, default=SCREEN_HEIGHT)
    args = parser.parse_args()

    mismatches, first = compare_shaded_frame(
        raw_path=args.raw,
        expected_path=args.expected,
        output_png=args.output_png,
        width=args.width,
        height=args.height,
    )
    if mismatches == 0:
        print("frame matches reference")
        return 0
    first_text = ""
    if first is not None:
        x, y, actual_px, expected_px = first
        first_text = f" first mismatch at ({x}, {y}): actual=0x{actual_px:02X} expected=0x{expected_px:02X}"
    print(f"frame mismatch: {mismatches} pixels differ.{first_text}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
