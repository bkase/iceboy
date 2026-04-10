# top = ppu::rtl::mixer_test_top::mixer_test_top
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


SUITE_NAME = "test_mixer.py"


def case_logger(case_name: str) -> TestLogger:
    suite = TestLogger(suite_name=SUITE_NAME, stream=sys.stdout, color=False)
    suite.suite()
    return suite.bind_case(case_name)


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "lookup_shade": value & 0x3,
        "bg_enabled": bool((value >> 2) & 0x1),
        "mixed_shade": (value >> 3) & 0x3,
        "x": (value >> 5) & 0xFF,
        "y": (value >> 13) & 0xFF,
        "source": (value >> 21) & 0x3,
        "event_matches_mix": bool((value >> 23) & 0x1),
        "event_valid": bool((value >> 24) & 0x1),
        "obj_color": (value >> 25) & 0x3,
        "bg_from_window": bool((value >> 27) & 0x1),
        "obj_bg_over_obj": bool((value >> 28) & 0x1),
        "obj_valid": bool((value >> 29) & 0x1),
        "obj_enabled": bool((value >> 30) & 0x1),
    }


async def sample(
    dut,
    *,
    bg_color_idx: int,
    bgp_pop: int,
    obp0_pop: int = 0xE4,
    obp1_pop: int = 0x1B,
    bg_enable: bool = True,
    obj_enable: bool = True,
    pixel_valid: bool = True,
    obj_valid: bool = False,
    obj_color: int = 0,
    obj_palette_sel: bool = False,
    obj_bg_over_obj: bool = False,
    obj_x: int = 20,
    obj_selection_rank: int = 0,
    bg_from_window: bool = False,
    x: int = 12,
    y: int = 34,
) -> dict[str, int | bool]:
    dut.bg_color_idx_i.value = bg_color_idx & 0x3
    dut.bg_from_window_i.value = int(bg_from_window)
    dut.bgp_pop_i.value = bgp_pop & 0xFF
    dut.obp0_pop_i.value = obp0_pop & 0xFF
    dut.obp1_pop_i.value = obp1_pop & 0xFF
    dut.bg_enable_i.value = int(bg_enable)
    dut.obj_enable_i.value = int(obj_enable)
    dut.pixel_valid_i.value = int(pixel_valid)
    dut.obj_valid_i.value = int(obj_valid)
    dut.obj_color_i.value = obj_color & 0x3
    dut.obj_palette_sel_i.value = int(obj_palette_sel)
    dut.obj_bg_over_obj_i.value = int(obj_bg_over_obj)
    dut.obj_x_i.value = obj_x & 0xFF
    dut.obj_selection_rank_i.value = obj_selection_rank & 0xF
    dut.x_i.value = x & 0xFF
    dut.y_i.value = y & 0xFF
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
async def test_palette_lookup_uses_late_bgp_value(dut):
    logger = case_logger("test_palette_lookup_uses_late_bgp_value")
    cases = [
        ("color0", 0, 0b11_10_01_00, 0),
        ("color1", 1, 0b11_10_01_00, 1),
        ("color2", 2, 0b11_10_01_00, 2),
        ("color3", 3, 0b11_10_01_00, 3),
        ("swapped", 2, 0b00_01_11_10, 1),
    ]
    for label, color_idx, bgp_pop, expected in cases:
        logger.step(f"[{label}] Apply BGP=0b{bgp_pop:08b} to color index {color_idx}")
        snapshot = await sample(dut, bg_color_idx=color_idx, bgp_pop=bgp_pop)
        require(logger, snapshot, expected={"lookup_shade": expected, "mixed_shade": expected})


@cocotb.test()
async def test_bg_disable_forces_white_but_preserves_background_source(dut):
    logger = case_logger("test_bg_disable_forces_white_but_preserves_background_source")
    snapshot = await sample(dut, bg_color_idx=3, bgp_pop=0xE4, bg_enable=False, x=55, y=66)
    require(
        logger,
        snapshot,
        expected={
            "bg_enabled": False,
            "mixed_shade": 0,
            "x": 55,
            "y": 66,
            "source": 0,
            "event_valid": True,
            "event_matches_mix": True,
        },
    )


@cocotb.test()
async def test_no_scanout_event_when_pixel_is_not_valid(dut):
    logger = case_logger("test_no_scanout_event_when_pixel_is_not_valid")
    snapshot = await sample(dut, bg_color_idx=2, bgp_pop=0x1B, pixel_valid=False)
    require(
        logger,
        snapshot,
        expected={
            "lookup_shade": 1,
            "event_valid": False,
            "event_matches_mix": False,
        },
    )


@cocotb.test()
async def test_window_pixels_preserve_window_source_when_no_object_wins(dut):
    logger = case_logger("test_window_pixels_preserve_window_source_when_no_object_wins")
    snapshot = await sample(dut, bg_color_idx=2, bgp_pop=0xE4, bg_from_window=True)
    require(logger, snapshot, expected={"mixed_shade": 2, "source": 1, "bg_from_window": True})


@cocotb.test()
async def test_opaque_object_uses_selected_obj_palette_when_bg_does_not_block(dut):
    logger = case_logger("test_opaque_object_uses_selected_obj_palette_when_bg_does_not_block")
    snapshot = await sample(
        dut,
        bg_color_idx=0,
        bgp_pop=0xE4,
        obj_valid=True,
        obj_color=2,
        obj_palette_sel=True,
        obp1_pop=0b00_01_11_10,
    )
    require(
        logger,
        snapshot,
        expected={
            "obj_valid": True,
            "obj_color": 2,
            "mixed_shade": 1,
            "source": 2,
            "event_valid": True,
            "event_matches_mix": True,
        },
    )


@cocotb.test()
async def test_obj_disable_blocks_queued_object_pixels(dut):
    logger = case_logger("test_obj_disable_blocks_queued_object_pixels")
    snapshot = await sample(
        dut,
        bg_color_idx=0,
        bgp_pop=0xE4,
        obj_enable=False,
        obj_valid=True,
        obj_color=3,
        obj_palette_sel=True,
        obp1_pop=0b00_01_11_10,
    )
    require(
        logger,
        snapshot,
        expected={
            "obj_enabled": False,
            "obj_valid": True,
            "mixed_shade": 0,
            "source": 0,
            "event_valid": True,
            "event_matches_mix": True,
        },
    )


@cocotb.test()
async def test_bg_over_obj_flag_defers_to_nonzero_bg_when_enabled(dut):
    logger = case_logger("test_bg_over_obj_flag_defers_to_nonzero_bg_when_enabled")
    snapshot = await sample(
        dut,
        bg_color_idx=1,
        bgp_pop=0xE4,
        obj_valid=True,
        obj_color=3,
        obj_bg_over_obj=True,
    )
    require(
        logger,
        snapshot,
        expected={
            "bg_enabled": True,
            "obj_bg_over_obj": True,
            "mixed_shade": 1,
            "source": 0,
        },
    )


@cocotb.test()
async def test_bg_disable_lets_object_render_even_with_bg_over_obj_flag(dut):
    logger = case_logger("test_bg_disable_lets_object_render_even_with_bg_over_obj_flag")
    snapshot = await sample(
        dut,
        bg_color_idx=3,
        bgp_pop=0xE4,
        bg_enable=False,
        obj_valid=True,
        obj_color=1,
        obj_bg_over_obj=True,
        obp0_pop=0b11_10_01_00,
    )
    require(
        logger,
        snapshot,
        expected={
            "bg_enabled": False,
            "mixed_shade": 1,
            "source": 2,
        },
    )


@cocotb.test()
async def test_transparent_object_falls_back_to_background_or_window(dut):
    logger = case_logger("test_transparent_object_falls_back_to_background_or_window")
    snapshot = await sample(
        dut,
        bg_color_idx=2,
        bgp_pop=0xE4,
        bg_from_window=True,
        obj_valid=True,
        obj_color=0,
        obj_palette_sel=False,
    )
    require(
        logger,
        snapshot,
        expected={
            "obj_valid": True,
            "obj_color": 0,
            "mixed_shade": 2,
            "source": 1,
        },
    )
