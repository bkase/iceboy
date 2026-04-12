# top = video::framebuffer_spram_test_top::framebuffer_spram_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


SCANOUT_NONE = 0
SCANOUT_FRAME_START = 1
SCANOUT_LINE_START = 2
SCANOUT_BLANK = 3
SCANOUT_PIXEL = 4

FRAMEBUFFER_PIXELS = 160 * 144


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "pixel_shade": value & 0xFF,
        "next_read_addr": (value >> 8) & 0xFFFF,
        "reader_active": bool((value >> 24) & 0x1),
        "read_pending": bool((value >> 25) & 0x1),
        "frame_start": bool((value >> 26) & 0x1),
        "pixel_valid": bool((value >> 27) & 0x1),
    }


def shade_for(x: int, y: int) -> int:
    return (x ^ (y * 3)) & 0x3


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.rst_i.value = 1
    dut.scanout_kind_i.value = SCANOUT_NONE
    dut.scanout_x_i.value = 0
    dut.scanout_y_i.value = 0
    dut.scanout_shade_i.value = 0
    dut.pixel_advance_i.value = 0
    await RisingEdge(dut.clk_i)
    await RisingEdge(dut.clk_i)
    dut.rst_i.value = 0
    await Timer(1, units="ps")


async def step(
    dut,
    *,
    scanout_kind: int = SCANOUT_NONE,
    scanout_x: int = 0,
    scanout_y: int = 0,
    scanout_shade: int = 0,
    pixel_advance: bool = False,
) -> dict[str, int | bool]:
    dut.scanout_kind_i.value = scanout_kind
    dut.scanout_x_i.value = scanout_x & 0xFF
    dut.scanout_y_i.value = scanout_y & 0xFF
    dut.scanout_shade_i.value = scanout_shade & 0x3
    dut.pixel_advance_i.value = int(pixel_advance)
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


async def wait_for_pixel(dut, *, max_cycles: int = 12) -> dict[str, int | bool]:
    for _ in range(max_cycles):
        snapshot = await step(dut)
        if snapshot["pixel_valid"]:
            return snapshot
    raise AssertionError("pixel_valid did not assert")


@cocotb.test()
async def test_full_frame_writes_land_in_linear_pixel_order(dut):
    await reset_dut(dut)

    for y in range(144):
        for x in range(160):
            await step(dut, scanout_kind=SCANOUT_PIXEL, scanout_x=x, scanout_y=y, scanout_shade=shade_for(x, y))

    started = await step(dut, scanout_kind=SCANOUT_FRAME_START)
    assert started["reader_active"] is True
    assert started["next_read_addr"] == 1

    expected = [
        shade_for(0, 0),
        shade_for(1, 0),
        shade_for(2, 0),
        shade_for(159, 0),
        shade_for(0, 1),
    ]
    observed: list[int] = []

    for target_index in [0, 1, 2, 159, 160]:
        while len(observed) <= target_index:
            pixel = await wait_for_pixel(dut)
            observed.append(int(pixel["pixel_shade"]) & 0x3)
            await step(dut, pixel_advance=True)

    assert observed[0] == expected[0]
    assert observed[1] == expected[1]
    assert observed[2] == expected[2]
    assert observed[159] == expected[3]
    assert observed[160] == expected[4]
    assert len(observed) == 161


@cocotb.test()
async def test_write_priority_stalls_reads_until_the_conflicting_pixel_update_lands(dut):
    await reset_dut(dut)

    for x in range(4):
        await step(dut, scanout_kind=SCANOUT_PIXEL, scanout_x=x, scanout_y=0, scanout_shade=x & 0x3)

    await step(dut, scanout_kind=SCANOUT_FRAME_START)
    first_pixel = await wait_for_pixel(dut)
    assert int(first_pixel["pixel_shade"]) & 0x3 == 0

    await step(dut, pixel_advance=True)
    blocked = await step(dut, scanout_kind=SCANOUT_PIXEL, scanout_x=1, scanout_y=0, scanout_shade=3)
    assert blocked["read_pending"] is False
    assert blocked["next_read_addr"] == 1
    assert blocked["pixel_valid"] is False

    issued = await step(dut)
    assert issued["read_pending"] is True
    assert issued["next_read_addr"] == 2

    next_pixel = await wait_for_pixel(dut)
    assert int(next_pixel["pixel_shade"]) & 0x3 == 3


@cocotb.test()
async def test_frame_start_is_a_one_shot_sync_pulse_while_idle_only(dut):
    await reset_dut(dut)

    await step(dut, scanout_kind=SCANOUT_PIXEL, scanout_x=0, scanout_y=0, scanout_shade=2)

    started = await step(dut, scanout_kind=SCANOUT_FRAME_START)
    assert started["reader_active"] is True
    assert started["next_read_addr"] == 1

    pixel = await wait_for_pixel(dut)
    assert int(pixel["pixel_shade"]) & 0x3 == 2

    mid_sweep = await step(dut, scanout_kind=SCANOUT_FRAME_START)
    assert mid_sweep["reader_active"] is True
    assert mid_sweep["next_read_addr"] >= 1
