# top = ppu::rtl::fifo_test_top::fifo_test_top
from __future__ import annotations

import sys
from pathlib import Path

import cocotb
from cocotb.triggers import ReadOnly, Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from logging_std import TestLogger


WINDOW_INACTIVE = 0
WINDOW_ARMED = 1
WINDOW_ACTIVE = 2

SUITE_NAME = "test_bg_fifo.py"


def case_logger(case_name: str) -> TestLogger:
    suite = TestLogger(suite_name=SUITE_NAME, stream=sys.stdout, color=False)
    suite.suite()
    return suite.bind_case(case_name)


def pack_shades(shades: list[int]) -> int:
    value = 0
    for index, shade in enumerate(shades[:16]):
        value |= (shade & 0x3) << (index * 2)
    return value


def unpack_shades(value: int) -> list[int]:
    return [(value >> (index * 2)) & 0x3 for index in range(16)]


def decode_output(value: int) -> dict[str, int | bool | list[int]]:
    packed_shades = value & 0xFFFFFFFF
    return {
        "next_fifo_shades": unpack_shades(packed_shades),
        "next_fifo_count": (value >> 32) & 0x1F,
        "pixel_valid": bool((value >> 37) & 0x1),
        "pixel_shade": (value >> 38) & 0x3,
        "pixel_palette": (value >> 40) & 0xFF,
        "discard_applied": bool((value >> 48) & 0x1),
        "next_discard_scx": (value >> 49) & 0x7,
        "window_state": (value >> 52) & 0x3,
        "window_win_x": (value >> 54) & 0x1F,
        "window_win_line": (value >> 59) & 0xFF,
        "next_window_line": (value >> 67) & 0xFF,
        "restart_fetcher": bool((value >> 75) & 0x1),
        "has_room_for_row": bool((value >> 81) & 0x1),
    }


async def sample(
    dut,
    *,
    fifo_count: int = 0,
    fifo_shades: list[int] | None = None,
    fifo_palette: int = 0xE4,
    scx_low3: int = 0,
    discard_scx: int = 0,
    push_valid: bool = False,
    push_row: list[int] | None = None,
    push_palette: int = 0xE4,
    window_state: int = WINDOW_INACTIVE,
    active_win_x: int = 0,
    active_win_line: int = 0,
    window_line: int = 0,
    wy_triggered: bool = False,
    window_enable_at_mode2_start: bool = False,
    wx_live: int = 0,
    x_out: int = 0,
    frame_start: bool = False,
    line_start: bool = False,
    note_window_tile_push: bool = False,
    win_enable: bool = True,
    current_stall_dots: int = 0,
) -> dict[str, int | bool | list[int]]:
    fifo_shades = fifo_shades or [0] * 16
    push_row = push_row or [0] * 8
    dut.fifo_count_i.value = fifo_count & 0x1F
    dut.fifo_shades_i.value = pack_shades(fifo_shades)
    dut.fifo_palette_i.value = fifo_palette & 0xFF
    dut.scx_low3_i.value = scx_low3 & 0x7
    dut.discard_scx_i.value = discard_scx & 0x7
    dut.push_valid_i.value = int(push_valid)
    dut.push_row_i.value = pack_shades(push_row)
    dut.push_palette_i.value = push_palette & 0xFF
    dut.window_state_i.value = window_state & 0x3
    dut.active_win_x_i.value = active_win_x & 0x1F
    dut.active_win_line_i.value = active_win_line & 0xFF
    dut.window_line_i.value = window_line & 0xFF
    dut.wy_triggered_i.value = int(wy_triggered)
    dut.window_enable_at_mode2_start_i.value = int(window_enable_at_mode2_start)
    dut.wx_live_i.value = wx_live & 0xFF
    dut.x_out_i.value = x_out & 0xFF
    dut.frame_start_i.value = int(frame_start)
    dut.line_start_i.value = int(line_start)
    dut.note_window_tile_push_i.value = int(note_window_tile_push)
    dut.win_enable_i.value = int(win_enable)
    dut.current_stall_dots_i.value = current_stall_dots & 0x1F
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


def require(logger: TestLogger, snapshot: dict[str, int | bool | list[int]], *, expected: dict[str, int | bool | list[int]]) -> None:
    for field, value in expected.items():
        assert logger.check(field, expected=value, actual=snapshot[field]), (
            f"{field} mismatch: expected={value} actual={snapshot[field]} snapshot={snapshot}"
        )


@cocotb.test()
async def test_fifo_push_pop_and_depth_tracking(dut):
    logger = case_logger("test_fifo_push_pop_and_depth_tracking")
    logger.step("Push eight shades into an empty FIFO")
    pushed = await sample(
        dut,
        fifo_count=0,
        fifo_shades=[0] * 16,
        push_valid=True,
        push_row=[0, 1, 2, 3, 0, 1, 2, 3],
        push_palette=0xE4,
    )
    require(
        logger,
        pushed,
        expected={
            "next_fifo_count": 7,
            "pixel_valid": True,
            "pixel_shade": 0,
            "pixel_palette": 0xE4,
            "next_fifo_shades": [1, 2, 3, 0, 1, 2, 3, 0] + [0] * 8,
        },
    )

    logger.step("Pop from a non-empty FIFO without a push")
    popped = await sample(
        dut,
        fifo_count=4,
        fifo_shades=[3, 2, 1, 0] + [0] * 12,
        discard_scx=0,
    )
    require(
        logger,
        popped,
        expected={
            "next_fifo_count": 3,
            "pixel_valid": True,
            "pixel_shade": 3,
            "next_fifo_shades": [2, 1, 0] + [0] * 13,
        },
    )


@cocotb.test()
async def test_scx_discard_suppresses_output_until_counter_reaches_zero(dut):
    logger = case_logger("test_scx_discard_suppresses_output_until_counter_reaches_zero")
    fifo = [0, 1, 2, 3, 0, 1, 2, 3] + [0] * 8

    logger.step("Discard the first three sampled pixels")
    discard = await sample(dut, fifo_count=8, fifo_shades=fifo, discard_scx=3, scx_low3=5)
    require(
        logger,
        discard,
        expected={
            "next_fifo_count": 7,
            "pixel_valid": False,
            "discard_applied": True,
            "next_discard_scx": 2,
            "pixel_shade": 0,
        },
    )

    logger.step("Once the discard counter is zero, pixels become visible")
    visible = await sample(dut, fifo_count=5, fifo_shades=[1, 2, 3, 0, 1] + [0] * 11, discard_scx=0, scx_low3=7)
    require(
        logger,
        visible,
        expected={
            "pixel_valid": True,
            "discard_applied": False,
            "next_discard_scx": 0,
            "pixel_shade": 1,
        },
    )


@cocotb.test()
async def test_fifo_empty_and_full_stall_cases(dut):
    logger = case_logger("test_fifo_empty_and_full_stall_cases")

    logger.step("Empty FIFO produces no pixel and no underflow")
    empty = await sample(dut, fifo_count=0, fifo_shades=[0] * 16)
    require(
        logger,
        empty,
        expected={"next_fifo_count": 0, "pixel_valid": False, "discard_applied": False},
    )

    logger.step("A full FIFO rejects another eight-pixel push")
    full = await sample(
        dut,
        fifo_count=16,
        fifo_shades=[0, 1, 2, 3] * 4,
        push_valid=True,
        push_row=[3, 3, 3, 3, 2, 2, 2, 2],
    )
    require(
        logger,
        full,
        expected={
            "next_fifo_count": 15,
            "pixel_valid": True,
            "pixel_shade": 0,
            "next_fifo_shades": [1, 2, 3] + [0, 1, 2, 3] * 3 + [0] * 1,
        },
    )


@cocotb.test()
async def test_bg_push_requires_empty_fifo(dut):
    logger = case_logger("test_bg_push_requires_empty_fifo")

    logger.step("Only an empty FIFO has room for a full eight-pixel BG push")
    for count in [0, 1, 4, 7, 8, 16]:
        snapshot = await sample(
            dut,
            fifo_count=count,
            fifo_shades=[0, 1, 2, 3] * 4,
            push_valid=True,
            push_row=[3, 2, 1, 0, 3, 2, 1, 0],
        )
        require(
            logger,
            snapshot,
            expected={
                "has_room_for_row": count == 0,
                "next_fifo_count": 7 if count == 0 else max(count - 1, 0),
            },
        )


@cocotb.test()
async def test_window_activation_clears_fifo_and_restarts_fetcher(dut):
    logger = case_logger("test_window_activation_clears_fifo_and_restarts_fetcher")

    logger.step("Window trigger clears the background FIFO and increments the internal window line")
    activated = await sample(
        dut,
        fifo_count=6,
        fifo_shades=[3, 2, 1, 0, 3, 2] + [0] * 10,
        discard_scx=2,
        window_state=WINDOW_INACTIVE,
        window_line=4,
        wy_triggered=True,
        window_enable_at_mode2_start=True,
        wx_live=15,
        x_out=8,
        line_start=True,
    )
    require(
        logger,
        activated,
        expected={
            "next_fifo_count": 0,
            "pixel_valid": False,
            "window_state": WINDOW_ACTIVE,
            "window_win_x": 0,
            "window_win_line": 4,
            "next_window_line": 5,
            "restart_fetcher": True,
            "next_discard_scx": 2,
        },
    )

    logger.step("Window tile pushes advance the internal tile X counter")
    advanced = await sample(
        dut,
        fifo_count=0,
        fifo_shades=[0] * 16,
        window_state=WINDOW_ACTIVE,
        active_win_x=0,
        active_win_line=4,
        window_line=5,
        note_window_tile_push=True,
    )
    require(
        logger,
        advanced,
        expected={"window_state": WINDOW_ACTIVE, "window_win_x": 1, "window_win_line": 4, "restart_fetcher": False},
    )
