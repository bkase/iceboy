# top = ppu::rtl::transfer_penalty_test_top::transfer_penalty_test_top
from __future__ import annotations

import cocotb
from cocotb.triggers import ReadOnly, Timer


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "current_stall_dots": value & 0x1F,
        "align_penalty": (value >> 5) & 0xF,
        "total_penalty": (value >> 9) & 0xF,
        "next_stall_dots": (value >> 13) & 0x1F,
        "already_considered": bool((value >> 18) & 0x1),
        "next_valid": bool((value >> 19) & 0x1),
        "next_source_window": bool((value >> 20) & 0x1),
        "next_tile_x": (value >> 21) & 0x1F,
        "next_tile_y": (value >> 26) & 0x1F,
        "source_window": bool((value >> 31) & 0x1),
        "tile_x": (value >> 32) & 0x1F,
        "tile_y": (value >> 37) & 0x1F,
        "pixel_offset": (value >> 42) & 0x7,
        "leftmost_x": (value >> 45) & 0xFF,
    }


async def sample(
    dut,
    *,
    current_stall_dots: int,
    ticket_x: int,
    visible_ly: int,
    scx: int,
    scy: int,
    wx: int,
    window_enabled_line: bool,
    window_line: int,
    considered_valid: bool = False,
    considered_source_window: bool = False,
    considered_tile_x: int = 0,
    considered_tile_y: int = 0,
) -> dict[str, int | bool]:
    dut.current_stall_dots_i.value = current_stall_dots & 0x1F
    dut.ticket_x_i.value = ticket_x & 0xFF
    dut.visible_ly_i.value = visible_ly & 0xFF
    dut.scx_i.value = scx & 0xFF
    dut.scy_i.value = scy & 0xFF
    dut.wx_i.value = wx & 0xFF
    dut.window_enabled_line_i.value = int(window_enabled_line)
    dut.window_line_i.value = window_line & 0xFF
    dut.considered_valid_i.value = int(considered_valid)
    dut.considered_source_window_i.value = int(considered_source_window)
    dut.considered_tile_x_i.value = considered_tile_x & 0x1F
    dut.considered_tile_y_i.value = considered_tile_y & 0x1F
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_x_zero_exception_adds_eleven_stall_dots_without_marking_considered_tile(dut):
    snapshot = await sample(
        dut,
        current_stall_dots=0,
        ticket_x=0,
        visible_ly=40,
        scx=7,
        scy=3,
        wx=15,
        window_enabled_line=True,
        window_line=5,
        considered_valid=True,
        considered_source_window=True,
        considered_tile_x=1,
        considered_tile_y=0,
    )

    assert snapshot["align_penalty"] == 5
    assert snapshot["total_penalty"] == 11
    assert snapshot["next_stall_dots"] == 11
    assert snapshot["next_valid"] is True
    assert snapshot["next_source_window"] is True
    assert snapshot["next_tile_x"] == 1
    assert snapshot["next_tile_y"] == 0


@cocotb.test()
async def test_per_offset_alignment_penalty_is_added_into_stall_budget(dut):
    expected = {
        0: (6, 12),
        1: (5, 11),
        2: (4, 10),
        3: (3, 9),
        4: (2, 8),
        5: (1, 7),
        6: (0, 6),
        7: (0, 6),
    }

    for offset, (align_penalty, total_penalty) in expected.items():
        snapshot = await sample(
            dut,
            current_stall_dots=3,
            ticket_x=8 + offset,
            visible_ly=0,
            scx=0,
            scy=0,
            wx=0,
            window_enabled_line=False,
            window_line=0,
        )

        assert snapshot["align_penalty"] == align_penalty, (offset, snapshot)
        assert snapshot["total_penalty"] == total_penalty, (offset, snapshot)
        assert snapshot["next_stall_dots"] == 3 + total_penalty, (offset, snapshot)
        assert snapshot["next_valid"] is True, (offset, snapshot)
        assert snapshot["next_tile_x"] == 0, (offset, snapshot)
        assert snapshot["next_tile_y"] == 0, (offset, snapshot)


@cocotb.test()
async def test_same_tile_second_object_suppresses_alignment_penalty(dut):
    snapshot = await sample(
        dut,
        current_stall_dots=4,
        ticket_x=21,
        visible_ly=0,
        scx=0,
        scy=0,
        wx=0,
        window_enabled_line=False,
        window_line=0,
        considered_valid=True,
        considered_source_window=False,
        considered_tile_x=1,
        considered_tile_y=0,
    )

    assert snapshot["already_considered"] is True
    assert snapshot["align_penalty"] == 0
    assert snapshot["total_penalty"] == 6
    assert snapshot["next_stall_dots"] == 10
    assert snapshot["next_tile_x"] == 1
    assert snapshot["next_tile_y"] == 0


@cocotb.test()
async def test_distinct_tile_second_object_keeps_full_alignment_penalty(dut):
    snapshot = await sample(
        dut,
        current_stall_dots=4,
        ticket_x=24,
        visible_ly=0,
        scx=0,
        scy=0,
        wx=0,
        window_enabled_line=False,
        window_line=0,
        considered_valid=True,
        considered_source_window=False,
        considered_tile_x=1,
        considered_tile_y=0,
    )

    assert snapshot["already_considered"] is False
    assert snapshot["align_penalty"] == 6
    assert snapshot["total_penalty"] == 12
    assert snapshot["next_stall_dots"] == 16
    assert snapshot["next_tile_x"] == 2
    assert snapshot["next_tile_y"] == 0
