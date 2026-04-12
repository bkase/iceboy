from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional, Tuple


DISPLAY_WIDTH = 320
DISPLAY_HEIGHT = 240
FRAME_WIDTH = 160
FRAME_HEIGHT = 144
FRAME_PIXELS = FRAME_WIDTH * FRAME_HEIGHT
RGB565_PALETTE = (
    0xFFFF,
    0xAD55,
    0x52AA,
    0x0000,
)

TranscriptEntry = Tuple[bool, int, Optional[str]]


def _command(byte: int, label: str) -> TranscriptEntry:
    return (False, byte, label)


def _data(byte: int, label: Optional[str] = None) -> TranscriptEntry:
    return (True, byte, label)


def _word_bytes(word: int) -> tuple[int, int]:
    return ((word >> 8) & 0xFF, word & 0xFF)


def _window_bounds(width: int, height: int, *, centered: bool) -> tuple[int, int, int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if width > DISPLAY_WIDTH or height > DISPLAY_HEIGHT:
        raise ValueError("frame exceeds ST7789 panel bounds")

    if centered:
        x0 = (DISPLAY_WIDTH - width) // 2
        y0 = (DISPLAY_HEIGHT - height) // 2
    else:
        x0 = 0
        y0 = 0
    x1 = x0 + width - 1
    y1 = y0 + height - 1
    return (x0, x1, y0, y1)


def generate_init_transcript() -> List[TranscriptEntry]:
    return [
        _command(0x01, "SWRESET"),
        _command(0x11, "SLPOUT"),
        _command(0x3A, "COLMOD"),
        _data(0x55, "COLMOD=RGB565"),
        _command(0x36, "MADCTL"),
        _data(0x00, "MADCTL=0x00"),
        _command(0x2A, "CASET"),
        _data(0x00, "CASET.x0[15:8]"),
        _data(0x00, "CASET.x0[7:0]"),
        _data(0x01, "CASET.x1[15:8]"),
        _data(0x3F, "CASET.x1[7:0]"),
        _command(0x2B, "RASET"),
        _data(0x00, "RASET.y0[15:8]"),
        _data(0x00, "RASET.y0[7:0]"),
        _data(0x00, "RASET.y1[15:8]"),
        _data(0xEF, "RASET.y1[7:0]"),
        _command(0x21, "INVON"),
        _command(0x13, "NORON"),
        _command(0x29, "DISPON"),
    ]


def generate_windowed_frame_transcript(
    frame: bytes,
    *,
    width: int,
    height: int,
    centered: bool = True,
) -> List[TranscriptEntry]:
    expected_bytes = width * height
    if len(frame) != expected_bytes:
        raise ValueError(f"expected {expected_bytes} frame bytes for {width}x{height}, got {len(frame)}")

    x0, x1, y0, y1 = _window_bounds(width, height, centered=centered)
    transcript: List[TranscriptEntry] = [
        _command(0x2A, "CASET"),
        _data((x0 >> 8) & 0xFF, "CASET.x0[15:8]"),
        _data(x0 & 0xFF, "CASET.x0[7:0]"),
        _data((x1 >> 8) & 0xFF, "CASET.x1[15:8]"),
        _data(x1 & 0xFF, "CASET.x1[7:0]"),
        _command(0x2B, "RASET"),
        _data((y0 >> 8) & 0xFF, "RASET.y0[15:8]"),
        _data(y0 & 0xFF, "RASET.y0[7:0]"),
        _data((y1 >> 8) & 0xFF, "RASET.y1[15:8]"),
        _data(y1 & 0xFF, "RASET.y1[7:0]"),
        _command(0x2C, "RAMWR"),
    ]

    for index, shade in enumerate(frame):
        rgb565 = RGB565_PALETTE[shade & 0x3]
        hi, lo = _word_bytes(rgb565)
        transcript.append(_data(hi, f"PIXEL[{index}].hi"))
        transcript.append(_data(lo, f"PIXEL[{index}].lo"))

    return transcript


def generate_frame_transcript(frame: bytes, centered: bool = True) -> List[TranscriptEntry]:
    return generate_windowed_frame_transcript(frame, width=FRAME_WIDTH, height=FRAME_HEIGHT, centered=centered)


def transcript_to_jsonable(transcript: List[TranscriptEntry]) -> List[dict]:
    return [{"dc": dc, "byte": byte, "label": label} for dc, byte, label in transcript]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a golden ST7789 SPI transcript.")
    parser.add_argument("--mode", choices=("init", "frame"), required=True)
    parser.add_argument("--input", type=Path, help="raw 1-byte-per-pixel shade buffer")
    parser.add_argument("--output", type=Path, help="output JSON path; defaults to stdout")
    parser.add_argument("--no-center", action="store_true", help="place the frame at (0,0) instead of centering")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    centered = not args.no_center

    if args.mode == "init":
        transcript = generate_init_transcript()
    else:
        if args.input is None:
            raise SystemExit("--input is required in frame mode")
        transcript = generate_frame_transcript(args.input.read_bytes(), centered=centered)

    text = json.dumps(transcript_to_jsonable(transcript), indent=2) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
