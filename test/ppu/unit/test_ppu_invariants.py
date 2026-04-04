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

RUN_DISABLED = 0
RUN_WARMUP = 1
RUN_RUNNING = 2

LCDC_TARGET = 0
STAT_TARGET = 1
LYC_TARGET = 4

LCDC_OFF = 0x11
STAT_SEL_LYC = 0x40

DOTS_PER_LINE = 456
LINES_PER_FRAME = 154
FRAME_DOTS = DOTS_PER_LINE * LINES_PER_FRAME

SUITE_NAME = "test_ppu_invariants.py"


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
        "mem_req_count": (value >> 37) & 0x7,
        "scanout_valid": bool((value >> 40) & 0x1),
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


async def advance_until(dut, predicate, *, max_dots: int = FRAME_DOTS * 2) -> dict[str, int | bool]:
    for _ in range(max_dots):
        snapshot = await step(dut)
        if predicate(snapshot):
            return snapshot
    raise TimeoutError(f"predicate not met within {max_dots} dots")


@cocotb.test()
async def test_dot_ce_zero_holds_architectural_state_and_traffic(dut):
    logger = case_logger("test_dot_ce_zero_holds_architectural_state_and_traffic")
    await reset_dut(dut)

    logger.step("Advance once, then capture the first held sample as the architectural baseline")
    await step(dut)
    baseline = await step(dut, dot_ce=False)
    require(logger, "baseline_mem_req_count", 0, baseline["mem_req_count"], snapshot=baseline)
    require(logger, "baseline_scanout_valid", False, baseline["scanout_valid"], snapshot=baseline)

    logger.step("Hold dot_ce low for 100 more clocks and verify all exposed architectural state is unchanged")
    for index in range(100):
        held = await step(dut, dot_ce=False)
        for field in [
            "phase",
            "ly",
            "dot",
            "mode",
            "stat_line",
            "vblank_irq",
            "stat_irq",
            "run",
            "first_frame_blank",
            "stat_readback",
            "mem_req_count",
            "scanout_valid",
        ]:
            require(logger, f"{field}@hold{index}", baseline[field], held[field], snapshot=held)


@cocotb.test()
async def test_frame_timing_mode_sequence_and_vblank_window(dut):
    logger = case_logger("test_frame_timing_mode_sequence_and_vblank_window")
    await reset_dut(dut)

    logger.step("Run one full frame and verify completed visible-line mode sequences plus VBlank residency")
    visible_sequences: dict[int, list[int]] = {}
    visible_counts: dict[int, int] = {}
    vblank_lines: set[int] = set()
    frame_wrap_seen = False
    current_visible_ly: int | None = None
    current_visible_sequence: list[int] = []
    current_visible_count = 0

    for _ in range(FRAME_DOTS - 1):
        snapshot = await step(dut)
        ly = int(snapshot["ly"])
        dot = int(snapshot["dot"])
        mode = int(snapshot["mode"])
        phase = int(snapshot["phase"])

        assert snapshot["mem_req_count"] == 0, snapshot
        assert snapshot["scanout_valid"] is False, snapshot

        if ly < 144:
            if current_visible_ly is None:
                current_visible_ly = ly
            elif ly != current_visible_ly:
                visible_sequences[current_visible_ly] = current_visible_sequence
                visible_counts[current_visible_ly] = current_visible_count
                current_visible_ly = ly
                current_visible_sequence = []
                current_visible_count = 0

            if not current_visible_sequence or current_visible_sequence[-1] != mode:
                current_visible_sequence.append(mode)
            current_visible_count += 1
            assert phase != PHASE_VBLANK, f"visible line entered VBlank: {snapshot}"
            assert mode in (MODE_OAM, MODE_TRANSFER, MODE_HBLANK), f"bad visible mode: {snapshot}"
        else:
            if current_visible_ly is not None:
                visible_sequences[current_visible_ly] = current_visible_sequence
                visible_counts[current_visible_ly] = current_visible_count
                current_visible_ly = None
                current_visible_sequence = []
                current_visible_count = 0
            vblank_lines.add(ly)
            assert mode == MODE_VBLANK, snapshot
            assert phase == PHASE_VBLANK, snapshot

        if ly == 0 and dot == 0 and mode == MODE_OAM and int(snapshot["run"]) == RUN_RUNNING:
            frame_wrap_seen = True

    for ly in range(144):
        assert visible_sequences.get(ly) == [MODE_OAM, MODE_TRANSFER, MODE_HBLANK], (
            ly,
            visible_sequences.get(ly),
        )
        expected_count = DOTS_PER_LINE - 2 if ly == 0 else DOTS_PER_LINE
        require(logger, f"visible_dot_count@ly{ly}", expected_count, visible_counts.get(ly, 0), snapshot={"ly": ly})

    assert tuple(sorted(vblank_lines)) == tuple(range(144, 154)), tuple(sorted(vblank_lines))
    assert frame_wrap_seen, "frame wrap back to line 0 OAM was not observed"


@cocotb.test()
async def test_lyc_equality_updates_immediately_on_mid_scanline_write(dut):
    logger = case_logger("test_lyc_equality_updates_immediately_on_mid_scanline_write")
    await reset_dut(dut)

    logger.step("Enable LYC compare with a non-matching target and advance into visible transfer")
    await step(dut, write_target=LYC_TARGET, write_value=0x20)
    await step(dut, write_target=STAT_TARGET, write_value=STAT_SEL_LYC)
    transfer = await advance_until(dut, lambda snap: snap["ly"] == 0 and snap["phase"] == PHASE_TRANSFER)
    require(logger, "transfer_stat_line_before", False, transfer["stat_line"], snapshot=transfer)
    require(logger, "transfer_stat_bit_before", False, bool(int(transfer["stat_readback"]) & 0x04), snapshot=transfer)

    logger.step("Write LYC=0 mid-scanline and verify coincidence/readback update on the same committed dot")
    updated = await step(dut, write_target=LYC_TARGET, write_value=0x00)
    require(logger, "updated_stat_line", True, updated["stat_line"], snapshot=updated)
    require(logger, "updated_lyc_bit", True, bool(int(updated["stat_readback"]) & 0x04), snapshot=updated)
    require(logger, "updated_stat_irq", False, updated["stat_irq"], snapshot=updated)


@cocotb.test()
async def test_lcd_off_suppresses_all_traffic_and_holds_off_state(dut):
    logger = case_logger("test_lcd_off_suppresses_all_traffic_and_holds_off_state")
    await reset_dut(dut)

    logger.step("Disable LCD and verify the PPU collapses to LCD-off state")
    disabled = await step(dut, write_target=LCDC_TARGET, write_value=LCDC_OFF)
    require(logger, "disabled_mode", MODE_LCD_OFF, disabled["mode"], snapshot=disabled)
    require(logger, "disabled_phase", PHASE_LCD_OFF, disabled["phase"], snapshot=disabled)
    require(logger, "disabled_run", RUN_DISABLED, disabled["run"], snapshot=disabled)
    require(logger, "disabled_ly", 0, disabled["ly"], snapshot=disabled)
    require(logger, "disabled_dot", 0, disabled["dot"], snapshot=disabled)

    logger.step("Run 1000 dots with LCD disabled and verify zero traffic and stable state")
    for index in range(1000):
        snapshot = await step(dut)
        for field, expected in [
            ("mode", MODE_LCD_OFF),
            ("phase", PHASE_LCD_OFF),
            ("run", RUN_DISABLED),
            ("ly", 0),
            ("dot", 0),
            ("mem_req_count", 0),
            ("scanout_valid", False),
        ]:
            require(logger, f"{field}@lcd_off_{index}", expected, snapshot[field], snapshot=snapshot)
