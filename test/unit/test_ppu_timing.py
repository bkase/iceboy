# top = ppu::rtl::timing_test_top::timing_test_top
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

MODE_HBLANK = 0
MODE_VBLANK = 1
MODE_OAM = 2
MODE_TRANSFER = 3
MODE_LCD_OFF = 4


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "next_phase": value & 0x7,
        "next_ly": (value >> 3) & 0xFF,
        "next_scx_low3": (value >> 11) & 0x7,
        "next_wy_triggered": bool((value >> 14) & 0x1),
        "next_window_enable": bool((value >> 15) & 0x1),
        "line_start": bool((value >> 16) & 0x1),
        "frame_start": bool((value >> 17) & 0x1),
        "next_run": (value >> 18) & 0x3,
        "transition_mode": (value >> 20) & 0x7,
        "transition_lcd_enabled": bool((value >> 23) & 0x1),
        "transition_ly": (value >> 24) & 0xFF,
        "transition_run": (value >> 32) & 0x3,
    }


async def sample(
    dut,
    *,
    run: int,
    phase: int,
    ly: int,
    dot_in_line: int,
    line: int = 0,
    dots_left: int = 0,
    sampled_scx_low3: int = 0,
    sampled_wy_triggered: bool = False,
    sampled_window_enable: bool = False,
    scx: int = 0,
    wy: int = 0,
    win_enable: bool = False,
    old_lcdc_enable: bool = True,
    new_lcdc_enable: bool = True,
) -> dict[str, int | bool]:
    dut.run_i.value = run
    dut.phase_i.value = phase
    dut.ly_i.value = ly
    dut.dot_in_line_i.value = dot_in_line
    dut.line_i.value = line
    dut.dots_left_i.value = dots_left
    dut.sampled_scx_low3_i.value = sampled_scx_low3
    dut.sampled_wy_triggered_i.value = int(sampled_wy_triggered)
    dut.sampled_window_enable_i.value = int(sampled_window_enable)
    dut.scx_i.value = scx
    dut.wy_i.value = wy
    dut.win_enable_i.value = int(win_enable)
    dut.old_lcdc_enable_i.value = int(old_lcdc_enable)
    dut.new_lcdc_enable_i.value = int(new_lcdc_enable)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_visible_line_mode_sequence_transitions(dut):
    oam_hold = await sample(dut, run=RUN_RUNNING, phase=PHASE_OAM, ly=12, dot_in_line=78)
    assert oam_hold["next_phase"] == PHASE_OAM
    assert oam_hold["next_ly"] == 12
    assert not oam_hold["line_start"]

    to_transfer = await sample(dut, run=RUN_RUNNING, phase=PHASE_OAM, ly=12, dot_in_line=79, sampled_scx_low3=5)
    assert to_transfer["next_phase"] == PHASE_TRANSFER
    assert to_transfer["next_ly"] == 12
    assert not to_transfer["line_start"]

    transfer_hold = await sample(dut, run=RUN_RUNNING, phase=PHASE_TRANSFER, ly=12, dot_in_line=250, sampled_scx_low3=5)
    assert transfer_hold["next_phase"] == PHASE_TRANSFER
    assert transfer_hold["next_ly"] == 12

    to_hblank = await sample(dut, run=RUN_RUNNING, phase=PHASE_TRANSFER, ly=12, dot_in_line=251, sampled_scx_low3=5)
    assert to_hblank["next_phase"] == PHASE_HBLANK
    assert to_hblank["next_ly"] == 12
    assert not to_hblank["line_start"]


@cocotb.test()
async def test_line_wrap_enters_next_visible_line_and_samples_mode2_inputs(dut):
    snapshot = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_HBLANK,
        ly=41,
        dot_in_line=455,
        sampled_scx_low3=1,
        scx=0x1D,
        wy=42,
        win_enable=True,
    )
    assert snapshot["next_phase"] == PHASE_OAM
    assert snapshot["next_ly"] == 42
    assert snapshot["line_start"]
    assert not snapshot["frame_start"]
    assert snapshot["next_scx_low3"] == 0x1D & 0x7
    assert snapshot["next_wy_triggered"] is True
    assert snapshot["next_window_enable"] is True


@cocotb.test()
async def test_visible_line_143_enters_vblank_and_vblank_wraps_frame(dut):
    to_vblank = await sample(dut, run=RUN_RUNNING, phase=PHASE_HBLANK, ly=143, dot_in_line=455)
    assert to_vblank["next_phase"] == PHASE_VBLANK
    assert to_vblank["next_ly"] == 144
    assert to_vblank["line_start"]
    assert not to_vblank["frame_start"]

    stay_vblank = await sample(dut, run=RUN_RUNNING, phase=PHASE_VBLANK, ly=144, line=144, dot_in_line=455)
    assert stay_vblank["next_phase"] == PHASE_VBLANK
    assert stay_vblank["next_ly"] == 145
    assert stay_vblank["line_start"]
    assert not stay_vblank["frame_start"]

    wrap_frame = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_VBLANK,
        ly=153,
        line=153,
        dot_in_line=455,
        sampled_wy_triggered=True,
        wy=7,
    )
    assert wrap_frame["next_phase"] == PHASE_OAM
    assert wrap_frame["next_ly"] == 0
    assert wrap_frame["line_start"]
    assert wrap_frame["frame_start"]
    assert wrap_frame["next_run"] == RUN_RUNNING
    assert wrap_frame["next_wy_triggered"] is False


@cocotb.test()
async def test_warmup_frame_promotes_to_running_on_first_frame_boundary(dut):
    snapshot = await sample(
        dut,
        run=RUN_WARMUP,
        phase=PHASE_VBLANK,
        ly=153,
        line=153,
        dot_in_line=455,
    )
    assert snapshot["frame_start"]
    assert snapshot["next_run"] == RUN_RUNNING


@cocotb.test()
async def test_lcd_disable_resets_visible_state_and_mode_projection(dut):
    snapshot = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_TRANSFER,
        ly=99,
        dot_in_line=120,
        old_lcdc_enable=True,
        new_lcdc_enable=False,
    )
    assert snapshot["transition_run"] == RUN_DISABLED
    assert snapshot["transition_mode"] == MODE_LCD_OFF
    assert snapshot["transition_lcd_enabled"] is False
    assert snapshot["transition_ly"] == 0


@cocotb.test()
async def test_lcd_enable_enters_warmup_blank_frame(dut):
    snapshot = await sample(
        dut,
        run=RUN_DISABLED,
        phase=PHASE_LCD_OFF,
        ly=0,
        dot_in_line=0,
        scx=0x23,
        wy=0,
        win_enable=True,
        old_lcdc_enable=False,
        new_lcdc_enable=True,
    )
    assert snapshot["transition_run"] == RUN_WARMUP
    assert snapshot["transition_mode"] == MODE_OAM
    assert snapshot["transition_lcd_enabled"] is True
    assert snapshot["transition_ly"] == 0
