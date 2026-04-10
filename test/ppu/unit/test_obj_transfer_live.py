# top = ppu::rtl::obj_transfer_live_test_top::obj_transfer_live_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


REQ_IDLE = 0
REQ_READ = 1
REQ_WRITE = 2
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
        "active_obj_oam_index": (value >> 97) & 0x3F,
        "active_obj_x": (value >> 103) & 0xFF,
    }


def lcdc_with_obj_enable(obj_size_8x16: bool, obj_enable: bool) -> int:
    return 0x80 | 0x10 | (0x04 if obj_size_8x16 else 0x00) | (0x02 if obj_enable else 0x00) | 0x01


async def reset_dut(
    dut,
    *,
    line_obj_count: int = 1,
    ticket0_x: int = 9,
    ticket1_x: int = 17,
    ticket2_x: int = 25,
    ticket_y: int = 16,
    visible_ly: int = 0,
    obj_size_8x16: bool = False,
    obj_enable: bool = True,
    start_x_out: int = 1,
    start_dot_in_line: int = 80,
    tile_id: int = 0x01,
    flags: int = 0x00,
    tile_lo: int = 0x50,
    tile_hi: int = 0x30,
    write_valid: bool = False,
    write_target: int = 0,
    write_value: int = 0,
    use_bridge: bool = False,
    m_ce: bool = False,
    req_kind: int = REQ_IDLE,
    req_addr: int = 0,
    req_data: int = 0,
    start_in_oam_scan: bool = False,
) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.dot_ce_i.value = 0
    dut.line_obj_count_i.value = line_obj_count & 0xF
    dut.ticket0_x_i.value = ticket0_x & 0xFF
    dut.ticket1_x_i.value = ticket1_x & 0xFF
    dut.ticket2_x_i.value = ticket2_x & 0xFF
    dut.ticket_y_i.value = ticket_y & 0xFF
    dut.visible_ly_i.value = visible_ly & 0xFF
    dut.obj_size_8x16_i.value = int(obj_size_8x16)
    dut.obj_enable_i.value = int(obj_enable)
    dut.start_x_out_i.value = start_x_out & 0xFF
    dut.start_dot_in_line_i.value = start_dot_in_line & 0x1FF
    dut.tile_id_i.value = tile_id & 0xFF
    dut.flags_i.value = flags & 0xFF
    dut.tile_lo_i.value = tile_lo & 0xFF
    dut.tile_hi_i.value = tile_hi & 0xFF
    dut.write_valid_i.value = int(write_valid)
    dut.write_target_i.value = write_target & 0xF
    dut.write_value_i.value = write_value & 0xFF
    dut.use_bridge_i.value = int(use_bridge)
    dut.m_ce_i.value = int(m_ce)
    dut.req_kind_i.value = req_kind & 0x3
    dut.req_addr_i.value = req_addr & 0xFFFF
    dut.req_data_i.value = req_data & 0xFF
    dut.start_in_oam_scan_i.value = int(start_in_oam_scan)
    dut.rst_i.value = 1
    await RisingEdge(dut.clk_i)
    await RisingEdge(dut.clk_i)
    dut.rst_i.value = 0
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    await Timer(1, units="ps")


async def step(
    dut,
    *,
    write_valid: bool = False,
    write_target: int = 0,
    write_value: int = 0,
    use_bridge: bool = False,
    m_ce: bool = False,
    req_kind: int = REQ_IDLE,
    req_addr: int = 0,
    req_data: int = 0,
) -> dict[str, int | bool]:
    dut.write_valid_i.value = int(write_valid)
    dut.write_target_i.value = write_target & 0xF
    dut.write_value_i.value = write_value & 0xFF
    dut.use_bridge_i.value = int(use_bridge)
    dut.m_ce_i.value = int(m_ce)
    dut.req_kind_i.value = req_kind & 0x3
    dut.req_addr_i.value = req_addr & 0xFFFF
    dut.req_data_i.value = req_data & 0xFF
    dut.dot_ce_i.value = 1
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


async def run_steps(dut, count: int) -> list[dict[str, int | bool]]:
    return [await step(dut) for _ in range(count)]


async def step_with_lcdc_write(dut, value: int) -> dict[str, int | bool]:
    return await step(dut, write_valid=True, write_target=0, write_value=value)


async def step_with_bridge_lcdc_write(dut, value: int) -> dict[str, int | bool]:
    return await step(dut, use_bridge=True, m_ce=True, req_kind=REQ_WRITE, req_addr=0xFF40, req_data=value)

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

    snapshots = await run_steps(dut, 48)

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
async def test_smaller_x_object_fetches_before_earlier_oam_entry(dut):
    await reset_dut(dut, line_obj_count=2, ticket0_x=64, ticket1_x=50, start_x_out=42, start_dot_in_line=121)

    snapshots = await run_steps(dut, 24)
    first_obj_fetch = next(
        (
            s for s in snapshots
            if s["fetcher_source"] == FETCHER_OBJ
            and s["mem_req_count"] > 0
            and s["req_region"] == MEM_REGION_OAM
            and s["req_client"] == MEM_CLIENT_OBJ_FETCHER
        ),
        None,
    )

    assert first_obj_fetch is not None, snapshots
    assert first_obj_fetch["active_obj_oam_index"] == 1, first_obj_fetch
    assert first_obj_fetch["active_obj_x"] == 50, first_obj_fetch


@cocotb.test()
async def test_three_contiguous_objects_reach_the_third_object_pixels(dut):
    await reset_dut(
        dut,
        line_obj_count=3,
        ticket0_x=9,
        ticket1_x=17,
        ticket2_x=25,
        start_x_out=1,
        start_dot_in_line=80,
        tile_lo=0xFF,
        tile_hi=0xFF,
    )

    snapshots = await run_steps(dut, 96)
    object_pixels = [
        s for s in snapshots
        if s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
    ]

    assert object_pixels, snapshots
    xs = {int(s["scanout_x"]) for s in object_pixels}
    assert all(x in xs for x in range(17, 25)), sorted(xs)


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

    snapshots = await run_steps(dut, 48)

    saw_obj_fetch = any(s["fetcher_source"] == FETCHER_OBJ for s in snapshots)
    saw_hblank = any(s["phase"] == PHASE_HBLANK for s in snapshots)
    hblank = next(s for s in snapshots if s["phase"] == PHASE_HBLANK)

    assert saw_obj_fetch, snapshots
    assert saw_hblank, snapshots
    assert hblank["fetcher_source"] == FETCHER_BG, hblank
    assert hblank["obj_fifo_count"] == 0, hblank


@cocotb.test()
async def test_flipped_8x16_odd_tile_lower_half_uses_expected_addr_and_emits_pixels(dut):
    await reset_dut(
        dut,
        line_obj_count=1,
        ticket0_x=56,
        ticket_y=32,
        visible_ly=31,
        obj_size_8x16=True,
        start_x_out=48,
        start_dot_in_line=140,
        tile_id=0x03,
        flags=0x40,
        tile_lo=0xFF,
        tile_hi=0xFF,
    )

    snapshots = await run_steps(dut, 48)
    vram_req_addrs = [
        int(s["req_addr"])
        for s in snapshots
        if s["mem_req_count"] > 0
        and s["req_region"] == MEM_REGION_VRAM
        and s["req_client"] == MEM_CLIENT_OBJ_FETCHER
    ]
    assert 0x8020 in vram_req_addrs, vram_req_addrs
    assert 0x8021 in vram_req_addrs, vram_req_addrs

    object_pixels = [
        s for s in snapshots
        if s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
    ]
    assert object_pixels, snapshots


@cocotb.test()
async def test_eight_contiguous_objects_reach_late_object_pixels(dut):
    await reset_dut(
        dut,
        line_obj_count=8,
        ticket0_x=48,
        ticket1_x=56,
        ticket2_x=64,
        start_x_out=40,
        start_dot_in_line=120,
        tile_lo=0xFF,
        tile_hi=0xFF,
    )

    snapshots = await run_steps(dut, 192)
    object_pixels = [
        s for s in snapshots
        if s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
    ]

    assert object_pixels, snapshots
    xs = {int(s["scanout_x"]) for s in object_pixels}
    assert all(x in xs for x in range(88, 104)), sorted(xs)


@cocotb.test()
async def test_object_enable_low_cancels_active_fetch_and_reenable_restarts_it(dut):
    await reset_dut(
        dut,
        line_obj_count=1,
        ticket0_x=9,
        start_x_out=1,
        start_dot_in_line=80,
        tile_lo=0xFF,
        tile_hi=0xFF,
    )

    armed = []
    for _ in range(4):
        snapshot = await step(dut)
        armed.append(snapshot)
        if snapshot["fetcher_source"] == FETCHER_OBJ:
            break

    assert any(s["fetcher_source"] == FETCHER_OBJ for s in armed), armed

    disabled = [await step_with_lcdc_write(dut, lcdc_with_obj_enable(False, False))] + await run_steps(dut, 7)
    assert all(s["fetcher_source"] != FETCHER_OBJ for s in disabled), disabled
    assert all(s["obj_fifo_count"] == 0 for s in disabled), disabled
    assert not any(
        s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
        for s in disabled
    ), disabled

    resumed = [await step_with_lcdc_write(dut, lcdc_with_obj_enable(False, True))] + await run_steps(dut, 31)
    assert any(
        s["fetcher_source"] == FETCHER_OBJ
        and s["mem_req_count"] > 0
        and s["req_client"] == MEM_CLIENT_OBJ_FETCHER
        for s in resumed
    ), resumed
    assert any(
        s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
        for s in resumed
    ), resumed


@cocotb.test()
async def test_lcdc_disable_bus_event_blocks_first_late_object_pixels(dut):
    await reset_dut(
        dut,
        line_obj_count=1,
        ticket0_x=128,
        start_x_out=116,
        start_dot_in_line=195,
        tile_lo=0xFF,
        tile_hi=0xFF,
    )

    armed = []
    for _ in range(16):
        snapshot = await step(dut)
        armed.append(snapshot)
        if int(snapshot["x_out"]) >= 118:
            break

    assert int(armed[-1]["x_out"]) >= 118, armed

    disabled = await step_with_lcdc_write(dut, 0x91)
    tail = [disabled] + await run_steps(dut, 24)
    object_pixels = [
        s for s in tail
        if s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
    ]

    assert not object_pixels, object_pixels


@cocotb.test()
async def test_bridge_lcdc_disable_blocks_first_late_object_pixels(dut):
    await reset_dut(
        dut,
        line_obj_count=1,
        ticket0_x=128,
        start_x_out=116,
        start_dot_in_line=195,
        tile_lo=0xFF,
        tile_hi=0xFF,
        use_bridge=True,
    )

    armed = []
    for _ in range(16):
        snapshot = await step(dut, use_bridge=True)
        armed.append(snapshot)
        if int(snapshot["x_out"]) >= 118:
            break

    assert int(armed[-1]["x_out"]) >= 118, armed

    disabled = await step_with_bridge_lcdc_write(dut, 0x91)
    tail = [disabled] + [await step(dut, use_bridge=True) for _ in range(24)]
    object_pixels = [
        s for s in tail
        if s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
    ]

    assert not object_pixels, object_pixels


@cocotb.test()
async def test_bridge_lcdc_disable_after_fixed_late_line_delay_blocks_first_target_row(dut):
    await reset_dut(
        dut,
        line_obj_count=3,
        ticket0_x=128,
        ticket1_x=136,
        ticket2_x=144,
        start_x_out=116,
        start_dot_in_line=195,
        tile_lo=0xFF,
        tile_hi=0xFF,
        use_bridge=True,
    )

    pre_disable = [await step(dut, use_bridge=True) for _ in range(12)]
    disabled = await step_with_bridge_lcdc_write(dut, 0x91)
    tail = [disabled] + [await step(dut, use_bridge=True) for _ in range(24)]

    leaked_first_row_pixels = [
        s for s in tail
        if s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
        and 120 <= int(s["scanout_x"]) <= 127
    ]

    assert int(pre_disable[-1]["x_out"]) >= 120 or pre_disable[-1]["fetcher_source"] == FETCHER_OBJ, pre_disable
    assert not leaked_first_row_pixels, leaked_first_row_pixels


@cocotb.test()
async def test_bridge_lcdc_disable_after_row_loop_like_delay_blocks_first_target_row(dut):
    await reset_dut(
        dut,
        line_obj_count=3,
        ticket0_x=128,
        ticket1_x=136,
        ticket2_x=144,
        start_x_out=64,
        start_dot_in_line=144,
        tile_lo=0xFF,
        tile_hi=0xFF,
        use_bridge=True,
    )

    pre_disable = [await step(dut, use_bridge=True) for _ in range(72)]
    disabled = await step_with_bridge_lcdc_write(dut, 0x91)
    tail = [disabled] + [await step(dut, use_bridge=True) for _ in range(48)]

    leaked_first_row_pixels = [
        s for s in tail
        if s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
        and 120 <= int(s["scanout_x"]) <= 127
    ]

    assert (
        120 <= int(pre_disable[-1]["x_out"]) <= 127
        or pre_disable[-1]["fetcher_source"] == FETCHER_OBJ
    ), pre_disable[-8:]
    assert not leaked_first_row_pixels, leaked_first_row_pixels


@cocotb.test()
async def test_bridge_lcdc_disable_after_oam_to_transfer_boundary_blocks_first_target_row(dut):
    await reset_dut(
        dut,
        line_obj_count=3,
        ticket0_x=128,
        ticket1_x=136,
        ticket2_x=144,
        visible_ly=40,
        start_x_out=0,
        start_dot_in_line=79,
        tile_lo=0xFF,
        tile_hi=0xFF,
        use_bridge=True,
        start_in_oam_scan=True,
    )

    pre_disable = [await step(dut, use_bridge=True) for _ in range(37)]
    disabled = await step_with_bridge_lcdc_write(dut, 0x91)
    tail = [disabled] + [await step(dut, use_bridge=True) for _ in range(48)]

    leaked_first_row_pixels = [
        s for s in tail
        if s["scanout_valid"]
        and s["scanout_kind"] == SCANOUT_PIXEL
        and s["scanout_source"] == PIXEL_SOURCE_OBJECT
        and 120 <= int(s["scanout_x"]) <= 127
    ]

    assert any(s["phase"] == PHASE_TRANSFER for s in pre_disable), pre_disable
    assert not leaked_first_row_pixels, leaked_first_row_pixels


@cocotb.test()
async def test_late_object_fetch_does_not_leave_stale_object_state_on_next_line(dut):
    await reset_dut(
        dut,
        line_obj_count=3,
        ticket0_x=128,
        ticket1_x=136,
        ticket2_x=144,
        visible_ly=39,
        start_x_out=116,
        start_dot_in_line=195,
        tile_lo=0xFF,
        tile_hi=0xFF,
    )

    crossed = []
    for _ in range(320):
        snapshot = await step(dut)
        crossed.append(snapshot)
        if snapshot["ly"] == 40 and snapshot["phase"] != PHASE_TRANSFER:
            break

    assert crossed[-1]["ly"] == 40, crossed[-8:]
    assert crossed[-1]["phase"] != PHASE_TRANSFER, crossed[-8:]
    assert crossed[-1]["fetcher_source"] != FETCHER_OBJ, crossed[-8:]
    assert crossed[-1]["obj_fifo_count"] == 0, crossed[-8:]
