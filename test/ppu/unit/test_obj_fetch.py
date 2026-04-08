# top = ppu::rtl::obj_fetch_test_top::obj_fetch_test_top
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


SUITE_NAME = "test_obj_fetch.py"


def case_logger(case_name: str) -> TestLogger:
    suite = TestLogger(suite_name=SUITE_NAME, stream=sys.stdout, color=False)
    suite.suite()
    return suite.bind_case(case_name)


def pack_colors(colors: list[int]) -> int:
    value = 0
    for index, color in enumerate(colors[:16]):
        value |= (color & 0x3) << (index * 2)
    return value


def unpack_colors(value: int, *, width: int) -> list[int]:
    return [(value >> (index * 2)) & 0x3 for index in range(width)]


def decode_output(value: int) -> dict[str, int | bool | list[int]]:
    return {
        "tile_req_addr": value & 0xFFFF,
        "flags_req_addr": (value >> 16) & 0xFFFF,
        "lo_req_addr": (value >> 32) & 0xFFFF,
        "hi_req_addr": (value >> 48) & 0xFFFF,
        "row_index": (value >> 64) & 0xF,
        "tile": (value >> 68) & 0xFF,
        "y_flip": bool((value >> 76) & 0x1),
        "x_flip": bool((value >> 77) & 0x1),
        "palette": (value >> 78) & 0x1,
        "bg_over_obj": bool((value >> 79) & 0x1),
        "offset": (value >> 80) & 0xF,
        "left_clip": (value >> 84) & 0xF,
        "row_colors": unpack_colors((value >> 88) & 0xFFFF, width=8),
        "fifo_count": (value >> 104) & 0x1F,
        "fifo_colors": unpack_colors((value >> 109) & 0xFFFF_FFFF, width=16),
        "cancel_epoch": (value >> 141) & 0xF,
        "cancel_pending_valid": bool((value >> 145) & 0x1),
    }


async def sample(
    dut,
    *,
    oam_index: int,
    x: int,
    y: int,
    selection_rank: int,
    visible_ly: int,
    obj_size_8x16: bool,
    tile_id: int,
    flags_byte: int,
    tile_lo: int,
    tile_hi: int,
    x_out: int,
    fifo_count: int = 0,
    fifo_colors: list[int] | None = None,
    epoch: int = 0,
    pending_valid: bool = False,
    pending_id: int = 0,
    pending_epoch: int = 0,
) -> dict[str, int | bool | list[int]]:
    dut.oam_index_i.value = oam_index & 0x3F
    dut.x_i.value = x & 0xFF
    dut.y_i.value = y & 0xFF
    dut.selection_rank_i.value = selection_rank & 0xF
    dut.visible_ly_i.value = visible_ly & 0xFF
    dut.obj_size_8x16_i.value = int(obj_size_8x16)
    dut.tile_id_i.value = tile_id & 0xFF
    dut.flags_byte_i.value = flags_byte & 0xFF
    dut.tile_lo_i.value = tile_lo & 0xFF
    dut.tile_hi_i.value = tile_hi & 0xFF
    dut.x_out_i.value = x_out & 0xFF
    dut.fifo_count_i.value = fifo_count & 0x1F
    dut.fifo_colors_i.value = pack_colors(fifo_colors or [0] * 16)
    dut.epoch_i.value = epoch & 0xF
    dut.pending_valid_i.value = int(pending_valid)
    dut.pending_id_i.value = pending_id & 0xF
    dut.pending_epoch_i.value = pending_epoch & 0xF
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


def require(logger: TestLogger, snapshot: dict[str, int | bool | list[int]], *, expected: dict[str, int | bool | list[int]]) -> None:
    for field, value in expected.items():
        assert logger.check(field, expected=value, actual=snapshot[field]), (
            f"{field} mismatch: expected={value} actual={snapshot[field]} snapshot={snapshot}"
        )


@cocotb.test()
async def test_object_fetch_builds_oam_and_vram_requests_and_resolves_meta(dut):
    logger = case_logger("test_object_fetch_builds_oam_and_vram_requests_and_resolves_meta")
    logger.step("Resolve a flipped 8x16 object on the lower tile half")
    snapshot = await sample(
        dut,
        oam_index=3,
        x=24,
        y=32,
        selection_rank=2,
        visible_ly=24,
        obj_size_8x16=True,
        tile_id=0x21,
        flags_byte=0xF0,
        tile_lo=0x00,
        tile_hi=0x00,
        x_out=16,
    )
    require(
        logger,
        snapshot,
        expected={
            "tile_req_addr": 0xFE0E,
            "flags_req_addr": 0xFE0F,
            "lo_req_addr": 0x820E,
            "hi_req_addr": 0x820F,
            "row_index": 8,
            "tile": 0x21,
            "y_flip": True,
            "x_flip": True,
            "palette": 1,
            "bg_over_obj": True,
            "offset": 0,
            "left_clip": 0,
        },
    )


@cocotb.test()
async def test_object_decode_applies_xflip_and_only_overlays_transparent_fifo_slots(dut):
    logger = case_logger("test_object_decode_applies_xflip_and_only_overlays_transparent_fifo_slots")
    logger.step("Decode a sprite row, reverse it with X flip, and merge into transparent OBJ FIFO slots only")
    snapshot = await sample(
        dut,
        oam_index=0,
        x=20,
        y=16,
        selection_rank=1,
        visible_ly=0,
        obj_size_8x16=False,
        tile_id=0x08,
        flags_byte=0x20,
        tile_lo=0x50,
        tile_hi=0x30,
        x_out=8,
        fifo_count=4,
        fifo_colors=[0, 1, 0, 2] + [0] * 12,
    )
    require(
        logger,
        snapshot,
        expected={
            "row_colors": [0, 0, 0, 0, 3, 2, 1, 0],
            "left_clip": 0,
            "fifo_count": 12,
            "fifo_colors": [0, 1, 0, 2, 0, 0, 0, 0, 3, 2, 1, 0] + [0] * 4,
        },
    )


@cocotb.test()
async def test_object_fetch_cancel_bumps_epoch_and_clears_pending_state(dut):
    logger = case_logger("test_object_fetch_cancel_bumps_epoch_and_clears_pending_state")
    logger.step("Cancel an in-flight object fetch and verify epoch bump plus pending clear")
    snapshot = await sample(
        dut,
        oam_index=1,
        x=8,
        y=16,
        selection_rank=0,
        visible_ly=0,
        obj_size_8x16=False,
        tile_id=0,
        flags_byte=0,
        tile_lo=0,
        tile_hi=0,
        x_out=0,
        epoch=5,
        pending_valid=True,
        pending_id=3,
        pending_epoch=5,
    )
    require(logger, snapshot, expected={"cancel_epoch": 6, "cancel_pending_valid": False})


@cocotb.test()
async def test_object_fetch_8x8_yflip_mirrors_row_and_selects_obp0(dut):
    logger = case_logger("test_object_fetch_8x8_yflip_mirrors_row_and_selects_obp0")
    logger.step("Resolve an 8x8 sprite on LY=0 with Y flip set so row 0 maps to row 7")
    snapshot = await sample(
        dut,
        oam_index=2,
        x=32,
        y=16,
        selection_rank=0,
        visible_ly=0,
        obj_size_8x16=False,
        tile_id=0x24,
        flags_byte=0x40,
        tile_lo=0x00,
        tile_hi=0x00,
        x_out=24,
    )
    require(
        logger,
        snapshot,
        expected={
            "row_index": 0,
            "lo_req_addr": 0x824E,
            "hi_req_addr": 0x824F,
            "y_flip": True,
            "x_flip": False,
            "palette": 0,
            "bg_over_obj": False,
            "offset": 0,
            "left_clip": 0,
        },
    )


@cocotb.test()
async def test_object_overlay_preserves_earlier_opaque_pixels_on_overlap(dut):
    logger = case_logger("test_object_overlay_preserves_earlier_opaque_pixels_on_overlap")
    logger.step("Overlay an incoming sprite row onto already-opaque OBJ FIFO slots and keep the earlier opaque pixels")
    snapshot = await sample(
        dut,
        oam_index=4,
        x=16,
        y=16,
        selection_rank=3,
        visible_ly=0,
        obj_size_8x16=False,
        tile_id=0x08,
        flags_byte=0x00,
        tile_lo=0x50,
        tile_hi=0x30,
        x_out=8,
        fifo_count=8,
        fifo_colors=[2, 0, 1, 0, 0, 0, 0, 0] + [0] * 8,
    )
    require(
        logger,
        snapshot,
        expected={
            "offset": 0,
            "left_clip": 0,
            "row_colors": [0, 1, 2, 3, 0, 0, 0, 0],
            "fifo_count": 8,
            "fifo_colors": [2, 1, 1, 3, 0, 0, 0, 0] + [0] * 8,
        },
    )


@cocotb.test()
async def test_object_at_x0_is_fetched_but_fully_clipped_from_fifo(dut):
    logger = case_logger("test_object_at_x0_is_fetched_but_fully_clipped_from_fifo")
    logger.step("Fetch a sprite at X=0 and verify it issues memory requests but contributes no visible OBJ FIFO pixels")
    snapshot = await sample(
        dut,
        oam_index=5,
        x=0,
        y=16,
        selection_rank=4,
        visible_ly=0,
        obj_size_8x16=False,
        tile_id=0x10,
        flags_byte=0x00,
        tile_lo=0xFF,
        tile_hi=0x00,
        x_out=0,
        fifo_count=0,
    )
    require(
        logger,
        snapshot,
        expected={
            "tile_req_addr": 0xFE16,
            "flags_req_addr": 0xFE17,
            "offset": 0,
            "left_clip": 8,
            "fifo_count": 0,
            "fifo_colors": [0] * 16,
        },
    )


@cocotb.test()
async def test_lcd_disable_cancel_matches_window_cancel_semantics(dut):
    logger = case_logger("test_lcd_disable_cancel_matches_window_cancel_semantics")
    logger.step("Use the same cancel helper semantics for LCD disable and verify the pending state is abandoned")
    snapshot = await sample(
        dut,
        oam_index=1,
        x=12,
        y=16,
        selection_rank=0,
        visible_ly=0,
        obj_size_8x16=False,
        tile_id=0,
        flags_byte=0,
        tile_lo=0,
        tile_hi=0,
        x_out=8,
        epoch=9,
        pending_valid=True,
        pending_id=2,
        pending_epoch=9,
    )
    require(logger, snapshot, expected={"cancel_epoch": 10, "cancel_pending_valid": False})
