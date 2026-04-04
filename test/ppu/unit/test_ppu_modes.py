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
LCDC_OFF = 0x11
LCDC_ON = 0x91

DOTS_PER_LINE = 456
LINES_PER_FRAME = 154
FRAME_DOTS = DOTS_PER_LINE * LINES_PER_FRAME
VISIBLE_DOTS_BEFORE_VBLANK = (144 * DOTS_PER_LINE) - 1
FRAME_DOTS_FROM_INITIAL_STATE = FRAME_DOTS - 1

SUITE_NAME = "test_ppu_modes.py"


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


async def advance_until(dut, predicate, *, max_dots: int = FRAME_DOTS * 2) -> tuple[int, dict[str, int | bool]]:
    for cycle in range(1, max_dots + 1):
        snapshot = await step(dut)
        if predicate(snapshot):
            return cycle, snapshot
    raise TimeoutError(f"predicate not met within {max_dots} dots")


@cocotb.test()
async def test_mode_sequence_visible_line(dut):
    logger = case_logger("test_mode_sequence_visible_line")
    await reset_dut(dut)

    logger.step("Read initial projected state at line 0")
    start = await step(dut, dot_ce=False)
    require(logger, "run@start", RUN_RUNNING, start["run"], snapshot=start)
    require(logger, "mode@start", MODE_OAM, start["mode"], snapshot=start)
    require(logger, "phase@start", PHASE_OAM, start["phase"], snapshot=start)
    require(logger, "ly@start", 0, start["ly"], snapshot=start)
    require(logger, "dot@start", 0, start["dot"], snapshot=start)

    logger.step("Advance until mode 3 entry on the first visible line")
    _, transfer = await advance_until(dut, lambda snap: snap["phase"] == PHASE_TRANSFER)
    require(logger, "transfer_entry_dot", 80, transfer["dot"], snapshot=transfer)
    require(logger, "transfer_entry_mode", MODE_TRANSFER, transfer["mode"], snapshot=transfer)

    logger.step("Advance until HBlank entry on the same line")
    _, hblank = await advance_until(dut, lambda snap: snap["phase"] == PHASE_HBLANK)
    require(logger, "hblank_entry_dot", 252, hblank["dot"], snapshot=hblank)
    require(logger, "hblank_entry_mode", MODE_HBLANK, hblank["mode"], snapshot=hblank)
    require(logger, "hblank_entry_ly", 0, hblank["ly"], snapshot=hblank)

    logger.step("Advance until the next visible line restarts in mode 2")
    _, next_line = await advance_until(dut, lambda snap: snap["ly"] == 1 and snap["phase"] == PHASE_OAM)
    require(logger, "next_line_dot", 0, next_line["dot"], snapshot=next_line)
    require(logger, "next_line_mode", MODE_OAM, next_line["mode"], snapshot=next_line)


@cocotb.test()
async def test_vblank_entry_exit_and_frame_exactness(dut):
    logger = case_logger("test_vblank_entry_exit_and_frame_exactness")
    await reset_dut(dut)

    logger.step("Advance from reset until mode 1 first appears")
    steps_to_vblank, vblank_entry = await advance_until(dut, lambda snap: snap["mode"] == MODE_VBLANK)
    require(logger, "vblank_entry_ly", 144, vblank_entry["ly"], snapshot=vblank_entry)
    require(logger, "vblank_entry_phase", PHASE_VBLANK, vblank_entry["phase"], snapshot=vblank_entry)
    require(logger, "steps_to_vblank", VISIBLE_DOTS_BEFORE_VBLANK, steps_to_vblank, snapshot=vblank_entry)

    logger.step("Continue through vblank until frame wrap returns to line 0")
    seen_vblank_lines = {int(vblank_entry["ly"])}
    total_dots = steps_to_vblank
    while True:
        snapshot = await step(dut)
        total_dots += 1
        if snapshot["mode"] == MODE_VBLANK:
            seen_vblank_lines.add(int(snapshot["ly"]))
        if snapshot["ly"] == 0 and snapshot["phase"] == PHASE_OAM and total_dots > steps_to_vblank:
            wrap = snapshot
            break

    require(logger, "frame_dots", FRAME_DOTS_FROM_INITIAL_STATE, total_dots, snapshot=wrap)
    require(logger, "wrap_mode", MODE_OAM, wrap["mode"], snapshot=wrap)
    require(logger, "wrap_run", RUN_RUNNING, wrap["run"], snapshot=wrap)
    require(logger, "wrap_first_frame_blank", False, wrap["first_frame_blank"], snapshot=wrap)
    assert logger.check("vblank_lines", expected=tuple(range(144, 154)), actual=tuple(sorted(seen_vblank_lines))), (
        f"vblank lines mismatch: expected={tuple(range(144, 154))} actual={tuple(sorted(seen_vblank_lines))}"
    )


@cocotb.test()
async def test_lcd_disable_mid_transfer_and_reenable_warmup(dut):
    logger = case_logger("test_lcd_disable_mid_transfer_and_reenable_warmup")
    await reset_dut(dut)

    logger.step("Advance into pixel transfer before disabling LCD")
    _, transfer = await advance_until(dut, lambda snap: snap["phase"] == PHASE_TRANSFER)
    require(logger, "transfer_mode_before_disable", MODE_TRANSFER, transfer["mode"], snapshot=transfer)

    logger.step("Disable LCDC.7 during mode 3 and verify immediate reset to LCD off")
    disabled = await step(dut, dot_ce=True, write_target=LCDC_TARGET, write_value=LCDC_OFF)
    require(logger, "disabled_mode", MODE_LCD_OFF, disabled["mode"], snapshot=disabled)
    require(logger, "disabled_phase", PHASE_LCD_OFF, disabled["phase"], snapshot=disabled)
    require(logger, "disabled_run", RUN_DISABLED, disabled["run"], snapshot=disabled)
    require(logger, "disabled_ly", 0, disabled["ly"], snapshot=disabled)
    require(logger, "disabled_dot", 0, disabled["dot"], snapshot=disabled)

    logger.step("Verify the disabled state remains quiescent")
    for _ in range(8):
        held = await step(dut)
        require(logger, "held_mode", MODE_LCD_OFF, held["mode"], snapshot=held)
        require(logger, "held_run", RUN_DISABLED, held["run"], snapshot=held)
        require(logger, "held_ly", 0, held["ly"], snapshot=held)
        require(logger, "held_dot", 0, held["dot"], snapshot=held)

    logger.step("Re-enable LCDC.7 and verify warmup blank frame starts immediately")
    warmup = await step(dut, dot_ce=True, write_target=LCDC_TARGET, write_value=LCDC_ON)
    require(logger, "warmup_mode", MODE_OAM, warmup["mode"], snapshot=warmup)
    require(logger, "warmup_phase", PHASE_OAM, warmup["phase"], snapshot=warmup)
    require(logger, "warmup_run", RUN_WARMUP, warmup["run"], snapshot=warmup)
    require(logger, "warmup_ly", 0, warmup["ly"], snapshot=warmup)
    require(logger, "warmup_first_frame_blank", True, warmup["first_frame_blank"], snapshot=warmup)

    logger.step("Advance until warmup promotes back to Running at the next frame boundary")
    dots_until_running, running = await advance_until(dut, lambda snap: snap["run"] == RUN_RUNNING, max_dots=FRAME_DOTS + 8)
    require(logger, "warmup_duration_dots", FRAME_DOTS_FROM_INITIAL_STATE, dots_until_running, snapshot=running)
    require(logger, "running_mode", MODE_OAM, running["mode"], snapshot=running)
    require(logger, "running_ly", 0, running["ly"], snapshot=running)
    require(logger, "running_dot", 0, running["dot"], snapshot=running)
    require(logger, "running_first_frame_blank", False, running["first_frame_blank"], snapshot=running)


@cocotb.test()
async def test_mode_projection_matches_run_state(dut):
    logger = case_logger("test_mode_projection_matches_run_state")
    await reset_dut(dut)

    logger.step("Observe baseline running state")
    running = await step(dut, dot_ce=False)
    require(logger, "baseline_run", RUN_RUNNING, running["run"], snapshot=running)
    require(logger, "baseline_mode", MODE_OAM, running["mode"], snapshot=running)

    logger.step("Force disabled state and verify mode collapses to LCD off")
    disabled = await step(dut, write_target=LCDC_TARGET, write_value=LCDC_OFF)
    require(logger, "disabled_run_projection", RUN_DISABLED, disabled["run"], snapshot=disabled)
    require(logger, "disabled_mode_projection", MODE_LCD_OFF, disabled["mode"], snapshot=disabled)

    logger.step("Re-enable and verify warmup still projects visible mode from the phase")
    warmup = await step(dut, write_target=LCDC_TARGET, write_value=LCDC_ON)
    require(logger, "warmup_run_projection", RUN_WARMUP, warmup["run"], snapshot=warmup)
    require(logger, "warmup_mode_projection", MODE_OAM, warmup["mode"], snapshot=warmup)
