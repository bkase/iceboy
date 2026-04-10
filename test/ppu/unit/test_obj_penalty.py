# top = ppu::rtl::obj_penalty_test_top::obj_penalty_test_top
from __future__ import annotations

import sys
from pathlib import Path

import cocotb
from cocotb.triggers import ReadOnly, Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from obj_penalty_reference import (
    CHECKER_BALL_CANCEL_OVERLAP_BG_CASE,
    WINDOW_BASIC_BG_CASE,
    WINDOW_BASIC_WINDOW_NEXT_TILE_CASE,
    WINDOW_BASIC_WINDOW_THRESHOLD_CASE,
)


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "leftmost_x": value & 0xFF,
        "source_window": bool((value >> 8) & 0x1),
        "tile_x": (value >> 9) & 0x1F,
        "tile_y": (value >> 14) & 0x1F,
        "pixel_offset": (value >> 19) & 0x7,
        "already_considered": bool((value >> 22) & 0x1),
        "align_penalty": (value >> 23) & 0xF,
        "total_penalty": (value >> 27) & 0xF,
        "next_valid": bool((value >> 31) & 0x1),
        "next_source_window": bool((value >> 32) & 0x1),
        "next_tile_x": (value >> 33) & 0x1F,
        "next_tile_y": (value >> 38) & 0x1F,
    }


async def sample(
    dut,
    *,
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
async def test_pyboy_bg_reference_case_matches_helper_tile_selection(dut):
    case = CHECKER_BALL_CANCEL_OVERLAP_BG_CASE
    snapshot = await sample(
        dut,
        ticket_x=case.leftmost_pixel_x + 8,
        visible_ly=case.visible_ly,
        scx=case.scx,
        scy=case.scy,
        wx=case.wx,
        window_enabled_line=case.window_enabled_line,
        window_line=case.window_line,
    )

    assert snapshot["leftmost_x"] == case.leftmost_pixel_x
    assert snapshot["source_window"] is case.expected_source_window
    assert snapshot["tile_x"] == case.expected_tile_x
    assert snapshot["tile_y"] == case.expected_tile_y
    assert snapshot["pixel_offset"] == 0
    assert snapshot["align_penalty"] == 5
    assert snapshot["total_penalty"] == 11


@cocotb.test()
async def test_pyboy_window_reference_cases_match_helper_tile_selection(dut):
    for case in (
        WINDOW_BASIC_BG_CASE,
        WINDOW_BASIC_WINDOW_THRESHOLD_CASE,
        WINDOW_BASIC_WINDOW_NEXT_TILE_CASE,
    ):
        snapshot = await sample(
            dut,
            ticket_x=case.leftmost_pixel_x + 8,
            visible_ly=case.visible_ly,
            scx=case.scx,
            scy=case.scy,
            wx=case.wx,
            window_enabled_line=case.window_enabled_line,
            window_line=case.window_line,
        )

        assert snapshot["leftmost_x"] == case.leftmost_pixel_x, (case.name, snapshot)
        assert snapshot["source_window"] is case.expected_source_window, (case.name, snapshot)
        assert snapshot["tile_x"] == case.expected_tile_x, (case.name, snapshot)
        assert snapshot["tile_y"] == case.expected_tile_y, (case.name, snapshot)


@cocotb.test()
async def test_scx_alignment_changes_bg_pixel_offset_and_penalty(dut):
    snapshot = await sample(
        dut,
        ticket_x=40,
        visible_ly=24,
        scx=5,
        scy=0,
        wx=0,
        window_enabled_line=False,
        window_line=0,
    )

    assert snapshot["leftmost_x"] == 32
    assert snapshot["source_window"] is False
    assert snapshot["tile_x"] == 4
    assert snapshot["tile_y"] == 3
    assert snapshot["pixel_offset"] == 5
    assert snapshot["align_penalty"] == 0
    assert snapshot["total_penalty"] == 6


@cocotb.test()
async def test_already_considered_tile_suppresses_alignment_penalty(dut):
    snapshot = await sample(
        dut,
        ticket_x=121,
        visible_ly=80,
        scx=0,
        scy=0,
        wx=0,
        window_enabled_line=False,
        window_line=0,
        considered_valid=True,
        considered_source_window=False,
        considered_tile_x=14,
        considered_tile_y=10,
    )

    assert snapshot["leftmost_x"] == 113
    assert snapshot["tile_x"] == 14
    assert snapshot["tile_y"] == 10
    assert snapshot["already_considered"] is True
    assert snapshot["align_penalty"] == 0
    assert snapshot["total_penalty"] == 6


@cocotb.test()
async def test_next_tile_restarts_alignment_penalty_after_considered_tile(dut):
    snapshot = await sample(
        dut,
        ticket_x=129,
        visible_ly=80,
        scx=0,
        scy=0,
        wx=0,
        window_enabled_line=False,
        window_line=0,
        considered_valid=True,
        considered_source_window=False,
        considered_tile_x=14,
        considered_tile_y=10,
    )

    assert snapshot["leftmost_x"] == 121
    assert snapshot["tile_x"] == 15
    assert snapshot["tile_y"] == 10
    assert snapshot["already_considered"] is False
    assert snapshot["pixel_offset"] == 1
    assert snapshot["align_penalty"] == 4
    assert snapshot["total_penalty"] == 10
    assert snapshot["next_valid"] is True
    assert snapshot["next_source_window"] is False
    assert snapshot["next_tile_x"] == 15
    assert snapshot["next_tile_y"] == 10


@cocotb.test()
async def test_x_zero_special_case_forces_eleven_dot_penalty(dut):
    snapshot = await sample(
        dut,
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

    assert snapshot["leftmost_x"] == 0
    assert snapshot["align_penalty"] == 5
    assert snapshot["total_penalty"] == 11
    assert snapshot["next_valid"] is True
    assert snapshot["next_source_window"] is True
    assert snapshot["next_tile_x"] == 1
    assert snapshot["next_tile_y"] == 0
