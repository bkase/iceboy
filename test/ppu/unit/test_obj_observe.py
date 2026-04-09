# top = ppu::rtl::obj_observe_test_top::obj_observe_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


PHASE_LCD_OFF = 0
PHASE_OAM = 1
PHASE_TRANSFER = 2
PHASE_HBLANK = 3

MODE_LCD_OFF = 0
MODE_OAM = 1
MODE_TRANSFER = 2
MODE_HBLANK = 3

RUN_DISABLED = 0
RUN_WARMUP = 1
RUN_RUNNING = 2

FETCHER_BG = 0
FETCHER_GET_TILE = 0
MEM_REGION_VRAM = 0
MEM_CLIENT_CPU = 0

LCDC_TARGET = 0
LCDC_OFF = 0x11
LCDC_ON = 0x81


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "phase": value & 0x7,
        "ly": (value >> 3) & 0xFF,
        "dot": (value >> 11) & 0x1FF,
        "mode": (value >> 20) & 0x7,
        "run": (value >> 23) & 0x3,
        "mem_req_count": (value >> 25) & 0x7,
        "line_obj_count": (value >> 28) & 0xF,
        "oam_index": (value >> 32) & 0x3F,
        "oam_found": (value >> 38) & 0xF,
        "fetcher_epoch": (value >> 42) & 0xF,
        "fetcher_source": (value >> 46) & 0x3,
        "fetcher_step": (value >> 48) & 0x7,
        "fetcher_pending_push": bool((value >> 51) & 0x1),
        "fetcher_pending_valid": bool((value >> 52) & 0x1),
        "fetcher_pending_region": (value >> 53) & 0x1,
        "fetcher_pending_client": (value >> 54) & 0x7,
        "fetcher_pending_id": (value >> 57) & 0xF,
        "fetcher_pending_epoch": (value >> 61) & 0xF,
        "obj_fifo_count": (value >> 65) & 0x1F,
        "bg_fifo_count": (value >> 70) & 0x1F,
        "fetcher_map_x": (value >> 75) & 0x1F,
        "fetcher_map_y": (value >> 80) & 0x1F,
        "window_line": (value >> 85) & 0xFF,
        "first_frame_blank": bool((value >> 93) & 0x1),
        "slot0_oam_index": (value >> 94) & 0x3F,
        "slot0_rank": (value >> 100) & 0xF,
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


async def advance_until_phase(dut, phase: int, *, max_dots: int = 456 * 2) -> dict[str, int | bool]:
    for _ in range(max_dots):
        snapshot = await step(dut)
        if snapshot["phase"] == phase:
            return snapshot
    raise TimeoutError(f"phase {phase} not reached within {max_dots} dots")


@cocotb.test()
async def test_obj_observe_reset_baseline_is_decodable(dut):
    await reset_dut(dut)
    snapshot = decode_output(int(dut.output__.value))
    assert snapshot["phase"] == PHASE_OAM, snapshot
    assert snapshot["mode"] == MODE_OAM, snapshot
    assert snapshot["run"] == RUN_RUNNING, snapshot
    assert snapshot["mem_req_count"] == 0, snapshot
    assert snapshot["line_obj_count"] == 0, snapshot
    assert snapshot["oam_index"] == 0, snapshot
    assert snapshot["oam_found"] == 0, snapshot
    assert snapshot["fetcher_epoch"] == 0, snapshot
    assert snapshot["fetcher_source"] == FETCHER_BG, snapshot
    assert snapshot["fetcher_step"] == FETCHER_GET_TILE, snapshot
    assert snapshot["fetcher_pending_push"] is False, snapshot
    assert snapshot["fetcher_pending_valid"] is False, snapshot
    assert snapshot["fetcher_pending_region"] == MEM_REGION_VRAM, snapshot
    assert snapshot["fetcher_pending_client"] == MEM_CLIENT_CPU, snapshot
    assert snapshot["fetcher_pending_id"] == 0, snapshot
    assert snapshot["fetcher_pending_epoch"] == 0, snapshot
    assert snapshot["obj_fifo_count"] == 0, snapshot
    assert snapshot["slot0_oam_index"] == 0, snapshot
    assert snapshot["slot0_rank"] == 0, snapshot


@cocotb.test()
async def test_obj_observe_tracks_lcd_disable_and_reenable(dut):
    await reset_dut(dut)
    disabled = await step(dut, write_target=LCDC_TARGET, write_value=LCDC_OFF)
    assert disabled["phase"] == PHASE_LCD_OFF, disabled
    assert disabled["mode"] == MODE_LCD_OFF, disabled
    assert disabled["run"] == RUN_DISABLED, disabled
    assert disabled["line_obj_count"] == 0, disabled
    assert disabled["oam_index"] == 0, disabled
    assert disabled["fetcher_pending_valid"] is False, disabled

    enabled = await step(dut, write_target=LCDC_TARGET, write_value=LCDC_ON)
    assert enabled["run"] == RUN_WARMUP, enabled
    assert enabled["phase"] in {PHASE_LCD_OFF, PHASE_OAM}, enabled
    assert enabled["first_frame_blank"] is True, enabled
    assert enabled["line_obj_count"] == 0, enabled
    assert enabled["obj_fifo_count"] == 0, enabled


@cocotb.test()
async def test_obj_observe_surface_stays_well_formed_across_phase_progression(dut):
    await reset_dut(dut)
    transfer = await advance_until_phase(dut, PHASE_TRANSFER)
    assert transfer["mode"] == MODE_TRANSFER, transfer
    assert transfer["run"] == RUN_RUNNING, transfer
    assert 0 <= int(transfer["line_obj_count"]) <= 10, transfer
    assert 0 <= int(transfer["oam_index"]) <= 40, transfer
    assert 0 <= int(transfer["oam_found"]) <= 10, transfer
    assert 0 <= int(transfer["fetcher_epoch"]) <= 15, transfer
    assert 0 <= int(transfer["obj_fifo_count"]) <= 16, transfer
    assert 0 <= int(transfer["bg_fifo_count"]) <= 16, transfer
    assert 0 <= int(transfer["slot0_oam_index"]) <= 40, transfer

    hblank = await advance_until_phase(dut, PHASE_HBLANK)
    assert hblank["mode"] == MODE_HBLANK, hblank
    assert 0 <= int(hblank["fetcher_map_x"]) <= 31, hblank
    assert 0 <= int(hblank["fetcher_map_y"]) <= 31, hblank
    assert 0 <= int(hblank["window_line"]) <= 143, hblank


@cocotb.test()
async def test_obj_observe_live_oam_cadence_advances_index_every_two_dots(dut):
    await reset_dut(dut)

    first = await step(dut)
    second = await step(dut)
    third = await step(dut)
    fourth = await step(dut)

    assert first["phase"] == PHASE_OAM, first
    assert first["mem_req_count"] == 0, first
    assert first["oam_index"] == 1, first

    assert second["phase"] == PHASE_OAM, second
    assert second["mem_req_count"] == 2, second
    assert second["oam_index"] == 1, second

    assert third["phase"] == PHASE_OAM, third
    assert third["mem_req_count"] == 0, third
    assert third["oam_index"] == 2, third

    assert fourth["phase"] == PHASE_OAM, fourth
    assert fourth["mem_req_count"] == 2, fourth
    assert fourth["oam_index"] == 2, fourth
