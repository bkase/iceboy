# top = ppu::rtl::irq_test_top::irq_test_top
from __future__ import annotations

import cocotb
from cocotb.triggers import ReadOnly, Timer


RUN_DISABLED = 0
RUN_WARMUP = 1
RUN_RUNNING = 2

PHASE_LCD_OFF = 0
PHASE_OAM = 1
PHASE_TRANSFER = 2
PHASE_HBLANK = 3
PHASE_VBLANK = 4


def decode_output(value: int) -> dict[str, bool]:
    return {
        "lyc_match": bool(value & 0x1),
        "new_line": bool((value >> 1) & 0x1),
        "next_line_high": bool((value >> 2) & 0x1),
        "entered_vblank": bool((value >> 3) & 0x1),
        "quirk_pulse": bool((value >> 4) & 0x1),
        "edge_req": bool((value >> 5) & 0x1),
        "vblank_req": bool((value >> 6) & 0x1),
        "stat_req": bool((value >> 7) & 0x1),
        "mode1_sel": bool((value >> 8) & 0x1),
        "mode2_sel": bool((value >> 9) & 0x1),
    }


async def sample(
    dut,
    *,
    prev_run: int,
    prev_phase: int,
    next_run: int,
    next_phase: int,
    line: int = 0,
    ly: int = 0,
    lyc: int = 0,
    prev_line_high: bool = False,
    lyc_sel: bool = False,
    mode2_sel: bool = False,
    mode1_sel: bool = False,
    mode0_sel: bool = False,
    stat_write_seen: bool = False,
    quirk_enable: bool = False,
) -> dict[str, bool]:
    dut.prev_run_i.value = prev_run
    dut.prev_phase_i.value = prev_phase
    dut.next_run_i.value = next_run
    dut.next_phase_i.value = next_phase
    dut.line_i.value = line
    dut.ly_i.value = ly
    dut.lyc_i.value = lyc
    dut.prev_line_high_i.value = int(prev_line_high)
    dut.lyc_sel_i.value = int(lyc_sel)
    dut.mode2_sel_i.value = int(mode2_sel)
    dut.mode1_sel_i.value = int(mode1_sel)
    dut.mode0_sel_i.value = int(mode0_sel)
    dut.stat_write_seen_i.value = int(stat_write_seen)
    dut.quirk_enable_i.value = int(quirk_enable)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_lyc_source_raises_stat_line_and_request_on_rising_edge(dut):
    snapshot = await sample(
        dut,
        prev_run=RUN_RUNNING,
        prev_phase=PHASE_HBLANK,
        next_run=RUN_RUNNING,
        next_phase=PHASE_HBLANK,
        ly=37,
        lyc=37,
        lyc_sel=True,
    )
    assert snapshot["lyc_match"] is True
    assert snapshot["new_line"] is True
    assert snapshot["next_line_high"] is True
    assert snapshot["stat_req"] is True
    assert snapshot["vblank_req"] is False


@cocotb.test()
async def test_stat_blocking_suppresses_second_interrupt_when_line_stays_high(dut):
    snapshot = await sample(
        dut,
        prev_run=RUN_RUNNING,
        prev_phase=PHASE_OAM,
        next_run=RUN_RUNNING,
        next_phase=PHASE_VBLANK,
        line=144,
        ly=144,
        prev_line_high=True,
        mode2_sel=True,
        mode1_sel=True,
    )
    assert snapshot["new_line"] is True
    assert snapshot["next_line_high"] is True
    assert snapshot["entered_vblank"] is True
    assert snapshot["vblank_req"] is True
    assert snapshot["stat_req"] is False


@cocotb.test()
async def test_line_can_fall_without_request_and_rise_again_later(dut):
    fall = await sample(
        dut,
        prev_run=RUN_RUNNING,
        prev_phase=PHASE_OAM,
        next_run=RUN_RUNNING,
        next_phase=PHASE_TRANSFER,
        ly=12,
        prev_line_high=True,
        mode2_sel=True,
    )
    assert fall["new_line"] is False
    assert fall["next_line_high"] is False
    assert fall["stat_req"] is False

    rise = await sample(
        dut,
        prev_run=RUN_RUNNING,
        prev_phase=PHASE_TRANSFER,
        next_run=RUN_RUNNING,
        next_phase=PHASE_HBLANK,
        ly=12,
        prev_line_high=False,
        mode0_sel=True,
    )
    assert rise["new_line"] is True
    assert rise["next_line_high"] is True
    assert rise["stat_req"] is True


@cocotb.test()
async def test_vblank_request_only_fires_on_mode1_entry(dut):
    entry = await sample(
        dut,
        prev_run=RUN_RUNNING,
        prev_phase=PHASE_HBLANK,
        next_run=RUN_RUNNING,
        next_phase=PHASE_VBLANK,
        line=144,
        ly=144,
        mode1_sel=True,
    )
    assert entry["entered_vblank"] is True
    assert entry["vblank_req"] is True

    held = await sample(
        dut,
        prev_run=RUN_RUNNING,
        prev_phase=PHASE_VBLANK,
        next_run=RUN_RUNNING,
        next_phase=PHASE_VBLANK,
        line=145,
        ly=145,
        mode1_sel=True,
    )
    assert held["entered_vblank"] is False
    assert held["vblank_req"] is False


@cocotb.test()
async def test_stat_write_quirk_hook_is_feature_gated(dut):
    disabled = await sample(
        dut,
        prev_run=RUN_RUNNING,
        prev_phase=PHASE_TRANSFER,
        next_run=RUN_RUNNING,
        next_phase=PHASE_TRANSFER,
        stat_write_seen=True,
        quirk_enable=False,
    )
    assert disabled["quirk_pulse"] is False
    assert disabled["stat_req"] is False

    enabled = await sample(
        dut,
        prev_run=RUN_RUNNING,
        prev_phase=PHASE_TRANSFER,
        next_run=RUN_RUNNING,
        next_phase=PHASE_TRANSFER,
        stat_write_seen=True,
        quirk_enable=True,
    )
    assert enabled["quirk_pulse"] is True
    assert enabled["stat_req"] is True
    assert enabled["next_line_high"] is False
