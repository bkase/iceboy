# top = ppu::rtl::scanout_test_top::scanout_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


PHASE_LCD_OFF = 0
PHASE_OAM = 1
PHASE_TRANSFER = 2
PHASE_HBLANK = 3
PHASE_VBLANK = 4

SCANOUT_PIXEL = 0
SCANOUT_BLANK = 1
SCANOUT_FRAME_START = 2
SCANOUT_LINE_START = 3

BLANK_LCD_DISABLED = 0
BLANK_WARMUP = 1
BLANK_NON_VISIBLE_LINE = 2
BLANK_NON_VISIBLE_DOT = 3


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "phase": value & 0x7,
        "ly": (value >> 3) & 0xFF,
        "scanout_valid": bool((value >> 11) & 0x1),
        "scanout_kind": (value >> 12) & 0x3,
        "scanout_y": (value >> 14) & 0xFF,
        "blank_reason": (value >> 22) & 0x3,
    }


async def reset_dut(
    dut,
    *,
    seed_valid: bool = False,
    seed_run: int = 0,
    seed_phase: int = 0,
    seed_ly: int = 0,
    seed_dot_in_line: int = 0,
) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.dot_ce_i.value = 0
    dut.write_valid_i.value = 0
    dut.write_target_i.value = 0
    dut.write_value_i.value = 0
    dut.seed_valid_i.value = int(seed_valid)
    dut.seed_run_i.value = seed_run
    dut.seed_phase_i.value = seed_phase
    dut.seed_ly_i.value = seed_ly
    dut.seed_dot_in_line_i.value = seed_dot_in_line
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step(dut, *, dot_ce: bool = True, write_valid: bool = False, write_target: int = 0, write_value: int = 0) -> dict[str, int | bool]:
    dut.dot_ce_i.value = int(dot_ce)
    dut.write_valid_i.value = int(write_valid)
    dut.write_target_i.value = write_target
    dut.write_value_i.value = write_value
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    dut.write_valid_i.value = 0
    return snapshot


@cocotb.test()
async def test_visible_nonpixel_dots_emit_blank_reason(dut):
    await reset_dut(dut)

    snapshot = await step(dut)
    assert snapshot["scanout_valid"] is True
    assert snapshot["scanout_kind"] == SCANOUT_BLANK
    assert snapshot["scanout_y"] == 0
    assert snapshot["blank_reason"] == BLANK_NON_VISIBLE_DOT
    assert snapshot["phase"] == PHASE_OAM


@cocotb.test()
async def test_vblank_entry_emits_line_start_then_nonvisible_blank(dut):
    await reset_dut(dut, seed_valid=True, seed_run=2, seed_phase=3, seed_ly=143, seed_dot_in_line=400)

    line_start = None
    for _ in range(64):
        snapshot = await step(dut)
        if snapshot["scanout_kind"] == SCANOUT_LINE_START and snapshot["scanout_y"] == 144:
            line_start = snapshot
            break

    assert line_start is not None
    assert line_start["ly"] == 144
    assert line_start["scanout_valid"] is True
    assert line_start["scanout_kind"] == SCANOUT_LINE_START
    assert line_start["scanout_y"] == 144
    assert line_start["phase"] == PHASE_VBLANK

    blank = await step(dut)
    assert blank["scanout_valid"] is True
    assert blank["scanout_kind"] == SCANOUT_BLANK
    assert blank["scanout_y"] == 144
    assert blank["blank_reason"] == BLANK_NON_VISIBLE_LINE


@cocotb.test()
async def test_lcd_disable_and_reenable_change_blank_reason(dut):
    await reset_dut(dut)

    disabled = await step(dut, write_valid=True, write_target=0, write_value=0x00)
    assert disabled["scanout_valid"] is True
    assert disabled["scanout_kind"] == SCANOUT_BLANK
    assert disabled["blank_reason"] == BLANK_LCD_DISABLED
    assert disabled["phase"] == PHASE_LCD_OFF

    warmup = await step(dut, write_valid=True, write_target=0, write_value=0x91)
    assert warmup["scanout_valid"] is True
    assert warmup["scanout_kind"] == SCANOUT_BLANK
    assert warmup["blank_reason"] == BLANK_WARMUP
