# top = ppu::rtl::obj_transfer_live_test_top::obj_transfer_live_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


FETCHER_BG = 0
FETCHER_OBJ = 2
FETCHER_PUSH = 4

MEM_REGION_VRAM = 0
MEM_REGION_OAM = 1

MEM_CLIENT_OBJ_FETCHER = 2

PHASE_TRANSFER = 2
PHASE_HBLANK = 3
SCANOUT_PIXEL = 0
PIXEL_SOURCE_OBJECT = 2

def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "fetcher_source": value & 0x3,
        "fetcher_step": (value >> 2) & 0x7,
        "mem_req_count": (value >> 5) & 0x7,
        "obj_fifo_count": (value >> 8) & 0x1F,
        "req_addr": (value >> 13) & 0xFFFF,
        "req_region": (value >> 29) & 0x1,
        "req_client": (value >> 30) & 0x7,
        "req_id": (value >> 33) & 0xF,
        "resp_valid": bool((value >> 37) & 0x1),
        "line_obj_count": (value >> 38) & 0xF,
        "line_obj_fetch_index": (value >> 42) & 0xF,
        "x_out": (value >> 46) & 0xFF,
        "ly": (value >> 54) & 0xFF,
        "dot_in_line": (value >> 62) & 0x1FF,
        "phase": (value >> 71) & 0x7,
        "scanout_valid": bool((value >> 74) & 0x1),
        "scanout_kind": (value >> 75) & 0x3,
        "scanout_source": (value >> 77) & 0x3,
        "scanout_x": (value >> 79) & 0xFF,
        "scanout_shade": (value >> 87) & 0x3,
        "phase_x_out": (value >> 89) & 0xFF,
    }


async def reset_dut(
    dut,
    *,
    line_obj_count: int = 1,
    ticket0_x: int = 9,
    ticket1_x: int = 17,
    start_x_out: int = 1,
    start_dot_in_line: int = 80,
    tile_lo: int = 0x50,
    tile_hi: int = 0x30,
) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.dot_ce_i.value = 0
    dut.line_obj_count_i.value = line_obj_count & 0xF
    dut.ticket0_x_i.value = ticket0_x & 0xFF
    dut.ticket1_x_i.value = ticket1_x & 0xFF
    dut.start_x_out_i.value = start_x_out & 0xFF
    dut.start_dot_in_line_i.value = start_dot_in_line & 0x1FF
    dut.tile_lo_i.value = tile_lo & 0xFF
    dut.tile_hi_i.value = tile_hi & 0xFF
    dut.rst_i.value = 1
    await RisingEdge(dut.clk_i)
    await RisingEdge(dut.clk_i)
    dut.rst_i.value = 0
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    await Timer(1, units="ps")


async def step(
    dut,
) -> dict[str, int | bool]:
    dut.dot_ce_i.value = 1
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


async def run_steps(dut, count: int) -> list[dict[str, int | bool]]:
    return [await step(dut) for _ in range(count)]

@cocotb.test()
async def test_transfer_drives_live_object_fetch_requests_and_fifo_fill(dut):
    await reset_dut(dut)

    first = await step(dut)
    assert first["line_obj_count"] == 1, first
    assert first["ly"] == 0, first

    saw_obj_fetcher = first["fetcher_source"] == FETCHER_OBJ
    saw_oam_req = (
        first["mem_req_count"] > 0
        and first["req_region"] == MEM_REGION_OAM
        and first["req_client"] == MEM_CLIENT_OBJ_FETCHER
    )
    saw_vram_req = (
        first["mem_req_count"] > 0
        and first["req_region"] == MEM_REGION_VRAM
        and first["req_client"] == MEM_CLIENT_OBJ_FETCHER
    )
    saw_obj_fifo = first["obj_fifo_count"] > 0

    last = first
    for _ in range(16):
        last = await step(dut)
        saw_obj_fetcher = saw_obj_fetcher or last["fetcher_source"] == FETCHER_OBJ
        saw_oam_req = saw_oam_req or (
            last["mem_req_count"] > 0
            and last["req_region"] == MEM_REGION_OAM
            and last["req_client"] == MEM_CLIENT_OBJ_FETCHER
        )
        saw_vram_req = saw_vram_req or (
            last["mem_req_count"] > 0
            and last["req_region"] == MEM_REGION_VRAM
            and last["req_client"] == MEM_CLIENT_OBJ_FETCHER
        )
        saw_obj_fifo = saw_obj_fifo or last["obj_fifo_count"] > 0
        if saw_obj_fetcher and saw_oam_req and saw_vram_req and saw_obj_fifo:
            break

    assert saw_obj_fetcher, last
    assert saw_oam_req, last
    assert saw_vram_req, last
    assert saw_obj_fifo, last


@cocotb.test()
async def test_seeded_object_fetch_reaches_object_pixel_scanout(dut):
    await reset_dut(dut, line_obj_count=1, ticket0_x=9, start_x_out=1, start_dot_in_line=80)

    snapshots = await run_steps(dut, 48)

    object_pixels = [
        s for s in snapshots
        if s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
    ]

    assert object_pixels, snapshots
    assert object_pixels[0]["scanout_x"] >= 1, object_pixels[0]
    assert object_pixels[0]["scanout_shade"] != 0, object_pixels[0]
    assert object_pixels[-1]["scanout_x"] > object_pixels[0]["scanout_x"], object_pixels


@cocotb.test()
async def test_seeded_solid_object_row_emits_contiguous_pixels(dut):
    await reset_dut(
        dut,
        line_obj_count=1,
        ticket0_x=9,
        start_x_out=1,
        start_dot_in_line=80,
        tile_lo=0xFF,
        tile_hi=0xFF,
    )

    snapshots = await run_steps(dut, 48)
    object_pixels = [
        s for s in snapshots
        if s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
    ]

    assert len(object_pixels) >= 8, snapshots
    first_eight = object_pixels[:8]
    xs = [int(s["scanout_x"]) for s in first_eight]
    shades = [int(s["scanout_shade"]) for s in first_eight]
    assert xs == list(range(xs[0], xs[0] + 8)), first_eight
    assert all(shade == shades[0] for shade in shades), first_eight


@cocotb.test()
async def test_late_object_fetch_keeps_phase_x_out_aligned(dut):
    await reset_dut(
        dut,
        line_obj_count=1,
        ticket0_x=40,
        start_x_out=30,
        start_dot_in_line=109,
        tile_lo=0xFF,
        tile_hi=0xFF,
    )

    snapshots = await run_steps(dut, 80)
    obj_fetch = [s for s in snapshots if s["fetcher_source"] == FETCHER_OBJ]

    assert obj_fetch, snapshots
    assert int(obj_fetch[0]["x_out"]) == 32, obj_fetch[0]
    assert all(int(s["x_out"]) == 32 for s in obj_fetch), obj_fetch
    assert all(int(s["phase_x_out"]) == 32 for s in obj_fetch), obj_fetch


@cocotb.test()
async def test_single_object_fetch_imposes_visible_transfer_penalty_before_x_advances(dut):
    await reset_dut(dut, line_obj_count=1, ticket0_x=9, start_x_out=1, start_dot_in_line=80)

    snapshots = await run_steps(dut, 24)

    assert snapshots[0]["fetcher_source"] == FETCHER_OBJ, snapshots[0]
    assert snapshots[0]["x_out"] == 1, snapshots[0]
    assert snapshots[1]["x_out"] == 1, snapshots[1]
    assert snapshots[2]["x_out"] == 1, snapshots[2]
    assert snapshots[3]["x_out"] == 1, snapshots[3]
    assert any(s["fetcher_step"] == FETCHER_PUSH for s in snapshots), snapshots
    assert any(s["obj_fifo_count"] > 0 for s in snapshots), snapshots
    assert any(s["x_out"] > 1 for s in snapshots[8:]), snapshots


@cocotb.test()
async def test_two_objects_fetch_in_order_and_accumulate_penalty(dut):
    await reset_dut(dut, line_obj_count=2, ticket0_x=9, ticket1_x=17, start_x_out=1, start_dot_in_line=80)

    snapshots = await run_steps(dut, 48)

    saw_first_advance = any(s["line_obj_fetch_index"] >= 1 for s in snapshots)
    saw_second_fetch = any(
        s["line_obj_fetch_index"] == 1
        and s["fetcher_source"] == FETCHER_OBJ
        and s["mem_req_count"] > 0
        for s in snapshots
    )
    saw_second_complete = any(s["line_obj_fetch_index"] >= 2 for s in snapshots)

    assert saw_first_advance, snapshots[-1]
    assert saw_second_fetch, snapshots[-1]
    assert saw_second_complete, snapshots[-1]


@cocotb.test()
async def test_overlapping_objects_start_second_fetch_before_obj_fifo_drains(dut):
    await reset_dut(dut, line_obj_count=2, ticket0_x=9, ticket1_x=11, start_x_out=1, start_dot_in_line=80)

    snapshots = await run_steps(dut, 48)

    saw_first_complete = any(s["line_obj_fetch_index"] >= 1 and s["obj_fifo_count"] > 0 for s in snapshots)
    saw_overlapping_second_fetch = any(
        s["line_obj_fetch_index"] == 1
        and s["fetcher_source"] == FETCHER_OBJ
        and s["mem_req_count"] > 0
        and s["obj_fifo_count"] > 0
        for s in snapshots
    )
    saw_second_complete = any(s["line_obj_fetch_index"] >= 2 for s in snapshots)

    assert saw_first_complete, snapshots[-1]
    assert saw_overlapping_second_fetch, snapshots[-1]
    assert saw_second_complete, snapshots[-1]


@cocotb.test()
async def test_overlapping_second_object_tail_pixels_reach_scanout(dut):
    await reset_dut(
        dut,
        line_obj_count=2,
        ticket0_x=9,
        ticket1_x=11,
        start_x_out=1,
        start_dot_in_line=80,
        tile_lo=0xFF,
        tile_hi=0xFF,
    )

    snapshots = await run_steps(dut, 64)
    object_pixels = [
        s for s in snapshots
        if s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
    ]

    assert len(object_pixels) >= 10, snapshots
    first_ten = object_pixels[:10]
    xs = [int(s["scanout_x"]) for s in first_ten]
    shades = [int(s["scanout_shade"]) for s in first_ten]

    assert xs == list(range(1, 11)), first_ten
    assert shades == [3, 3, 3, 3, 3, 3, 3, 3, 1, 1], (xs, shades, first_ten)


@cocotb.test()
async def test_object_fetch_cancels_cleanly_when_transfer_ends(dut):
    await reset_dut(dut, line_obj_count=1, ticket0_x=159, start_x_out=151, start_dot_in_line=252)

    snapshots = await run_steps(dut, 12)

    saw_obj_fetch = any(s["fetcher_source"] == FETCHER_OBJ for s in snapshots)
    saw_hblank = any(s["phase"] == PHASE_HBLANK for s in snapshots)
    hblank = next(s for s in snapshots if s["phase"] == PHASE_HBLANK)

    assert saw_obj_fetch, snapshots
    assert saw_hblank, snapshots
    assert hblank["fetcher_source"] == FETCHER_BG, hblank
    assert hblank["obj_fifo_count"] == 0, hblank
