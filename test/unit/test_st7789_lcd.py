# top = periph::st7789_lcd_test_top::st7789_lcd_test_top
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


def find_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "tools" / "ref_st7789_transcript.py").is_file():
        return cwd

    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tools" / "ref_st7789_transcript.py").is_file():
            return candidate

    raise RuntimeError("could not locate repo root for ref_st7789_transcript.py")


ROOT = find_repo_root()
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from ref_st7789_transcript import generate_frame_transcript, generate_init_transcript


TranscriptByte = Tuple[bool, int]


def decode_output(value: int) -> Dict[str, int | bool]:
    return {
        "lcd_sck": bool(value & 0x1),
        "lcd_mosi": bool((value >> 1) & 0x1),
        "lcd_cs": bool((value >> 2) & 0x1),
        "lcd_dc": bool((value >> 3) & 0x1),
        "lcd_res": bool((value >> 4) & 0x1),
        "lcd_bl": bool((value >> 5) & 0x1),
        "pixel_advance": bool((value >> 6) & 0x1),
        "init_done": bool((value >> 7) & 0x1),
        "frame_active": bool((value >> 8) & 0x1),
        "tx_active": bool((value >> 9) & 0x1),
        "state_code": (value >> 10) & 0xF,
        "current_byte": (value >> 14) & 0xFF,
        "current_dc": bool((value >> 22) & 0x1),
        "command_index": (value >> 23) & 0xF,
        "data_index": (value >> 27) & 0x7,
        "pixel_count": (value >> 30) & 0x7FFF,
    }


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 84, units="ns").start())
    dut.reset_ticks_i.value = 2
    dut.post_reset_ticks_i.value = 3
    dut.sleep_out_ticks_i.value = 4
    dut.frame_start_i.value = 0
    dut.pixel_valid_i.value = 0
    dut.pixel_shade_i.value = 0
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step(
    dut,
    *,
    frame_start: bool = False,
    pixel_valid: bool = False,
    pixel_shade: int = 0,
) -> Dict[str, int | bool]:
    dut.frame_start_i.value = int(frame_start)
    dut.pixel_valid_i.value = int(pixel_valid)
    dut.pixel_shade_i.value = pixel_shade & 0xFF
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


async def collect_bytes(
    dut,
    *,
    expected_count: int,
    frame_start_at_cycle: Optional[int] = None,
    pixel_stream: Optional[Sequence[int]] = None,
    max_cycles: int = 4000,
) -> List[TranscriptByte]:
    transcript: List[TranscriptByte] = []
    prev = decode_output(int(dut.output__.value))
    byte = 0
    bit_count = 0
    byte_dc = False
    pixel_stream = [] if pixel_stream is None else list(pixel_stream)
    pixel_index = 0
    pixel_count_seen = int(prev["pixel_count"])

    for cycle in range(max_cycles):
        pixel_valid = pixel_index < len(pixel_stream)
        pixel_shade = pixel_stream[pixel_index] if pixel_valid else 0
        snapshot = await step(
            dut,
            frame_start=frame_start_at_cycle is not None and cycle == frame_start_at_cycle,
            pixel_valid=pixel_valid,
            pixel_shade=pixel_shade,
        )

        if snapshot["lcd_cs"]:
            byte = 0
            bit_count = 0
        elif (not prev["lcd_sck"]) and snapshot["lcd_sck"]:
            if bit_count == 0:
                byte_dc = bool(snapshot["lcd_dc"])
            byte = ((byte << 1) | int(snapshot["lcd_mosi"])) & 0xFF
            bit_count += 1
            if bit_count == 8:
                transcript.append((byte_dc, byte))
                if len(transcript) >= expected_count:
                    return transcript
                byte = 0
                bit_count = 0

        current_pixel_count = int(snapshot["pixel_count"])
        if current_pixel_count > pixel_count_seen and pixel_index < len(pixel_stream):
            pixel_index += current_pixel_count - pixel_count_seen
        pixel_count_seen = current_pixel_count

        prev = snapshot

    raise AssertionError(f"Timed out collecting {expected_count} bytes, got {len(transcript)}")


async def wait_until(
    dut,
    predicate: Callable[[Dict[str, int | bool]], bool],
    *,
    max_cycles: int = 4000,
) -> Dict[str, int | bool]:
    for _ in range(max_cycles):
        snapshot = await step(dut)
        if predicate(snapshot):
            return snapshot
    raise AssertionError("condition not reached before timeout")


def assert_transcript_matches(
    actual: Sequence[TranscriptByte],
    expected_entries: Sequence[Tuple[bool, int, Optional[str]]],
) -> None:
    expected = [(dc, byte) for dc, byte, _ in expected_entries]
    assert len(actual) == len(expected), f"byte_count mismatch: expected {len(expected)} actual {len(actual)}"
    for index, (actual_entry, expected_entry) in enumerate(zip(actual, expected_entries)):
        actual_dc, actual_byte = actual_entry
        expected_dc, expected_byte, label = expected_entry
        if actual_dc != expected_dc or actual_byte != expected_byte:
            raise AssertionError(
                f"byte[{index}] mismatch label={label} expected=(dc={int(expected_dc)}, byte=0x{expected_byte:02X}) "
                f"actual=(dc={int(actual_dc)}, byte=0x{actual_byte:02X})"
            )


@cocotb.test()
async def test_reset_and_init_sequence_matches_golden_transcript(dut):
    await reset_dut(dut)

    snapshot = await step(dut)
    assert snapshot["lcd_res"] is False
    assert snapshot["lcd_bl"] is False
    assert snapshot["init_done"] is False

    expected = generate_init_transcript()
    transcript = await collect_bytes(dut, expected_count=len(expected))
    assert_transcript_matches(transcript, expected)

    final = await wait_until(dut, lambda snap: bool(snap["init_done"]) and not bool(snap["frame_active"]) and not bool(snap["tx_active"]))
    assert final["lcd_res"] is True
    assert final["lcd_bl"] is True


@cocotb.test()
async def test_frame_start_matches_full_frame_transcript_prefix_for_small_tile(dut):
    await reset_dut(dut)
    await wait_until(dut, lambda snap: bool(snap["init_done"]) and not bool(snap["frame_active"]))

    tile = [0, 1, 2, 3]
    frame = bytearray(160 * 144)
    frame[: len(tile)] = bytes(tile)
    expected = generate_frame_transcript(bytes(frame))
    expected_prefix = expected[: 11 + (len(tile) * 2)]

    transcript = await collect_bytes(
        dut,
        expected_count=len(expected_prefix),
        frame_start_at_cycle=0,
        pixel_stream=tile,
        max_cycles=5000,
    )
    assert_transcript_matches(transcript, expected_prefix)

    for index, shade in enumerate(tile):
        expected_hi = expected_prefix[11 + (index * 2)][1]
        expected_lo = expected_prefix[12 + (index * 2)][1]
        actual_hi = transcript[11 + (index * 2)][1]
        actual_lo = transcript[12 + (index * 2)][1]
        expected_word = (expected_hi << 8) | expected_lo
        actual_word = (actual_hi << 8) | actual_lo
        assert abs(actual_word - expected_word) <= 1, (
            f"pixel[{index}] shade={shade} expected_rgb565=0x{expected_word:04X} actual_rgb565=0x{actual_word:04X}"
        )

    for _ in range(2000):
        advanced = await step(dut, pixel_valid=False, pixel_shade=0)
        if advanced["pixel_count"] >= len(tile):
            break
    else:
        raise AssertionError("pixel_count did not advance through the requested tile")

    assert advanced["frame_active"] is True
    assert advanced["pixel_count"] >= len(tile)
