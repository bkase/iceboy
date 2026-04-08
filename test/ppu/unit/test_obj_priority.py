# top = ppu::rtl::obj_priority_test_top::obj_priority_test_top
from __future__ import annotations

import sys
from pathlib import Path

import cocotb
from cocotb.triggers import ReadOnly, Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from logging_std import TestLogger


SUITE_NAME = "test_obj_priority.py"


def case_logger(case_name: str) -> TestLogger:
    suite = TestLogger(suite_name=SUITE_NAME, stream=sys.stdout, color=False)
    suite.suite()
    return suite.bind_case(case_name)


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "overlap": bool(value & 0x1),
        "selected": bool((value >> 1) & 0x1),
        "next_found": (value >> 2) & 0xF,
        "next_count": (value >> 6) & 0xF,
        "ticket_oam_index": (value >> 10) & 0x3F,
        "ticket_x": (value >> 16) & 0xFF,
        "ticket_y": (value >> 24) & 0xFF,
        "ticket_rank": (value >> 32) & 0xF,
        "chosen_color": (value >> 36) & 0x3,
        "chosen_palette": (value >> 38) & 0x1,
        "chosen_bg_over_obj": bool((value >> 39) & 0x1),
        "chosen_x": (value >> 40) & 0xFF,
        "chosen_rank": (value >> 48) & 0xF,
        "mixed_shade": (value >> 52) & 0x3,
        "mixed_source": (value >> 54) & 0x3,
        "direct_overlap": bool((value >> 56) & 0x1),
        "incoming_precedes": bool((value >> 57) & 0x1),
    }


async def sample(
    dut,
    *,
    ly: int = 0,
    scan_obj_y: int = 0x10,
    scan_obj_x: int = 0x20,
    obj_size_8x16: bool = False,
    obj_enable: bool = True,
    scan_index: int = 0,
    found: int = 0,
    count: int = 0,
    bg_color_idx: int = 0,
    bg_from_window: bool = False,
    bg_enable: bool = True,
    bgp_pop: int = 0xE4,
    obp0_pop: int = 0xE4,
    obp1_pop: int = 0x1B,
    existing_color: int = 0,
    existing_palette_sel: bool = False,
    existing_bg_over_obj: bool = False,
    existing_x: int = 20,
    existing_selection_rank: int = 0,
    incoming_color: int = 0,
    incoming_palette_sel: bool = False,
    incoming_bg_over_obj: bool = False,
    incoming_x: int = 20,
    incoming_selection_rank: int = 1,
) -> dict[str, int | bool]:
    dut.ly_i.value = ly & 0xFF
    dut.scan_obj_y_i.value = scan_obj_y & 0xFF
    dut.scan_obj_x_i.value = scan_obj_x & 0xFF
    dut.obj_size_8x16_i.value = int(obj_size_8x16)
    dut.obj_enable_i.value = int(obj_enable)
    dut.scan_index_i.value = scan_index & 0x3F
    dut.found_i.value = found & 0xF
    dut.count_i.value = count & 0xF
    dut.bg_color_idx_i.value = bg_color_idx & 0x3
    dut.bg_from_window_i.value = int(bg_from_window)
    dut.bg_enable_i.value = int(bg_enable)
    dut.bgp_pop_i.value = bgp_pop & 0xFF
    dut.obp0_pop_i.value = obp0_pop & 0xFF
    dut.obp1_pop_i.value = obp1_pop & 0xFF
    dut.existing_color_i.value = existing_color & 0x3
    dut.existing_palette_sel_i.value = int(existing_palette_sel)
    dut.existing_bg_over_obj_i.value = int(existing_bg_over_obj)
    dut.existing_x_i.value = existing_x & 0xFF
    dut.existing_selection_rank_i.value = existing_selection_rank & 0xF
    dut.incoming_color_i.value = incoming_color & 0x3
    dut.incoming_palette_sel_i.value = int(incoming_palette_sel)
    dut.incoming_bg_over_obj_i.value = int(incoming_bg_over_obj)
    dut.incoming_x_i.value = incoming_x & 0xFF
    dut.incoming_selection_rank_i.value = incoming_selection_rank & 0xF
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


def require(logger: TestLogger, snapshot: dict[str, int | bool], *, expected: dict[str, int | bool]) -> None:
    for field, value in expected.items():
        assert logger.check(field, expected=value, actual=snapshot[field]), (
            f"{field} mismatch: expected={value} actual={snapshot[field]} snapshot={snapshot}"
        )


@cocotb.test()
async def test_basic_selection_builds_ticket_for_visible_object(dut):
    logger = case_logger("test_basic_selection_builds_ticket_for_visible_object")
    snapshot = await sample(dut, ly=0, scan_obj_y=0x10, scan_obj_x=0x28, scan_index=5, found=0, count=0)
    require(
        logger,
        snapshot,
        expected={
            "overlap": True,
            "direct_overlap": True,
            "selected": True,
            "next_found": 1,
            "next_count": 1,
            "ticket_oam_index": 5,
            "ticket_x": 0x28,
            "ticket_y": 0x10,
            "ticket_rank": 0,
        },
    )


@cocotb.test()
async def test_selection_caps_at_ten_objects_and_excludes_eleventh(dut):
    logger = case_logger("test_selection_caps_at_ten_objects_and_excludes_eleventh")
    tenth = await sample(dut, ly=0x0F, scan_obj_y=0x10, scan_obj_x=0x44, obj_size_8x16=True, scan_index=9, found=9, count=9)
    require(logger, tenth, expected={"selected": True, "next_found": 10, "next_count": 10, "ticket_oam_index": 9, "ticket_rank": 9})

    eleventh = await sample(dut, ly=0x0F, scan_obj_y=0x10, scan_obj_x=0x55, obj_size_8x16=True, scan_index=10, found=10, count=10)
    require(logger, eleventh, expected={"selected": False, "next_found": 10, "next_count": 10, "ticket_oam_index": 9, "ticket_rank": 9})


@cocotb.test()
async def test_selection_order_tracks_oam_scan_order_not_object_position(dut):
    logger = case_logger("test_selection_order_tracks_oam_scan_order_not_object_position")
    first = await sample(dut, ly=0x20, scan_obj_y=0x30, scan_obj_x=0x80, scan_index=12, found=0, count=0)
    second = await sample(dut, ly=0x20, scan_obj_y=0x2D, scan_obj_x=0x08, scan_index=13, found=1, count=1)
    third = await sample(dut, ly=0x20, scan_obj_y=0x29, scan_obj_x=0xF0, scan_index=14, found=2, count=2)
    require(logger, first, expected={"selected": True, "ticket_oam_index": 12, "ticket_rank": 0})
    require(logger, second, expected={"selected": True, "ticket_oam_index": 13, "ticket_rank": 1})
    require(logger, third, expected={"selected": True, "ticket_oam_index": 14, "ticket_rank": 2})


@cocotb.test()
async def test_hidden_x_objects_still_count_and_obj_disable_suppresses_selection(dut):
    logger = case_logger("test_hidden_x_objects_still_count_and_obj_disable_suppresses_selection")
    hidden_left = await sample(dut, ly=0, scan_obj_y=0x10, scan_obj_x=0x00, scan_index=2, found=0, count=0)
    hidden_right = await sample(dut, ly=0, scan_obj_y=0x10, scan_obj_x=0xA8, scan_index=3, found=1, count=1)
    disabled = await sample(dut, ly=0, scan_obj_y=0x10, scan_obj_x=0x20, obj_enable=False, scan_index=4, found=0, count=0)
    require(logger, hidden_left, expected={"selected": True, "next_count": 1, "ticket_x": 0x00, "ticket_rank": 0})
    require(logger, hidden_right, expected={"selected": True, "next_count": 2, "ticket_x": 0xA8, "ticket_rank": 1})
    require(logger, disabled, expected={"overlap": True, "selected": False, "next_found": 0, "next_count": 0})


@cocotb.test()
async def test_smaller_x_wins_draw_priority_between_overlapping_objects(dut):
    logger = case_logger("test_smaller_x_wins_draw_priority_between_overlapping_objects")
    snapshot = await sample(
        dut,
        existing_color=2,
        existing_x=20,
        existing_selection_rank=0,
        incoming_color=3,
        incoming_x=10,
        incoming_selection_rank=5,
        obp1_pop=0b11_10_01_00,
        incoming_palette_sel=True,
    )
    require(
        logger,
        snapshot,
        expected={
            "incoming_precedes": True,
            "chosen_color": 3,
            "chosen_x": 10,
            "chosen_rank": 5,
            "chosen_palette": 1,
            "mixed_shade": 3,
            "mixed_source": 2,
        },
    )


@cocotb.test()
async def test_lower_selection_rank_breaks_same_x_ties(dut):
    logger = case_logger("test_lower_selection_rank_breaks_same_x_ties")
    incoming_wins = await sample(
        dut,
        existing_color=1,
        existing_x=24,
        existing_selection_rank=6,
        incoming_color=2,
        incoming_x=24,
        incoming_selection_rank=2,
    )
    existing_wins = await sample(
        dut,
        existing_color=3,
        existing_x=24,
        existing_selection_rank=1,
        incoming_color=2,
        incoming_x=24,
        incoming_selection_rank=4,
    )
    require(logger, incoming_wins, expected={"incoming_precedes": True, "chosen_color": 2, "chosen_rank": 2})
    require(logger, existing_wins, expected={"incoming_precedes": False, "chosen_color": 3, "chosen_rank": 1})


@cocotb.test()
async def test_transparent_object_falls_back_to_other_sprite_candidate(dut):
    logger = case_logger("test_transparent_object_falls_back_to_other_sprite_candidate")
    incoming_transparent = await sample(
        dut,
        existing_color=2,
        existing_x=16,
        existing_selection_rank=0,
        incoming_color=0,
        incoming_x=8,
        incoming_selection_rank=1,
    )
    existing_transparent = await sample(
        dut,
        existing_color=0,
        existing_x=8,
        existing_selection_rank=0,
        incoming_color=1,
        incoming_x=16,
        incoming_selection_rank=3,
    )
    require(logger, incoming_transparent, expected={"chosen_color": 2, "chosen_x": 16, "chosen_rank": 0, "mixed_source": 2})
    require(logger, existing_transparent, expected={"chosen_color": 1, "chosen_x": 16, "chosen_rank": 3, "mixed_source": 2})


@cocotb.test()
async def test_bg_over_obj_flag_and_bg_disable_follow_dmg_rules(dut):
    logger = case_logger("test_bg_over_obj_flag_and_bg_disable_follow_dmg_rules")
    blocked = await sample(
        dut,
        bg_color_idx=1,
        bg_enable=True,
        existing_color=3,
        existing_bg_over_obj=True,
        existing_x=20,
        existing_selection_rank=0,
    )
    bg_disabled = await sample(
        dut,
        bg_color_idx=3,
        bg_enable=False,
        existing_color=1,
        existing_bg_over_obj=True,
        existing_x=20,
        existing_selection_rank=0,
    )
    require(logger, blocked, expected={"chosen_bg_over_obj": True, "mixed_shade": 1, "mixed_source": 0})
    require(logger, bg_disabled, expected={"chosen_bg_over_obj": True, "mixed_shade": 1, "mixed_source": 2})
