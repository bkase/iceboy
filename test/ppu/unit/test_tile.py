# top = ppu::rtl::tile_test_top::tile_test_top
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


SUITE_NAME = "test_tile.py"


def case_logger(case_name: str) -> TestLogger:
    suite = TestLogger(suite_name=SUITE_NAME, stream=sys.stdout, color=False)
    suite.suite()
    return suite.bind_case(case_name)


def decode_output(value: int) -> dict[str, int]:
    return {
        "decoded": value & 0xFFFF,
        "flipped": (value >> 16) & 0xFFFF,
        "bg_addr": (value >> 32) & 0xFFFF,
        "y_flipped": (value >> 48) & 0xF,
        "obj_addr": (value >> 52) & 0xFFFF,
    }


def pack_row(row: list[int]) -> int:
    value = 0
    for index, pixel in enumerate(row):
        value |= (pixel & 0x3) << (index * 2)
    return value


async def sample(
    dut,
    *,
    lo: int,
    hi: int,
    bgwin_data_hi: bool,
    tile_id: int,
    row: int,
    obj_size: bool,
    x_flip: bool = False,
    y_flip: bool = False,
) -> dict[str, int]:
    dut.lo_i.value = lo & 0xFF
    dut.hi_i.value = hi & 0xFF
    dut.bgwin_data_hi_i.value = int(bgwin_data_hi)
    dut.tile_id_i.value = tile_id & 0xFF
    dut.row_i.value = row & 0xF
    dut.obj_size_i.value = int(obj_size)
    dut.x_flip_i.value = int(x_flip)
    dut.y_flip_i.value = int(y_flip)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


def require(logger: TestLogger, snapshot: dict[str, int], *, expected: dict[str, int]) -> None:
    for field, value in expected.items():
        assert logger.check(field, expected=value, actual=snapshot[field]), (
            f"{field} mismatch: expected={value} actual={snapshot[field]} snapshot={snapshot}"
        )


@cocotb.test()
async def test_decode_tile_row_patterns(dut):
    logger = case_logger("test_decode_tile_row_patterns")
    cases = [
        ("center_gradient", 0x3C, 0x7E, [0, 2, 3, 3, 3, 3, 2, 0]),
        ("all_zero", 0x00, 0x00, [0, 0, 0, 0, 0, 0, 0, 0]),
        ("all_one", 0xFF, 0xFF, [3, 3, 3, 3, 3, 3, 3, 3]),
        ("checkerboard", 0xAA, 0x55, [1, 2, 1, 2, 1, 2, 1, 2]),
    ]
    for label, lo, hi, expected_row in cases:
        logger.step(f"[{label}] Decode lo=0x{lo:02X} hi=0x{hi:02X}")
        snapshot = await sample(dut, lo=lo, hi=hi, bgwin_data_hi=True, tile_id=0x00, row=0, obj_size=False)
        require(logger, snapshot, expected={"decoded": pack_row(expected_row)})


@cocotb.test()
async def test_bg_tile_addressing_unsigned_and_signed(dut):
    logger = case_logger("test_bg_tile_addressing_unsigned_and_signed")

    logger.step("Unsigned $8000 method with tile_id=0x00 row=0")
    base_unsigned = await sample(dut, lo=0, hi=0, bgwin_data_hi=True, tile_id=0x00, row=0, obj_size=False)
    require(logger, base_unsigned, expected={"bg_addr": 0x8000})

    logger.step("Unsigned $8000 method with tile_id=0xFF row=7")
    max_unsigned = await sample(dut, lo=0, hi=0, bgwin_data_hi=True, tile_id=0xFF, row=7, obj_size=False)
    require(logger, max_unsigned, expected={"bg_addr": 0x8FFE})

    logger.step("Signed $8800 method with tile_id=0x00 row=0")
    zero_signed = await sample(dut, lo=0, hi=0, bgwin_data_hi=False, tile_id=0x00, row=0, obj_size=False)
    require(logger, zero_signed, expected={"bg_addr": 0x9000})

    logger.step("Signed $8800 method with tile_id=0x80 row=0")
    neg128_signed = await sample(dut, lo=0, hi=0, bgwin_data_hi=False, tile_id=0x80, row=0, obj_size=False)
    require(logger, neg128_signed, expected={"bg_addr": 0x8800})

    logger.step("Signed $8800 method with tile_id=0x7F row=7")
    pos127_signed = await sample(dut, lo=0, hi=0, bgwin_data_hi=False, tile_id=0x7F, row=7, obj_size=False)
    require(logger, pos127_signed, expected={"bg_addr": 0x97FE})


@cocotb.test()
async def test_obj_tile_addressing_and_y_flip(dut):
    logger = case_logger("test_obj_tile_addressing_and_y_flip")

    logger.step("8x8 object uses unsigned $8000 addressing")
    obj_8x8 = await sample(dut, lo=0, hi=0, bgwin_data_hi=True, tile_id=0x24, row=3, obj_size=False)
    require(logger, obj_8x8, expected={"obj_addr": 0x8246, "y_flipped": 4})

    logger.step("8x16 object ignores low tile_id bit for top half")
    obj_8x16_top = await sample(dut, lo=0, hi=0, bgwin_data_hi=True, tile_id=0x01, row=0, obj_size=True)
    require(logger, obj_8x16_top, expected={"obj_addr": 0x8000, "y_flipped": 15})

    logger.step("8x16 object selects the paired tile for the bottom half")
    obj_8x16_bottom = await sample(dut, lo=0, hi=0, bgwin_data_hi=True, tile_id=0x01, row=8, obj_size=True)
    require(logger, obj_8x16_bottom, expected={"obj_addr": 0x8010, "y_flipped": 7})

    logger.step("Y flip in 8x8 mirrors within the single tile")
    obj_8x8_yflip = await sample(
        dut,
        lo=0,
        hi=0,
        bgwin_data_hi=True,
        tile_id=0x24,
        row=0,
        obj_size=False,
        y_flip=True,
    )
    require(logger, obj_8x8_yflip, expected={"obj_addr": 0x824E, "y_flipped": 7})


@cocotb.test()
async def test_x_flip_reverses_pixel_order(dut):
    logger = case_logger("test_x_flip_reverses_pixel_order")
    row = [0, 1, 2, 3, 0, 0, 0, 0]
    logger.step("Reverse [0,1,2,3,0,0,0,0] with x_flip")
    snapshot = await sample(
        dut,
        lo=0x50,
        hi=0x30,
        bgwin_data_hi=True,
        tile_id=0x00,
        row=0,
        obj_size=False,
        x_flip=True,
    )
    require(
        logger,
        snapshot,
        expected={
            "decoded": pack_row(row),
            "flipped": pack_row([0, 0, 0, 0, 3, 2, 1, 0]),
        },
    )
