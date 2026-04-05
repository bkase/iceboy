# top = ppu::rtl::core_test_top::core_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


PHASE_LCD_OFF = 0

MODE_LCD_OFF = 0

RUN_DISABLED = 0
RUN_WARMUP = 1

LCDC_TARGET = 0
LYC_TARGET = 4

LCDC_OFF = 0x11
LCDC_ON = 0x81

CHECKPOINTS = (0, 17, 60, 110, 130, 174, 224, 244)
DOT_CHECKPOINTS = tuple(checkpoint * 4 for checkpoint in CHECKPOINTS)
EXPECT_LY_ROWS = (
    (0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x02),
    (0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x02, 0x02),
    (0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x02, 0x02),
)
EXPECT_STAT_LYC0_ROWS = (
    (0x84, 0x84, 0x87, 0x84, 0x82, 0x83, 0x80, 0x82),
    (0x84, 0x87, 0x84, 0x80, 0x82, 0x80, 0x80, 0x82),
    (0x84, 0x87, 0x84, 0x82, 0x83, 0x80, 0x82, 0x83),
)
EXPECT_STAT_LYC1_ROWS = (
    (0x80, 0x80, 0x83, 0x80, 0x86, 0x87, 0x84, 0x82),
    (0x80, 0x83, 0x80, 0x80, 0x86, 0x84, 0x80, 0x82),
    (0x80, 0x83, 0x80, 0x86, 0x87, 0x84, 0x82, 0x83),
)


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


async def advance_until(dut, predicate, *, max_dots: int = 456 * 2) -> dict[str, int | bool]:
    for _ in range(max_dots):
        snapshot = await step(dut)
        if predicate(snapshot):
            return snapshot
    raise TimeoutError(f"predicate not met within {max_dots} dots")


async def capture_enable_timeline(dut, *, lyc_value: int) -> list[dict[str, int | bool]]:
    await reset_dut(dut)
    await step(dut, write_target=LYC_TARGET, write_value=lyc_value)
    await advance_until(dut, lambda snap: snap["run"] != RUN_DISABLED and snap["mode"] != MODE_LCD_OFF)
    disabled = await step(dut, write_target=LCDC_TARGET, write_value=LCDC_OFF)
    assert disabled["run"] == RUN_DISABLED, disabled
    assert disabled["phase"] == PHASE_LCD_OFF, disabled
    enabled = await step(dut, write_target=LCDC_TARGET, write_value=LCDC_ON)
    assert enabled["run"] == RUN_WARMUP, enabled
    timeline = [enabled]
    for _ in range(DOT_CHECKPOINTS[-1] + 8):
        timeline.append(await step(dut))
    return timeline


def sample_row(
    timeline: list[dict[str, int | bool]],
    row_index: int,
    field: str,
) -> tuple[int, ...]:
    offset = row_index * 4
    return tuple(int(timeline[dot + offset][field]) for dot in DOT_CHECKPOINTS)


@cocotb.test()
async def test_lcdon_timing_matches_mooneye_ly_expectations(dut):
    timeline = await capture_enable_timeline(dut, lyc_value=0x00)
    for row_index, expected in enumerate(EXPECT_LY_ROWS):
        actual = sample_row(timeline, row_index, "ly")
        assert actual == expected, (
            f"LY mismatch for offset row {row_index} at {CHECKPOINTS}: expected={expected} actual={actual}"
        )


@cocotb.test()
async def test_lcdon_timing_matches_mooneye_stat_lyc0_expectations(dut):
    timeline = await capture_enable_timeline(dut, lyc_value=0x00)
    for row_index, expected in enumerate(EXPECT_STAT_LYC0_ROWS):
        actual = sample_row(timeline, row_index, "stat_readback")
        assert actual == expected, (
            f"STAT LYC=0 mismatch for offset row {row_index} at {CHECKPOINTS}: "
            f"expected={expected} actual={actual}"
        )


@cocotb.test()
async def test_lcdon_timing_matches_mooneye_stat_lyc1_expectations(dut):
    timeline = await capture_enable_timeline(dut, lyc_value=0x01)
    for row_index, expected in enumerate(EXPECT_STAT_LYC1_ROWS):
        actual = sample_row(timeline, row_index, "stat_readback")
        assert actual == expected, (
            f"STAT LYC=1 mismatch for offset row {row_index} at {CHECKPOINTS}: "
            f"expected={expected} actual={actual}"
        )
