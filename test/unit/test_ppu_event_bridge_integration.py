# top = bus::ppu_bridge_core_test_top::ppu_bridge_core_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


REQ_IDLE = 0
REQ_WRITE = 2

PHASE_LCD_OFF = 0
MODE_LCD_OFF = 0

RUN_DISABLED = 0
RUN_WARMUP = 1

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
        "bus_event_count": (value >> 37) & 0xF,
        "m_ce": bool((value >> 41) & 0x1),
        "dot_ce": bool((value >> 42) & 0x1),
        "frame_start": bool((value >> 43) & 0x1),
        "req_kind": (value >> 44) & 0x3,
    }


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.dot_ce_i.value = 0
    dut.m_ce_i.value = 0
    dut.req_kind_i.value = REQ_IDLE
    dut.addr_i.value = 0
    dut.data_i.value = 0
    dut.frame_start_i.value = 0
    dut.line_index_i.value = 0
    dut.dot_in_line_i.value = 0
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step(
    dut,
    dot_index: int,
    *,
    req_kind: int = REQ_IDLE,
    addr: int = 0,
    data: int = 0,
    dot_ce: bool = True,
) -> dict[str, int | bool]:
    dut.dot_ce_i.value = int(dot_ce)
    dut.m_ce_i.value = int((dot_index & 0x3) == 0x3)
    dut.req_kind_i.value = req_kind
    dut.addr_i.value = addr & 0xFFFF
    dut.data_i.value = data & 0xFF
    dut.frame_start_i.value = int(dot_index == 0)
    dut.line_index_i.value = (dot_index // 456) & 0xFF
    dut.dot_in_line_i.value = dot_index % 456
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


async def advance_until(dut, start_dot: int, predicate, *, max_dots: int = 456 * 2) -> tuple[int, dict[str, int | bool]]:
    dot_index = start_dot
    for _ in range(max_dots):
        snapshot = await step(dut, dot_index)
        if predicate(snapshot):
            return dot_index, snapshot
        dot_index += 1
    raise TimeoutError(f"predicate not met within {max_dots} dots")


async def write_on_next_mcycle(dut, start_dot: int, *, addr: int, data: int) -> tuple[int, dict[str, int | bool]]:
    dot_index = start_dot
    while (dot_index & 0x3) != 0x3:
        await step(dut, dot_index)
        dot_index += 1
    snapshot = await step(dut, dot_index, req_kind=REQ_WRITE, addr=addr, data=data)
    return dot_index, snapshot


async def capture_enable_timeline(dut) -> list[dict[str, int | bool]]:
    await reset_dut(dut)
    dot_index, _ = await advance_until(dut, 0, lambda snap: snap["run"] != RUN_DISABLED and snap["mode"] != MODE_LCD_OFF)
    dot_index += 1
    dot_index, disabled = await write_on_next_mcycle(dut, dot_index, addr=0xFF40, data=LCDC_OFF)
    assert disabled["run"] == RUN_DISABLED, disabled
    assert disabled["phase"] == PHASE_LCD_OFF, disabled
    dot_index += 1
    dot_index, enabled = await write_on_next_mcycle(dut, dot_index, addr=0xFF40, data=LCDC_ON)
    assert enabled["run"] == RUN_WARMUP, enabled
    timeline = [enabled]
    dot_index += 1
    for _ in range(DOT_CHECKPOINTS[-1] + 8):
        timeline.append(await step(dut, dot_index))
        dot_index += 1
    return timeline


def sample_row(timeline: list[dict[str, int | bool]], row_index: int, field: str) -> tuple[int, ...]:
    offset = row_index * 4
    return tuple(int(timeline[dot + offset][field]) for dot in DOT_CHECKPOINTS)


@cocotb.test()
async def test_bridge_path_matches_mooneye_lcdon_ly_timing(dut):
    timeline = await capture_enable_timeline(dut)
    for row_index, expected in enumerate(EXPECT_LY_ROWS):
        actual = sample_row(timeline, row_index, "ly")
        assert actual == expected, (
            f"LY mismatch for offset row {row_index} at {CHECKPOINTS}: expected={expected} actual={actual}"
        )


@cocotb.test()
async def test_bridge_path_matches_mooneye_lcdon_stat_timing(dut):
    timeline = await capture_enable_timeline(dut)
    for row_index, expected in enumerate(EXPECT_STAT_LYC0_ROWS):
        actual = sample_row(timeline, row_index, "stat_readback")
        assert actual == expected, (
            f"STAT mismatch for offset row {row_index} at {CHECKPOINTS}: expected={expected} actual={actual}"
        )
