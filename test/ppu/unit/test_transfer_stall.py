# top = ppu::rtl::transfer_stall_test_top::transfer_stall_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


def decode_output(value: int) -> dict[str, int]:
    return {
        "x_out": value & 0xFF,
        "stall_dots": (value >> 8) & 0x1F,
        "added_stall_dots": (value >> 13) & 0x1F,
    }


async def reset_dut(dut, *, seed_stall_dots: int, start_x_out: int, extra_stall_dots: int = 0) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.dot_ce_i.value = 0
    dut.seed_stall_dots_i.value = seed_stall_dots & 0x1F
    dut.start_x_out_i.value = start_x_out & 0xFF
    dut.extra_stall_dots_i.value = extra_stall_dots & 0x1F
    dut.rst_i.value = 1
    await RisingEdge(dut.clk_i)
    await RisingEdge(dut.clk_i)
    dut.rst_i.value = 0
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    await Timer(1, units="ps")


async def step(dut) -> dict[str, int]:
    dut.dot_ce_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.dot_ce_i.value = 0
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_stall_dots_freeze_x_out_until_countdown_expires(dut):
    await reset_dut(dut, seed_stall_dots=3, start_x_out=12)

    first = await step(dut)
    second = await step(dut)
    third = await step(dut)
    fourth = await step(dut)

    assert first["x_out"] == 12
    assert second["x_out"] == 12
    assert third["x_out"] == 12
    assert first["stall_dots"] == 2
    assert second["stall_dots"] == 1
    assert third["stall_dots"] == 0
    assert fourth["x_out"] == 13


@cocotb.test()
async def test_add_stall_dots_sums_multiple_sources(dut):
    await reset_dut(dut, seed_stall_dots=3, start_x_out=0, extra_stall_dots=6)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    assert snapshot["added_stall_dots"] == 9
