# top = ppu::rtl::core_test_top::core_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


PHASE_LCD_OFF = 0
PHASE_OAM = 1
PHASE_TRANSFER = 2
PHASE_HBLANK = 3
PHASE_VBLANK = 4

MODE_LCD_OFF = 0
MODE_OAM = 1
MODE_TRANSFER = 2
MODE_HBLANK = 3
MODE_VBLANK = 4

FRAME_DOTS = 154 * 456


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "phase": value & 0x7,
        "ly": (value >> 3) & 0xFF,
        "dot": (value >> 11) & 0x1FF,
        "mode": (value >> 20) & 0x7,
        "stat_line": bool((value >> 23) & 0x1),
        "vblank_irq": bool((value >> 24) & 0x1),
        "stat_irq": bool((value >> 25) & 0x1),
    }


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.dot_ce_i.value = 0
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step(dut, *, dot_ce: bool = True) -> dict[str, int | bool]:
    dut.dot_ce_i.value = int(dot_ce)
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_one_frame_mode_sequence(dut):
    await reset_dut(dut)

    saw_oam_to_transfer = False
    saw_transfer_to_hblank = False
    saw_hblank_to_oam = False
    saw_vblank_range = True
    saw_frame_wrap = False
    prev = decode_output(int(dut.output__.value))

    for _ in range(FRAME_DOTS):
        snapshot = await step(dut)
        if prev["phase"] == PHASE_OAM and snapshot["phase"] == PHASE_TRANSFER:
            saw_oam_to_transfer = True
        if prev["phase"] == PHASE_TRANSFER and snapshot["phase"] == PHASE_HBLANK:
            saw_transfer_to_hblank = True
        if prev["phase"] == PHASE_HBLANK and snapshot["phase"] == PHASE_OAM and snapshot["ly"] < 144:
            saw_hblank_to_oam = True
        if snapshot["mode"] == MODE_VBLANK and not (144 <= int(snapshot["ly"]) <= 153):
            saw_vblank_range = False
        if prev["ly"] == 153 and snapshot["ly"] == 0 and snapshot["phase"] == PHASE_OAM:
            saw_frame_wrap = True
        prev = snapshot

    assert saw_oam_to_transfer
    assert saw_transfer_to_hblank
    assert saw_hblank_to_oam
    assert saw_vblank_range
    assert saw_frame_wrap
    assert prev["ly"] == 0, prev


@cocotb.test()
async def test_dot_ce_hold(dut):
    await reset_dut(dut)

    await step(dut, dot_ce=True)
    held_baseline = await step(dut, dot_ce=False)

    for _ in range(99):
        held = await step(dut, dot_ce=False)
        assert held == held_baseline, (held, held_baseline)

    resumed = await step(dut, dot_ce=True)
    assert resumed != held_baseline, (resumed, held_baseline)
