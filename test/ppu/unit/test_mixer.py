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
    }


async def sample(
    dut,
    *,
    color_idx: int,
    bgp_pop: int,
    bg_enable: bool = True,
    pixel_valid: bool = True,
    x: int = 12,
    y: int = 34,
) -> dict[str, int | bool]:
    dut.color_idx_i.value = color_idx & 0x3
    dut.bgp_pop_i.value = bgp_pop & 0xFF
    dut.bg_enable_i.value = int(bg_enable)
    dut.pixel_valid_i.value = int(pixel_valid)
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
        snapshot = await sample(dut, color_idx=color_idx, bgp_pop=bgp_pop)
        require(logger, snapshot, expected={"lookup_shade": expected, "mixed_shade": expected})


@cocotb.test()
async def test_bg_disable_forces_white_but_preserves_background_source(dut):
    logger = case_logger("test_bg_disable_forces_white_but_preserves_background_source")
    snapshot = await sample(dut, color_idx=3, bgp_pop=0xE4, bg_enable=False, x=55, y=66)
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
    snapshot = await sample(dut, color_idx=2, bgp_pop=0x1B, pixel_valid=False)
    require(
        logger,
        snapshot,
        expected={
            "lookup_shade": 1,
            "event_valid": False,
            "event_matches_mix": False,
        },
    )
