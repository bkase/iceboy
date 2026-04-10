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

SUITE_NAME = "test_window.py"


def case_logger(case_name: str) -> TestLogger:
    suite = TestLogger(suite_name=SUITE_NAME, stream=sys.stdout, color=False)
    suite.suite()
    return suite.bind_case(case_name)


def pack_shades(shades: list[int]) -> int:
    value = 0
    for index, shade in enumerate(shades[:16]):
        value |= (shade & 0x3) << (index * 2)
    return value


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "next_fifo_count": (value >> 32) & 0x1F,
        "pixel_valid": bool((value >> 37) & 0x1),
        "discard_applied": bool((value >> 48) & 0x1),
        "next_discard_scx": (value >> 49) & 0x7,
        "window_state": (value >> 52) & 0x3,
        "window_win_x": (value >> 54) & 0x1F,
        "window_win_line": (value >> 59) & 0xFF,
        "next_window_line": (value >> 67) & 0xFF,
        "restart_fetcher": bool((value >> 75) & 0x1),
        "stall_dots_added": (value >> 76) & 0x1F,
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
) -> dict[str, int | bool]:
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
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


def require(logger: TestLogger, snapshot: dict[str, int | bool], *, expected: dict[str, int | bool]) -> None:
    for field, value in expected.items():
        assert logger.check(field, expected=value, actual=snapshot[field]), (
            f"{field} mismatch: expected={value} actual={snapshot[field]} snapshot={snapshot}"
        )


@cocotb.test()
async def test_window_activation_basic_at_x0(dut):
    logger = case_logger("test_window_activation_basic_at_x0")
    logger.step("Arm the window on line start and trigger immediately at WX=7, X=0")
    snapshot = await sample(
        dut,
        fifo_count=4,
        fifo_shades=[1, 2, 3, 0] + [0] * 12,
        window_state=WINDOW_INACTIVE,
        window_line=0,
        wy_triggered=True,
        window_enable_at_mode2_start=True,
        wx_live=7,
        x_out=0,
        line_start=True,
    )
    require(
        logger,
        snapshot,
        expected={
            "window_state": WINDOW_ACTIVE,
            "window_win_x": 0,
            "window_win_line": 0,
            "next_window_line": 1,
            "restart_fetcher": True,
            "stall_dots_added": 6,
            "next_fifo_count": 0,
            "pixel_valid": False,
        },
    )


@cocotb.test()
async def test_window_trigger_drops_stale_bg_push_on_restart(dut):
    logger = case_logger("test_window_trigger_drops_stale_bg_push_on_restart")
    logger.step("When the window triggers on the same dot as a BG push, the stale BG row must be discarded")
    snapshot = await sample(
        dut,
        fifo_count=0,
        push_valid=True,
        push_row=[3] * 8,
        window_state=WINDOW_INACTIVE,
        window_line=0,
        wy_triggered=True,
        window_enable_at_mode2_start=True,
        wx_live=15,
        x_out=8,
        line_start=True,
    )
    require(
        logger,
        snapshot,
        expected={
            "window_state": WINDOW_ACTIVE,
            "next_window_line": 1,
            "restart_fetcher": True,
            "stall_dots_added": 6,
            "next_fifo_count": 0,
            "pixel_valid": False,
        },
    )


@cocotb.test()
async def test_window_requires_wy_and_mode2_enable_to_arm(dut):
    logger = case_logger("test_window_requires_wy_and_mode2_enable_to_arm")

    logger.step("Without WY trigger, the window stays inactive even if WX condition is true")
    no_wy = await sample(
        dut,
        window_state=WINDOW_INACTIVE,
        window_line=3,
        wy_triggered=False,
        window_enable_at_mode2_start=True,
        wx_live=7,
        x_out=0,
        line_start=True,
    )
    require(
        logger,
        no_wy,
        expected={
            "window_state": WINDOW_INACTIVE,
            "next_window_line": 3,
            "restart_fetcher": False,
        },
    )

    logger.step("Without mode-2 enable sampling, the window also stays inactive")
    no_enable = await sample(
        dut,
        window_state=WINDOW_INACTIVE,
        window_line=3,
        wy_triggered=True,
        window_enable_at_mode2_start=False,
        wx_live=7,
        x_out=0,
        line_start=True,
    )
    require(
        logger,
        no_enable,
        expected={
            "window_state": WINDOW_INACTIVE,
            "next_window_line": 3,
            "restart_fetcher": False,
        },
    )


@cocotb.test()
async def test_window_wx_trigger_and_counter_progression(dut):
    logger = case_logger("test_window_wx_trigger_and_counter_progression")

    logger.step("WX=87 triggers when rendered X reaches 80")
    delayed = await sample(
        dut,
        fifo_count=2,
        fifo_shades=[2, 1] + [0] * 14,
        window_state=WINDOW_INACTIVE,
        window_line=5,
        wy_triggered=True,
        window_enable_at_mode2_start=True,
        wx_live=87,
        x_out=79,
        line_start=True,
    )
    require(
        logger,
        delayed,
        expected={
            "window_state": WINDOW_ARMED,
            "restart_fetcher": False,
            "next_window_line": 5,
            "next_fifo_count": 1,
            "pixel_valid": True,
        },
    )

    triggered = await sample(
        dut,
        fifo_count=2,
        fifo_shades=[2, 1] + [0] * 14,
        window_state=WINDOW_ARMED,
        window_line=5,
        wy_triggered=True,
        window_enable_at_mode2_start=True,
        wx_live=87,
        x_out=80,
    )
    require(
        logger,
        triggered,
        expected={
            "window_state": WINDOW_ACTIVE,
            "window_win_x": 0,
            "window_win_line": 5,
            "next_window_line": 6,
            "restart_fetcher": True,
            "stall_dots_added": 6,
            "next_fifo_count": 0,
        },
    )

    logger.step("Only lines that actually render the window advance next_window_line")
    continued = await sample(
        dut,
        fifo_count=0,
        fifo_shades=[0] * 16,
        window_state=WINDOW_ACTIVE,
        active_win_x=0,
        active_win_line=5,
        window_line=6,
        note_window_tile_push=True,
    )
    require(
        logger,
        continued,
        expected={
            "window_state": WINDOW_ACTIVE,
            "window_win_x": 1,
            "window_win_line": 5,
            "next_window_line": 6,
            "restart_fetcher": False,
            "stall_dots_added": 0,
        },
    )


@cocotb.test()
async def test_window_midframe_disable_resume_and_vblank_reset(dut):
    logger = case_logger("test_window_midframe_disable_resume_and_vblank_reset")

    logger.step("A mid-frame disable leaves the stored window line untouched")
    disabled = await sample(
        dut,
        window_state=WINDOW_ACTIVE,
        active_win_x=3,
        active_win_line=7,
        window_line=8,
        wy_triggered=True,
        window_enable_at_mode2_start=False,
        wx_live=7,
        x_out=0,
        line_start=True,
        win_enable=False,
    )
    require(
        logger,
        disabled,
        expected={
            "window_state": WINDOW_INACTIVE,
            "next_window_line": 8,
            "restart_fetcher": False,
            "stall_dots_added": 0,
        },
    )

    logger.step("Re-enabling later in the frame resumes from the preserved counter")
    resumed = await sample(
        dut,
        window_state=WINDOW_INACTIVE,
        window_line=8,
        wy_triggered=True,
        window_enable_at_mode2_start=True,
        wx_live=7,
        x_out=0,
        line_start=True,
        win_enable=True,
    )
    require(
        logger,
        resumed,
        expected={
            "window_state": WINDOW_ACTIVE,
            "window_win_line": 8,
            "next_window_line": 9,
            "restart_fetcher": True,
            "stall_dots_added": 6,
        },
    )

    logger.step("Frame start still arms line 0 immediately when WY already matched and WX is on-screen")
    reset = await sample(
        dut,
        window_state=WINDOW_ACTIVE,
        active_win_x=4,
        active_win_line=9,
        window_line=10,
        wy_triggered=True,
        window_enable_at_mode2_start=True,
        wx_live=7,
        x_out=0,
        frame_start=True,
        line_start=True,
    )
    require(
        logger,
        reset,
        expected={
            "window_state": WINDOW_ACTIVE,
            "window_win_x": 0,
            "window_win_line": 0,
            "next_window_line": 1,
            "restart_fetcher": True,
            "stall_dots_added": 6,
        },
    )


@cocotb.test()
async def test_window_trigger_adds_fixed_six_stall_dots_once(dut):
    logger = case_logger("test_window_trigger_adds_fixed_six_stall_dots_once")

    logger.step("The takeover dot adds a fixed 6-dot stall budget")
    triggered = await sample(
        dut,
        window_state=WINDOW_ARMED,
        window_line=4,
        wy_triggered=True,
        window_enable_at_mode2_start=True,
        wx_live=15,
        x_out=8,
    )
    require(
        logger,
        triggered,
        expected={
            "window_state": WINDOW_ACTIVE,
            "restart_fetcher": True,
            "stall_dots_added": 6,
            "next_window_line": 5,
        },
    )

    logger.step("Once active on the line, later pixels do not add another 6")
    continued = await sample(
        dut,
        window_state=WINDOW_ACTIVE,
        active_win_x=0,
        active_win_line=4,
        window_line=5,
        wy_triggered=True,
        window_enable_at_mode2_start=True,
        wx_live=15,
        x_out=9,
    )
    require(
        logger,
        continued,
        expected={
            "window_state": WINDOW_ACTIVE,
            "restart_fetcher": False,
            "stall_dots_added": 0,
            "next_window_line": 5,
        },
    )
