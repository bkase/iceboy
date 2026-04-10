from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path


SCREEN_WIDTH = 160
SCREEN_HEIGHT = 144
FRAME_SIZE = SCREEN_WIDTH * SCREEN_HEIGHT


def encode_png_grayscale(frame: bytes, width: int = SCREEN_WIDTH, height: int = SCREEN_HEIGHT) -> bytes:
    if len(frame) != width * height:
        raise ValueError(f"frame size mismatch: got {len(frame)}, expected {width * height}")

    rows = b"".join(b"\x00" + frame[row * width : (row + 1) * width] for row in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(rows, 9)),
            chunk(b"IEND", b""),
        ]
    )


def write_frame_artifacts(
    *,
    frames_raw_path: Path,
    target_frames: int,
    first_raw_path: Path,
    mid_raw_path: Path,
    last_raw_path: Path,
    first_png_path: Path,
    mid_png_path: Path,
    last_png_path: Path,
) -> int:
    data = frames_raw_path.read_bytes()
    expected_len = FRAME_SIZE * target_frames
    if len(data) != expected_len:
        raise ValueError(f"raw frame stream size mismatch: got {len(data)}, expected {expected_len}")

    first = data[:FRAME_SIZE]
    mid_offset = (target_frames // 2) * FRAME_SIZE
    mid = data[mid_offset : mid_offset + FRAME_SIZE]
    last = data[-FRAME_SIZE:]

    first_raw_path.write_bytes(first)
    mid_raw_path.write_bytes(mid)
    last_raw_path.write_bytes(last)
    first_png_path.write_bytes(encode_png_grayscale(first))
    mid_png_path.write_bytes(encode_png_grayscale(mid))
    last_png_path.write_bytes(encode_png_grayscale(last))
    return len(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames-raw", required=True, type=Path)
    parser.add_argument("--target-frames", required=True, type=int)
    parser.add_argument("--first-raw", required=True, type=Path)
    parser.add_argument("--mid-raw", required=True, type=Path)
    parser.add_argument("--last-raw", required=True, type=Path)
    parser.add_argument("--first-png", required=True, type=Path)
    parser.add_argument("--mid-png", required=True, type=Path)
    parser.add_argument("--last-png", required=True, type=Path)
    args = parser.parse_args()
    byte_count = write_frame_artifacts(
        frames_raw_path=args.frames_raw,
        target_frames=args.target_frames,
        first_raw_path=args.first_raw,
        mid_raw_path=args.mid_raw,
        last_raw_path=args.last_raw,
        first_png_path=args.first_png,
        mid_png_path=args.mid_png,
        last_png_path=args.last_png,
    )
    print(f"validated raw frame stream frames={args.target_frames} bytes={byte_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
