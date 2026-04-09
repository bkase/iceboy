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


SUITE_LABEL = "test_ppu_power_quiescence.py"

MODE_LCD_OFF = 0
MODE_OAM = 1
MODE_TRANSFER = 2
MODE_HBLANK = 3

MMIO_LCDC = 0


def decode_output(value: int) -> dict[str, int]:
    return {
        "mode": value & 0x7,
        "ly": (value >> 3) & 0xFF,
        "dot_in_line": (value >> 11) & 0x1FF,
        "bg_fifo_count": (value >> 20) & 0x1F,
        "obj_fifo_count": (value >> 25) & 0x1F,
        "oam_scan_index": (value >> 30) & 0x3F,
        "oam_scan_found": (value >> 36) & 0xF,
        "window_state": (value >> 40) & 0x3,
        "window_line": (value >> 42) & 0xFF,
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


async def step_dot(dut, *, write_valid: bool = False, write_target: int = 0, write_value: int = 0) -> dict[str, int]:
    dut.dot_ce_i.value = 1
    dut.write_valid_i.value = int(write_valid)
    dut.write_target_i.value = write_target & 0xF
    dut.write_value_i.value = write_value & 0xFF
    await RisingEdge(dut.clk_i)
    dut.write_valid_i.value = 0
    return await observe(dut)


async def advance_to_mode(dut, mode: int, *, max_dots: int = 1024) -> dict[str, int]:
    for _ in range(max_dots):
        snapshot = await step_dot(dut)
        if snapshot["mode"] == mode:
            return snapshot
    raise TimeoutError(f"Mode {mode} not reached within {max_dots} dots")


@cocotb.test()
async def test_lcd_off_quiescence_zeroes_render_activity(dut):
    await reset(dut)

    disabled = await step_dot(dut, write_valid=True, write_target=MMIO_LCDC, write_value=0x00)
    assert disabled["mode"] == MODE_LCD_OFF

    metrics_start = await read_ppu_power_metrics(dut)
    last = disabled
    for _ in range(32):
        last = await step_dot(dut)
    metrics = (await read_ppu_power_metrics(dut)).subtract(metrics_start)
    append_metrics_artifact(SUITE_LABEL, "test_lcd_off_quiescence_zeroes_render_activity", metrics)

    assert last["mode"] == MODE_LCD_OFF
    assert last["bg_fifo_count"] == 0
    assert last["obj_fifo_count"] == 0
    assert last["mem_req_count"] == 0
    assert last["pixel_emit"] == 0
    assert metrics.total_dots == 32
    assert metrics.mem_req_cycles == 0
    assert metrics.pixel_emit_cycles == 0
    assert metrics.ly_mode_mutation_cycles == 0
    assert metrics.window_mutation_cycles == 0
    assert metrics.oam_scan_mutation_cycles == 0
    assert metrics.line_objs_mutation_cycles == 0
    assert metrics.fetcher_mutation_cycles == 0
    assert metrics.bg_fifo_mutation_cycles == 0
    assert metrics.obj_fifo_mutation_cycles == 0
    assert metrics.bg_fifo_nonempty_cycles == 0
    assert metrics.obj_fifo_nonempty_cycles == 0


@cocotb.test()
async def test_oam_scan_keeps_fetcher_and_fifos_quiet(dut):
    await reset(dut)

    metrics_start = await read_ppu_power_metrics(dut)
    last = await advance_to_mode(dut, MODE_OAM, max_dots=8)
    for _ in range(31):
        last = await step_dot(dut)
        assert last["mode"] == MODE_OAM
    metrics = (await read_ppu_power_metrics(dut)).subtract(metrics_start)
    append_metrics_artifact(SUITE_LABEL, "test_oam_scan_keeps_fetcher_and_fifos_quiet", metrics)

    assert last["oam_scan_index"] > 0
    assert last["bg_fifo_count"] == 0
    assert last["obj_fifo_count"] == 0
    assert last["pixel_emit"] == 0
    assert metrics.total_dots == 32
    assert metrics.mem_req_cycles > 0
    assert metrics.pixel_emit_cycles == 0
    assert metrics.ly_mode_mutation_cycles == 0
    assert metrics.window_mutation_cycles == 0
    assert metrics.oam_scan_mutation_cycles > 0
    assert metrics.fetcher_mutation_cycles == 0
    assert metrics.bg_fifo_mutation_cycles == 0
    assert metrics.obj_fifo_mutation_cycles == 0
    assert metrics.bg_fifo_nonempty_cycles == 0
    assert metrics.obj_fifo_nonempty_cycles == 0


@cocotb.test()
async def test_hblank_keeps_render_pipe_quiet(dut):
    await reset(dut)

    hblank = await advance_to_mode(dut, MODE_HBLANK, max_dots=1024)
    assert hblank["mode"] == MODE_HBLANK
    metrics_start = await read_ppu_power_metrics(dut)
    last = hblank
    for _ in range(24):
        last = await step_dot(dut)
        assert last["mode"] == MODE_HBLANK
    metrics = (await read_ppu_power_metrics(dut)).subtract(metrics_start)
    append_metrics_artifact(SUITE_LABEL, "test_hblank_keeps_render_pipe_quiet", metrics)

    assert last["bg_fifo_count"] == 0
    assert last["obj_fifo_count"] == 0
    assert last["mem_req_count"] == 0
    assert last["pixel_emit"] == 0
    assert metrics.total_dots == 24
    assert metrics.mem_req_cycles == 0
    assert metrics.pixel_emit_cycles == 0
    assert metrics.window_mutation_cycles == 0
    assert metrics.oam_scan_mutation_cycles == 0
    assert metrics.line_objs_mutation_cycles == 0
    assert metrics.fetcher_mutation_cycles == 0
    assert metrics.bg_fifo_mutation_cycles == 0
    assert metrics.obj_fifo_mutation_cycles == 0
    assert metrics.bg_fifo_nonempty_cycles == 0
    assert metrics.obj_fifo_nonempty_cycles == 0
