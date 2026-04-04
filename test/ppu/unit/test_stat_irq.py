# top = ppu::rtl::core_test_top::core_test_top
from __future__ import annotations

import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from logging_std import TestLogger


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

STAT_TARGET = 1
LYC_TARGET = 4
LCDC_TARGET = 0

STAT_SEL_MODE0 = 0x08
STAT_SEL_MODE1 = 0x10
STAT_SEL_MODE2 = 0x20
STAT_SEL_LYC = 0x40

LCDC_OFF = 0x11

FRAME_DOTS = 456 * 154

SUITE_NAME = "test_stat_irq.py"


def case_logger(case_name: str) -> TestLogger:
    suite = TestLogger(suite_name=SUITE_NAME, stream=sys.stdout, color=False)
    suite.suite()
    return suite.bind_case(case_name)


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "phase": value & 0x7,
        "ly": (value >> 3) & 0xFF,
        "dot": (value >> 11) & 0x1FF,
        "mode": (value >> 20) & 0x7,
        "stat_line": bool((value >> 23) & 0x1),
        "vblank_irq": bool((value >> 24) & 0x1),
        "stat_irq": bool((value >> 25) & 0x1),
        "run": (value >> 26) & 0x3,
        "first_frame_blank": bool((value >> 28) & 0x1),
        "stat_readback": (value >> 29) & 0xFF,
    }


def require(logger: TestLogger, field: str, expected: int | bool, actual: int | bool, *, snapshot: dict[str, int | bool]) -> None:
    assert logger.check(field, expected=expected, actual=actual), (
        f"{field} mismatch: expected={expected} actual={actual} snapshot={snapshot}"
    )


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.dot_ce_i.value = 0
    dut.write_valid_i.value = 0
    dut.write_target_i.value = 0
    dut.write_value_i.value = 0
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step(
    dut,
    *,
    dot_ce: bool = True,
    write_target: int | None = None,
    write_value: int = 0,
) -> dict[str, int | bool]:
    dut.dot_ce_i.value = int(dot_ce)
    dut.write_valid_i.value = int(write_target is not None)
    dut.write_target_i.value = (write_target or 0) & 0xF
    dut.write_value_i.value = write_value & 0xFF
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


async def advance_until(dut, predicate, *, max_dots: int = FRAME_DOTS) -> dict[str, int | bool]:
    for _ in range(max_dots):
        snapshot = await step(dut)
        if predicate(snapshot):
            return snapshot
    raise TimeoutError(f"predicate not met within {max_dots} dots")


@cocotb.test()
async def test_stat_readback_and_lyc_flag(dut):
    logger = case_logger("test_stat_readback_and_lyc_flag")
    await reset_dut(dut)

    logger.step("Program LYC=0 and enable all STAT select bits")
    await step(dut, write_target=LYC_TARGET, write_value=0x00)
    programmed = await step(dut, write_target=STAT_TARGET, write_value=STAT_SEL_MODE0 | STAT_SEL_MODE1 | STAT_SEL_MODE2 | STAT_SEL_LYC)
    require(logger, "stat_readback@ly0", 0xFE, programmed["stat_readback"], snapshot=programmed)
    require(logger, "stat_line@ly0", True, programmed["stat_line"], snapshot=programmed)

    logger.step("Advance to LY=1 and verify LYC coincidence bit clears")
    line1 = await advance_until(dut, lambda snap: snap["ly"] == 1 and snap["phase"] == PHASE_OAM)
    require(logger, "ly@line1", 1, line1["ly"], snapshot=line1)
    require(logger, "lyc_bit@line1", 0xFA, line1["stat_readback"], snapshot=line1)


@cocotb.test()
async def test_lyc_irq_fires_on_matching_line(dut):
    logger = case_logger("test_lyc_irq_fires_on_matching_line")
    await reset_dut(dut)

    logger.step("Enable only LYC select and target line 2")
    await step(dut, write_target=LYC_TARGET, write_value=0x02)
    await step(dut, write_target=STAT_TARGET, write_value=STAT_SEL_LYC)

    logger.step("Advance until LY reaches 2 and verify the rising-edge STAT IRQ pulse")
    ly2 = await advance_until(dut, lambda snap: snap["ly"] == 2 and snap["phase"] == PHASE_OAM)
    require(logger, "ly2_stat_irq", True, ly2["stat_irq"], snapshot=ly2)
    require(logger, "ly2_stat_line", True, ly2["stat_line"], snapshot=ly2)
    require(logger, "ly2_stat_readback", 0xC6, ly2["stat_readback"], snapshot=ly2)

    logger.step("Verify the line stays high without retriggering on the next dot")
    ly2_hold = await step(dut)
    require(logger, "ly2_hold_irq", False, ly2_hold["stat_irq"], snapshot=ly2_hold)
    require(logger, "ly2_hold_line", True, ly2_hold["stat_line"], snapshot=ly2_hold)


@cocotb.test()
async def test_mode0_irq_fires_once_per_hblank_edge(dut):
    logger = case_logger("test_mode0_irq_fires_once_per_hblank_edge")
    await reset_dut(dut)

    logger.step("Enable mode 0 STAT source and advance to HBlank entry")
    await step(dut, write_target=STAT_TARGET, write_value=STAT_SEL_MODE0)
    hblank_entry = await advance_until(dut, lambda snap: snap["phase"] == PHASE_HBLANK)
    require(logger, "hblank_entry_dot", 252, hblank_entry["dot"], snapshot=hblank_entry)
    require(logger, "hblank_irq_edge", True, hblank_entry["stat_irq"], snapshot=hblank_entry)
    require(logger, "hblank_line_high", True, hblank_entry["stat_line"], snapshot=hblank_entry)

    logger.step("Step one more dot inside HBlank and verify the IRQ pulse is edge-only")
    hblank_hold = await step(dut)
    require(logger, "hblank_hold_irq", False, hblank_hold["stat_irq"], snapshot=hblank_hold)
    require(logger, "hblank_hold_line", True, hblank_hold["stat_line"], snapshot=hblank_hold)


@cocotb.test()
async def test_mode1_and_vblank_irqs_are_distinct_on_entry(dut):
    logger = case_logger("test_mode1_and_vblank_irqs_are_distinct_on_entry")
    await reset_dut(dut)

    logger.step("Enable mode 1 STAT source and advance to line 144 entry")
    await step(dut, write_target=STAT_TARGET, write_value=STAT_SEL_MODE1)
    vblank_entry = await advance_until(dut, lambda snap: snap["mode"] == MODE_VBLANK)
    require(logger, "vblank_entry_ly", 144, vblank_entry["ly"], snapshot=vblank_entry)
    require(logger, "vblank_irq", True, vblank_entry["vblank_irq"], snapshot=vblank_entry)
    require(logger, "stat_mode1_irq", True, vblank_entry["stat_irq"], snapshot=vblank_entry)
    require(logger, "stat_line", True, vblank_entry["stat_line"], snapshot=vblank_entry)

    logger.step("Verify both requests deassert after the edge while the STAT line stays high")
    vblank_hold = await step(dut)
    require(logger, "vblank_hold_vblank_irq", False, vblank_hold["vblank_irq"], snapshot=vblank_hold)
    require(logger, "vblank_hold_stat_irq", False, vblank_hold["stat_irq"], snapshot=vblank_hold)
    require(logger, "vblank_hold_line", True, vblank_hold["stat_line"], snapshot=vblank_hold)


@cocotb.test()
async def test_mode2_and_lyc_share_one_rising_edge(dut):
    logger = case_logger("test_mode2_and_lyc_share_one_rising_edge")
    await reset_dut(dut)

    logger.step("Enable mode 2 + LYC with LYC=0 so both sources are true on line 0")
    await step(dut, write_target=LYC_TARGET, write_value=0x00)
    start = await step(dut, write_target=STAT_TARGET, write_value=STAT_SEL_MODE2 | STAT_SEL_LYC)
    require(logger, "start_mode", MODE_OAM, start["mode"], snapshot=start)
    require(logger, "start_stat_irq", False, start["stat_irq"], snapshot=start)
    require(logger, "start_stat_line", True, start["stat_line"], snapshot=start)

    logger.step("Advance while the combined STAT line remains high and verify no second IRQ pulse appears")
    for _ in range(90):
        hold = await step(dut)
        require(logger, "combined_line_high", True, hold["stat_line"], snapshot=hold)
        require(logger, "combined_irq_retrigger", False, hold["stat_irq"], snapshot=hold)


@cocotb.test()
async def test_mode0_to_mode2_boundary_blocks_second_pulse(dut):
    logger = case_logger("test_mode0_to_mode2_boundary_blocks_second_pulse")
    await reset_dut(dut)

    logger.step("Enable mode 0 and mode 2 sources together")
    await step(dut, write_target=STAT_TARGET, write_value=STAT_SEL_MODE0 | STAT_SEL_MODE2)
    hblank_entry = await advance_until(dut, lambda snap: snap["phase"] == PHASE_HBLANK)
    require(logger, "hblank_irq", True, hblank_entry["stat_irq"], snapshot=hblank_entry)
    require(logger, "hblank_line", True, hblank_entry["stat_line"], snapshot=hblank_entry)

    logger.step("Advance to the next line's OAM entry and verify the line stayed high across the boundary")
    next_oam = await advance_until(dut, lambda snap: snap["ly"] == 1 and snap["phase"] == PHASE_OAM)
    require(logger, "next_oam_mode", MODE_OAM, next_oam["mode"], snapshot=next_oam)
    require(logger, "next_oam_line", True, next_oam["stat_line"], snapshot=next_oam)
    require(logger, "next_oam_irq_blocked", False, next_oam["stat_irq"], snapshot=next_oam)


@cocotb.test()
async def test_stat_mode_bits_report_zero_when_lcd_off(dut):
    logger = case_logger("test_stat_mode_bits_report_zero_when_lcd_off")
    await reset_dut(dut)

    logger.step("Disable LCD and verify STAT mode bits read back as zero")
    disabled = await step(dut, write_target=LCDC_TARGET, write_value=LCDC_OFF)
    require(logger, "lcd_off_mode", MODE_LCD_OFF, disabled["mode"], snapshot=disabled)
    require(logger, "lcd_off_phase", PHASE_LCD_OFF, disabled["phase"], snapshot=disabled)
    require(logger, "stat_mode_bits_lcd_off", 0x80, disabled["stat_readback"] & 0x83, snapshot=disabled)
