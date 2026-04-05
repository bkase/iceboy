# top = bus::ppu_event_bridge_test_top::ppu_event_bridge_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


REQ_IDLE = 0
REQ_READ = 1
REQ_WRITE = 2

KIND_IDLE = 0
KIND_MMIO = 1
KIND_DMA = 2
KIND_POWER = 3

TARGET_LCDC = 0
TARGET_SCY = 2
TARGET_OBP1 = 9


def decode_event(value: int) -> dict[str, int]:
    return {
        "seq": (value >> 14) & 0xFF,
        "kind": (value >> 12) & 0x3,
        "target": (value >> 8) & 0xF,
        "payload": value & 0xFF,
    }


def decode_output(value: int) -> dict[str, object]:
    return {
        "count": value & 0xF,
        "frame": (value >> 4) & 0xFF,
        "line": (value >> 12) & 0xFF,
        "dot": (value >> 20) & 0x1FF,
        "event0": decode_event((value >> 29) & 0xFFFFFF),
        "event1": decode_event((value >> 53) & 0xFFFFFF),
    }


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.m_ce_i.value = 0
    dut.req_kind_i.value = REQ_IDLE
    dut.addr_i.value = 0
    dut.data_i.value = 0
    dut.frame_start_i.value = 1
    dut.line_index_i.value = 0
    dut.dot_in_line_i.value = 0
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step(
    dut,
    *,
    req_kind: int = REQ_IDLE,
    addr: int = 0,
    data: int = 0,
    frame_start: bool = False,
    line_index: int = 0,
    dot_in_line: int = 0,
    m_ce: bool = True,
) -> dict[str, object]:
    dut.m_ce_i.value = int(m_ce)
    dut.req_kind_i.value = req_kind
    dut.addr_i.value = addr & 0xFFFF
    dut.data_i.value = data & 0xFF
    dut.frame_start_i.value = int(frame_start)
    dut.line_index_i.value = line_index & 0xFF
    dut.dot_in_line_i.value = dot_in_line & 0x1FF
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_mmio_write_becomes_timed_event_with_video_coord(dut):
    await reset_dut(dut)
    await step(dut, frame_start=False, line_index=0, dot_in_line=1, m_ce=False)

    snapshot = await step(
        dut,
        req_kind=REQ_WRITE,
        addr=0xFF42,
        data=0x99,
        frame_start=False,
        line_index=7,
        dot_in_line=42,
    )
    assert snapshot["count"] == 1
    assert snapshot["frame"] == 0
    assert snapshot["line"] == 7
    assert snapshot["dot"] == 42
    assert snapshot["event0"]["kind"] == KIND_MMIO
    assert snapshot["event0"]["target"] == TARGET_SCY
    assert snapshot["event0"]["payload"] == 0x99
    assert snapshot["event0"]["seq"] == 0


@cocotb.test()
async def test_dma_start_write_emits_dma_event(dut):
    await reset_dut(dut)
    await step(dut, frame_start=False, line_index=0, dot_in_line=1, m_ce=False)

    snapshot = await step(
        dut,
        req_kind=REQ_WRITE,
        addr=0xFF46,
        data=0xC1,
        frame_start=False,
        line_index=3,
        dot_in_line=12,
    )
    assert snapshot["count"] == 1
    assert snapshot["event0"]["kind"] == KIND_DMA
    assert snapshot["event0"]["payload"] == 0xC1
    assert snapshot["event0"]["seq"] == 0


@cocotb.test()
async def test_lcdc_transition_emits_mmio_then_force_power_event(dut):
    await reset_dut(dut)
    await step(dut, frame_start=False, line_index=0, dot_in_line=1, m_ce=False)

    disable = await step(
        dut,
        req_kind=REQ_WRITE,
        addr=0xFF40,
        data=0x11,
        frame_start=False,
        line_index=0,
        dot_in_line=5,
    )
    assert disable["count"] == 2
    assert disable["event0"]["kind"] == KIND_MMIO
    assert disable["event0"]["target"] == TARGET_LCDC
    assert disable["event0"]["payload"] == 0x11
    assert disable["event0"]["seq"] == 0
    assert disable["event1"]["kind"] == KIND_POWER
    assert disable["event1"]["payload"] == 0
    assert disable["event1"]["seq"] == 1

    enable = await step(
        dut,
        req_kind=REQ_WRITE,
        addr=0xFF40,
        data=0x91,
        frame_start=False,
        line_index=0,
        dot_in_line=6,
    )
    assert enable["count"] == 2
    assert enable["event0"]["kind"] == KIND_MMIO
    assert enable["event0"]["target"] == TARGET_LCDC
    assert enable["event0"]["payload"] == 0x91
    assert enable["event0"]["seq"] == 2
    assert enable["event1"]["kind"] == KIND_POWER
    assert enable["event1"]["payload"] == 1
    assert enable["event1"]["seq"] == 3

    steady = await step(
        dut,
        req_kind=REQ_WRITE,
        addr=0xFF40,
        data=0x81,
        frame_start=False,
        line_index=0,
        dot_in_line=7,
    )
    assert steady["count"] == 1
    assert steady["event0"]["kind"] == KIND_MMIO
    assert steady["event0"]["seq"] == 4
    assert steady["event1"]["kind"] == KIND_IDLE


@cocotb.test()
async def test_seq_is_monotonic_for_same_dot_events_across_cycles(dut):
    await reset_dut(dut)
    await step(dut, frame_start=False, line_index=0, dot_in_line=1, m_ce=False)

    first = await step(
        dut,
        req_kind=REQ_WRITE,
        addr=0xFF47,
        data=0xE4,
        frame_start=False,
        line_index=9,
        dot_in_line=88,
    )
    second = await step(
        dut,
        req_kind=REQ_WRITE,
        addr=0xFF48,
        data=0xD2,
        frame_start=False,
        line_index=9,
        dot_in_line=88,
    )
    assert first["count"] == 1
    assert second["count"] == 1
    assert first["frame"] == second["frame"] == 0
    assert first["line"] == second["line"] == 9
    assert first["dot"] == second["dot"] == 88
    assert first["event0"]["seq"] == 0
    assert second["event0"]["seq"] == 1


@cocotb.test()
async def test_frame_counter_advances_on_later_frame_start_and_non_ppu_writes_are_ignored(dut):
    await reset_dut(dut)
    await step(dut, frame_start=False, line_index=0, dot_in_line=1, m_ce=False)

    ignored = await step(
        dut,
        req_kind=REQ_WRITE,
        addr=0xFF10,
        data=0x77,
        frame_start=False,
        line_index=1,
        dot_in_line=2,
    )
    assert ignored["count"] == 0
    assert ignored["event0"]["kind"] == KIND_IDLE

    await step(dut, req_kind=REQ_IDLE, frame_start=False, line_index=153, dot_in_line=455)
    wrapped = await step(
        dut,
        req_kind=REQ_WRITE,
        addr=0xFF49,
        data=0x33,
        frame_start=True,
        line_index=0,
        dot_in_line=0,
    )
    assert wrapped["count"] == 1
    assert wrapped["frame"] == 1
    assert wrapped["line"] == 0
    assert wrapped["dot"] == 0
    assert wrapped["event0"]["kind"] == KIND_MMIO
    assert wrapped["event0"]["target"] == TARGET_OBP1
