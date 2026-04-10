# top = ppu::rtl::oam_scan_test_top::oam_scan_test_top
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


SUITE_NAME = "test_oam_scan.py"


def case_logger(case_name: str) -> TestLogger:
    suite = TestLogger(suite_name=SUITE_NAME, stream=sys.stdout, color=False)
    suite.suite()
    return suite.bind_case(case_name)


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "req_y_addr": value & 0xFFFF,
        "req_x_addr": (value >> 16) & 0xFFFF,
        "req_y_id": (value >> 32) & 0xF,
        "req_x_id": (value >> 36) & 0xF,
        "overlap": bool((value >> 40) & 0x1),
        "selected": bool((value >> 41) & 0x1),
        "next_index": (value >> 42) & 0x3F,
        "next_found": (value >> 48) & 0xF,
        "next_count": (value >> 52) & 0xF,
        "ticket_oam_index": (value >> 56) & 0x3F,
        "ticket_x": (value >> 62) & 0xFF,
        "ticket_y": (value >> 70) & 0xFF,
        "ticket_rank": (value >> 78) & 0xF,
        "direct_overlap": bool((value >> 82) & 0x1),
        "base_req_y": bool((value >> 83) & 0x1),
        "base_req_x": bool((value >> 84) & 0x1),
        "slot0_oam_index": (value >> 85) & 0x3F,
        "slot0_rank": (value >> 91) & 0xF,
    }


async def sample(
    dut,
    *,
    ly: int,
    obj_y: int,
    obj_x: int,
    obj_size_8x16: bool,
    scan_index: int,
    found: int,
    count: int,
) -> dict[str, int | bool]:
    dut.ly_i.value = ly & 0xFF
    dut.obj_y_i.value = obj_y & 0xFF
    dut.obj_x_i.value = obj_x & 0xFF
    dut.obj_size_8x16_i.value = int(obj_size_8x16)
    dut.scan_index_i.value = scan_index & 0x3F
    dut.found_i.value = found & 0xF
    dut.count_i.value = count & 0xF
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
async def test_oam_scan_requests_current_entry_y_and_x_bytes(dut):
    logger = case_logger("test_oam_scan_requests_current_entry_y_and_x_bytes")
    snapshot = await sample(dut, ly=0x00, obj_y=0x10, obj_x=0x20, obj_size_8x16=False, scan_index=5, found=0, count=0)
    require(
        logger,
        snapshot,
        expected={
            "req_y_addr": 0xFE14,
            "req_x_addr": 0xFE15,
            "req_y_id": 0,
            "req_x_id": 1,
            "next_index": 6,
            "base_req_y": False,
            "base_req_x": False,
        },
    )


@cocotb.test()
async def test_oam_scan_selects_by_y_overlap_only_and_counts_hidden_x_objects(dut):
    logger = case_logger("test_oam_scan_selects_by_y_overlap_only_and_counts_hidden_x_objects")

    hidden_left = await sample(dut, ly=0x00, obj_y=0x10, obj_x=0x00, obj_size_8x16=False, scan_index=2, found=0, count=0)
    require(
        logger,
        hidden_left,
        expected={
            "overlap": True,
            "selected": True,
            "next_found": 1,
            "next_count": 1,
            "ticket_oam_index": 2,
            "ticket_x": 0x00,
            "ticket_y": 0x10,
            "ticket_rank": 0,
        },
    )

    hidden_right = await sample(dut, ly=0x00, obj_y=0x10, obj_x=0xA8, obj_size_8x16=False, scan_index=3, found=1, count=1)
    require(
        logger,
        hidden_right,
        expected={
            "overlap": True,
            "selected": True,
            "next_found": 2,
            "next_count": 2,
            "ticket_oam_index": 3,
            "ticket_x": 0xA8,
            "ticket_rank": 1,
            "slot0_oam_index": 0,
            "slot0_rank": 0,
        },
    )


@cocotb.test()
async def test_oam_scan_respects_8x16_height_and_ten_object_cap(dut):
    logger = case_logger("test_oam_scan_respects_8x16_height_and_ten_object_cap")

    tall_overlap = await sample(dut, ly=0x0F, obj_y=0x10, obj_x=0x44, obj_size_8x16=True, scan_index=9, found=9, count=9)
    require(
        logger,
        tall_overlap,
        expected={
            "overlap": True,
            "direct_overlap": True,
            "selected": True,
            "next_found": 10,
            "next_count": 10,
            "ticket_oam_index": 9,
            "ticket_rank": 9,
        },
    )

    saturated = await sample(dut, ly=0x0F, obj_y=0x10, obj_x=0x55, obj_size_8x16=True, scan_index=10, found=10, count=10)
    require(
        logger,
        saturated,
        expected={
            "overlap": True,
            "selected": False,
            "next_found": 10,
            "next_count": 10,
            "ticket_oam_index": 9,
            "ticket_rank": 9,
        },
    )


@cocotb.test()
async def test_x_hidden_sprites_still_count_toward_ten_limit(dut):
    logger = case_logger("test_x_hidden_sprites_still_count_toward_ten_limit")

    xs = [0x00, 0xA8, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40, 0x48, 0x50, 0x58]
    found = 0
    count = 0
    selected_ids: list[int] = []
    selected_ranks: list[int] = []

    for scan_index, obj_x in enumerate(xs):
        snapshot = await sample(
            dut,
            ly=0x18,
            obj_y=0x28,
            obj_x=obj_x,
            obj_size_8x16=False,
            scan_index=scan_index,
            found=found,
            count=count,
        )
        should_select = scan_index < 10
        require(
            logger,
            snapshot,
            expected={
                "overlap": True,
                "selected": should_select,
                "next_found": min(scan_index + 1, 10),
                "next_count": min(scan_index + 1, 10),
            },
        )
        if should_select:
            selected_ids.append(int(snapshot["ticket_oam_index"]))
            selected_ranks.append(int(snapshot["ticket_rank"]))
            require(
                logger,
                snapshot,
                expected={
                    "ticket_oam_index": scan_index,
                    "ticket_rank": scan_index,
                },
            )
        found = int(snapshot["next_found"])
        count = int(snapshot["next_count"])

    assert selected_ids == list(range(10)), selected_ids
    assert selected_ranks == list(range(10)), selected_ranks


@cocotb.test()
async def test_oam_scan_rejects_non_overlapping_entries_and_stops_at_done(dut):
    logger = case_logger("test_oam_scan_rejects_non_overlapping_entries_and_stops_at_done")

    miss = await sample(dut, ly=0x20, obj_y=0x10, obj_x=0x66, obj_size_8x16=False, scan_index=7, found=2, count=2)
    require(
        logger,
        miss,
        expected={
            "overlap": False,
            "direct_overlap": False,
            "selected": False,
            "next_index": 8,
            "next_found": 2,
            "next_count": 2,
            "ticket_oam_index": 0,
            "ticket_rank": 0,
        },
    )

    done = await sample(dut, ly=0x00, obj_y=0x10, obj_x=0x20, obj_size_8x16=False, scan_index=40, found=4, count=4)
    require(
        logger,
        done,
        expected={
            "selected": False,
            "overlap": False,
            "next_index": 40,
            "next_found": 4,
            "next_count": 4,
            "req_y_addr": 0x0000,
            "req_x_addr": 0x0000,
        },
    )
