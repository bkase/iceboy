# top = ppu::rtl::fetcher_test_top::fetcher_test_top
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


SOURCE_BG = 0
SOURCE_WINDOW = 1

STEP_GET_TILE = 0
STEP_GET_LO = 1
STEP_GET_HI = 2
STEP_SLEEP = 3
STEP_PUSH = 4

MODE_ACTIVE = 0
MODE_START_BG = 1

SUITE_NAME = "test_bg_fetcher.py"


def case_logger(case_name: str) -> TestLogger:
    suite = TestLogger(suite_name=SUITE_NAME, stream=sys.stdout, color=False)
    suite.suite()
    return suite.bind_case(case_name)


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "req_addr": value & 0xFFFF,
        "req_valid": bool((value >> 16) & 0x1),
        "req_id": (value >> 17) & 0xF,
        "epoch": (value >> 21) & 0xF,
        "source": (value >> 25) & 0x3,
        "step": (value >> 27) & 0x7,
        "tile_id": (value >> 30) & 0xFF,
        "tile_lo": (value >> 38) & 0xFF,
        "tile_hi": (value >> 46) & 0xFF,
        "map_x": (value >> 54) & 0x1F,
        "map_y": (value >> 59) & 0x1F,
        "row": (value >> 64) & 0x7,
        "pending_push": bool((value >> 67) & 0x1),
        "pending_valid": bool((value >> 68) & 0x1),
        "pending_id": (value >> 69) & 0xF,
        "pending_epoch": (value >> 73) & 0xF,
        "push_valid": bool((value >> 77) & 0x1),
        "stale_resp": bool((value >> 78) & 0x1),
        "push_row": (value >> 79) & 0xFFFF,
    }


def pack_row(row: list[int]) -> int:
    value = 0
    for index, pixel in enumerate(row):
        value |= (pixel & 0x3) << (index * 2)
    return value


async def sample(
    dut,
    *,
    mode: int = MODE_ACTIVE,
    bg_map_hi: bool = False,
    win_map_hi: bool = False,
    bgwin_data_hi: bool = True,
    scx_fetch: int = 0,
    scy_fetch: int = 0,
    visible_ly: int = 0,
    tile_x: int = 0,
    window_line: int = 0,
    epoch: int = 0,
    source: int = SOURCE_BG,
    step: int = STEP_GET_TILE,
    tile_id: int = 0,
    tile_lo: int = 0,
    tile_hi: int = 0,
    map_x: int = 0,
    map_y: int = 0,
    row: int = 0,
    pending_push: bool = False,
    pending_valid: bool = False,
    pending_id: int = 0,
    pending_epoch: int = 0,
    fifo_has_room: bool = True,
    resp_valid: bool = False,
    resp_id: int = 0,
    resp_data: int = 0,
    restart_line: bool = False,
    window_restart: bool = False,
    fetch_cancel: bool = False,
    lcd_disable: bool = False,
) -> dict[str, int | bool]:
    dut.mode_i.value = mode & 0x3
    dut.bg_map_hi_i.value = int(bg_map_hi)
    dut.win_map_hi_i.value = int(win_map_hi)
    dut.bgwin_data_hi_i.value = int(bgwin_data_hi)
    dut.scx_fetch_i.value = scx_fetch & 0xFF
    dut.scy_fetch_i.value = scy_fetch & 0xFF
    dut.visible_ly_i.value = visible_ly & 0xFF
    dut.tile_x_i.value = tile_x & 0x1F
    dut.window_line_i.value = window_line & 0xFF
    dut.epoch_i.value = epoch & 0xF
    dut.source_i.value = source & 0x3
    dut.step_i.value = step & 0x7
    dut.tile_id_i.value = tile_id & 0xFF
    dut.tile_lo_i.value = tile_lo & 0xFF
    dut.tile_hi_i.value = tile_hi & 0xFF
    dut.map_x_i.value = map_x & 0x1F
    dut.map_y_i.value = map_y & 0x1F
    dut.row_i.value = row & 0x7
    dut.pending_push_i.value = int(pending_push)
    dut.pending_valid_i.value = int(pending_valid)
    dut.pending_id_i.value = pending_id & 0xF
    dut.pending_epoch_i.value = pending_epoch & 0xF
    dut.fifo_has_room_i.value = int(fifo_has_room)
    dut.resp_valid_i.value = int(resp_valid)
    dut.resp_id_i.value = resp_id & 0xF
    dut.resp_data_i.value = resp_data & 0xFF
    dut.restart_line_i.value = int(restart_line)
    dut.window_restart_i.value = int(window_restart)
    dut.fetch_cancel_i.value = int(fetch_cancel)
    dut.lcd_disable_i.value = int(lcd_disable)
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
async def test_start_bg_fetcher_uses_sampled_scx_scy_for_tilemap_read(dut):
    logger = case_logger("test_start_bg_fetcher_uses_sampled_scx_scy_for_tilemap_read")
    logger.step("Seed a background fetch with SCX[7:3]=3, SCY+LY=0x18, tile_x=2")
    snapshot = await sample(
        dut,
        mode=MODE_START_BG,
        bg_map_hi=False,
        scx_fetch=0x18,
        scy_fetch=0x10,
        visible_ly=0x08,
        tile_x=0x02,
    )
    require(
        logger,
        snapshot,
        expected={
            "req_valid": True,
            "req_id": 0,
            "req_addr": 0x9865,
            "source": SOURCE_BG,
            "step": STEP_GET_TILE,
            "map_x": 5,
            "map_y": 3,
            "row": 0,
            "pending_valid": True,
            "pending_id": 0,
            "pending_epoch": 0,
        },
    )


@cocotb.test()
async def test_fetch_sequence_progresses_through_sleep_and_push_stall(dut):
    logger = case_logger("test_fetch_sequence_progresses_through_sleep_and_push_stall")

    logger.step("Accept a tile-id response and advance to GetLo")
    get_lo = await sample(
        dut,
        epoch=2,
        step=STEP_GET_TILE,
        pending_valid=True,
        pending_id=0,
        pending_epoch=2,
        resp_valid=True,
        resp_id=0,
        resp_data=0x83,
    )
    require(logger, get_lo, expected={"step": STEP_GET_LO, "tile_id": 0x83, "pending_valid": False})

    logger.step("Issue the low-byte read using signed tile addressing")
    low_req = await sample(
        dut,
        bgwin_data_hi=False,
        epoch=2,
        step=STEP_GET_LO,
        tile_id=0x83,
        row=0x05,
    )
    require(
        logger,
        low_req,
        expected={"req_valid": True, "req_id": 1, "req_addr": 0x883A, "pending_valid": True, "pending_id": 1},
    )

    logger.step("Accept low/high responses, then stall at push until FIFO has room")
    get_hi = await sample(
        dut,
        epoch=2,
        step=STEP_GET_LO,
        tile_id=0x20,
        row=0x03,
        pending_valid=True,
        pending_id=1,
        pending_epoch=2,
        resp_valid=True,
        resp_id=1,
        resp_data=0x55,
    )
    require(logger, get_hi, expected={"step": STEP_GET_HI, "tile_lo": 0x55})

    sleep_state = await sample(
        dut,
        epoch=2,
        step=STEP_GET_HI,
        tile_id=0x20,
        tile_lo=0x55,
        row=0x03,
        pending_valid=True,
        pending_id=2,
        pending_epoch=2,
        resp_valid=True,
        resp_id=2,
        resp_data=0x33,
    )
    require(logger, sleep_state, expected={"step": STEP_SLEEP, "tile_hi": 0x33, "pending_push": True})

    push_state = await sample(
        dut,
        epoch=2,
        step=STEP_SLEEP,
        tile_id=0x20,
        tile_lo=0x55,
        tile_hi=0x33,
        row=0x03,
        pending_push=True,
    )
    require(logger, push_state, expected={"step": STEP_PUSH, "pending_push": True, "push_valid": False})

    stalled = await sample(
        dut,
        epoch=2,
        step=STEP_PUSH,
        tile_lo=0x55,
        tile_hi=0x33,
        map_x=7,
        row=0x03,
        pending_push=True,
        fifo_has_room=False,
    )
    require(logger, stalled, expected={"step": STEP_PUSH, "pending_push": True, "push_valid": False, "map_x": 7})

    pushed = await sample(
        dut,
        epoch=2,
        step=STEP_PUSH,
        tile_lo=0x55,
        tile_hi=0x33,
        map_x=7,
        row=0x03,
        pending_push=True,
        fifo_has_room=True,
    )
    require(
        logger,
        pushed,
        expected={
            "step": STEP_GET_TILE,
            "map_x": 8,
            "pending_push": False,
            "push_valid": True,
            "push_row": pack_row([0, 1, 2, 3, 0, 1, 2, 3]),
        },
    )


@cocotb.test()
async def test_epoch_bumps_on_window_restart_and_fetch_cancel(dut):
    logger = case_logger("test_epoch_bumps_on_window_restart_and_fetch_cancel")

    logger.step("Window restart increments epoch and retargets the fetcher to the window tilemap seed")
    window = await sample(
        dut,
        epoch=3,
        source=SOURCE_BG,
        step=STEP_GET_LO,
        tile_id=0x42,
        tile_lo=0x11,
        map_x=9,
        map_y=4,
        row=2,
        pending_valid=True,
        pending_id=1,
        pending_epoch=3,
        window_restart=True,
        window_line=0x09,
    )
    require(
        logger,
        window,
        expected={
            "epoch": 4,
            "source": SOURCE_WINDOW,
            "step": STEP_GET_TILE,
            "map_x": 0,
            "map_y": 1,
            "row": 1,
            "pending_valid": False,
            "req_valid": False,
        },
    )

    logger.step("Fetch cancel also bumps epoch and reseeds background coordinates")
    canceled = await sample(
        dut,
        epoch=4,
        source=SOURCE_WINDOW,
        step=STEP_GET_HI,
        scx_fetch=0x20,
        scy_fetch=0x18,
        visible_ly=0x04,
        tile_x=0x03,
        map_x=1,
        map_y=1,
        row=1,
        fetch_cancel=True,
    )
    require(
        logger,
        canceled,
        expected={
            "epoch": 5,
            "source": SOURCE_BG,
            "step": STEP_GET_TILE,
            "map_x": 7,
            "map_y": 3,
            "row": 4,
            "pending_valid": False,
        },
    )


@cocotb.test()
async def test_stale_response_discard_and_disable_quiesce_fetcher(dut):
    logger = case_logger("test_stale_response_discard_and_disable_quiesce_fetcher")

    logger.step("Reject an old response whose pending epoch no longer matches the fetcher epoch")
    stale = await sample(
        dut,
        epoch=4,
        step=STEP_GET_HI,
        tile_id=0x22,
        tile_lo=0xC3,
        pending_valid=False,
        pending_id=2,
        pending_epoch=3,
        resp_valid=True,
        resp_id=2,
        resp_data=0x99,
    )
    require(logger, stale, expected={"stale_resp": True, "step": STEP_GET_HI, "tile_hi": 0x00, "push_valid": False})

    logger.step("LCD disable increments epoch and returns the fetcher to a quiescent GetTile seed")
    disabled = await sample(
        dut,
        epoch=9,
        step=STEP_GET_LO,
        scx_fetch=0x28,
        scy_fetch=0x04,
        visible_ly=0x02,
        tile_x=0x01,
        lcd_disable=True,
    )
    require(
        logger,
        disabled,
        expected={
            "epoch": 10,
            "source": SOURCE_BG,
            "step": STEP_GET_TILE,
            "map_x": 6,
            "map_y": 0,
            "row": 6,
            "pending_valid": False,
            "req_valid": False,
        },
    )
