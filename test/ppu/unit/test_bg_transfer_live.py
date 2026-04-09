# top = sim::ppu_power_top::ppu_power_top
from __future__ import annotations

import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from power_metrics import append_metrics_artifact, read_ppu_power_metrics


SUITE_LABEL = "test_bg_transfer_live.py"

MODE_TRANSFER = 2


def decode_output(value: int) -> dict[str, int]:
    return {
        "mode": value & 0x7,
        "ly": (value >> 3) & 0xFF,
        "dot_in_line": (value >> 11) & 0x1FF,
        "bg_fifo_count": (value >> 20) & 0x1F,
        "mem_req_count": (value >> 50) & 0x7,
        "pixel_emit": (value >> 53) & 0x1,
    }


async def observe(dut) -> dict[str, int]:
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


async def reset(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.dot_ce_i.value = 0
    dut.write_valid_i.value = 0
    dut.write_target_i.value = 0
    dut.write_value_i.value = 0
    dut.rst_i.value = 1
    await RisingEdge(dut.clk_i)
    await RisingEdge(dut.clk_i)
    dut.rst_i.value = 0
    await RisingEdge(dut.clk_i)
    dut.dot_ce_i.value = 1


async def step_dot(dut) -> dict[str, int]:
    dut.dot_ce_i.value = 1
    dut.write_valid_i.value = 0
    await RisingEdge(dut.clk_i)
    return await observe(dut)


async def advance_to_mode(dut, mode: int, *, max_dots: int = 1024) -> dict[str, int]:
    for _ in range(max_dots):
        snapshot = await step_dot(dut)
        if snapshot["mode"] == mode:
            return snapshot
    raise TimeoutError(f"Mode {mode} not reached within {max_dots} dots")


@cocotb.test()
async def test_transfer_drives_live_fetch_fifo_and_pixels(dut):
    await reset(dut)

    transfer = await advance_to_mode(dut, MODE_TRANSFER, max_dots=256)
    assert transfer["ly"] == 0

    metrics_start = await read_ppu_power_metrics(dut)
    saw_mem_req = transfer["mem_req_count"] > 0
    saw_bg_fifo = transfer["bg_fifo_count"] > 0
    saw_pixel_emit = transfer["pixel_emit"] == 1

    last = transfer
    for _ in range(63):
        last = await step_dot(dut)
        assert last["mode"] == MODE_TRANSFER, last
        saw_mem_req = saw_mem_req or last["mem_req_count"] > 0
        saw_bg_fifo = saw_bg_fifo or last["bg_fifo_count"] > 0
        saw_pixel_emit = saw_pixel_emit or last["pixel_emit"] == 1

    metrics = (await read_ppu_power_metrics(dut)).subtract(metrics_start)
    append_metrics_artifact(SUITE_LABEL, "test_transfer_drives_live_fetch_fifo_and_pixels", metrics)

    assert saw_mem_req, last
    assert saw_bg_fifo, last
    assert saw_pixel_emit, last
    assert metrics.total_dots == 63
    assert metrics.mem_req_cycles > 0
    assert metrics.pixel_emit_cycles > 0
    assert metrics.fetcher_mutation_cycles > 0
    assert metrics.bg_fifo_mutation_cycles > 0
    assert metrics.bg_fifo_nonempty_cycles > 0
