# top = sim::line_summary_test_top::line_summary_test_top
from __future__ import annotations

import cocotb
from cocotb.triggers import ReadOnly, Timer


RUN_DISABLED = 0
RUN_WARMUP = 1
RUN_RUNNING = 2

PHASE_LCD_OFF = 0
PHASE_OAM = 1
PHASE_TRANSFER = 2
PHASE_HBLANK = 3
PHASE_VBLANK = 4


def mix_hash(value: int, sample: int) -> int:
    return (((value << 5) ^ value ^ sample ^ 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF)


def option_u8_sample(value: int | None) -> int:
    return 0 if value is None else (0x100 | value)


def option_u6_sample(value: int | None) -> int:
    return 0 if value is None else (0x40 | value)


def expected_hash(
    *,
    ly: int,
    mode3_len: int,
    window_start_x: int | None,
    window_line_after: int,
    obj_count: int,
    selected_objs: list[int | None],
) -> int:
    value = mix_hash(0, ly)
    value = mix_hash(value, mode3_len)
    value = mix_hash(value, option_u8_sample(window_start_x))
    value = mix_hash(value, window_line_after)
    value = mix_hash(value, obj_count)
    for obj in selected_objs:
        value = mix_hash(value, option_u6_sample(obj))
    return value


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "summary_valid": bool(value & 0x1),
        "next_phase": (value >> 1) & 0x7,
        "next_ly": (value >> 4) & 0xFF,
        "mode3_len": (value >> 12) & 0x1FF,
        "window_start_valid": bool((value >> 21) & 0x1),
        "window_start_x": (value >> 22) & 0xFF,
        "window_line_after": (value >> 30) & 0xFF,
        "obj_count": (value >> 38) & 0xF,
        "slot0_valid": bool((value >> 42) & 0x1),
        "slot0_id": (value >> 43) & 0x3F,
        "slot1_valid": bool((value >> 49) & 0x1),
        "slot1_id": (value >> 50) & 0x3F,
        "line_hash": (value >> 56) & 0xFFFFFFFFFFFFFFFF,
    }


async def observe(dut) -> dict[str, int | bool]:
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


def drive_defaults(dut) -> None:
    dut.run_i.value = RUN_RUNNING
    dut.phase_i.value = PHASE_TRANSFER
    dut.ly_i.value = 0
    dut.dot_in_line_i.value = 255
    dut.wx_i.value = 7
    dut.window_active_i.value = 0
    dut.window_line_i.value = 0
    dut.line_obj_count_i.value = 0
    dut.slot0_i.value = 0
    dut.slot1_i.value = 0
    dut.x_out_i.value = 0
    dut.discard_scx_i.value = 0
    dut.first_frame_blank_i.value = 0


@cocotb.test()
async def test_transfer_to_hblank_emits_summary_with_window_and_obj_ids(dut):
    drive_defaults(dut)
    dut.run_i.value = RUN_RUNNING
    dut.phase_i.value = PHASE_TRANSFER
    dut.ly_i.value = 37
    dut.dot_in_line_i.value = 255
    dut.wx_i.value = 12
    dut.window_active_i.value = 1
    dut.window_line_i.value = 9
    dut.line_obj_count_i.value = 2
    dut.slot0_i.value = 3
    dut.slot1_i.value = 17

    snapshot = await observe(dut)
    assert snapshot["summary_valid"] is True
    assert snapshot["next_phase"] == PHASE_HBLANK
    assert snapshot["next_ly"] == 37
    assert snapshot["mode3_len"] == 176
    assert snapshot["window_start_valid"] is True
    assert snapshot["window_start_x"] == 5
    assert snapshot["window_line_after"] == 9
    assert snapshot["obj_count"] == 2
    assert snapshot["slot0_valid"] is True
    assert snapshot["slot0_id"] == 3
    assert snapshot["slot1_valid"] is True
    assert snapshot["slot1_id"] == 17
    assert snapshot["line_hash"] == expected_hash(
        ly=37,
        mode3_len=176,
        window_start_x=5,
        window_line_after=9,
        obj_count=2,
        selected_objs=[3, 17, None, None, None, None, None, None, None, None],
    )


@cocotb.test()
async def test_warmup_line0_uses_shorter_mode3_len(dut):
    drive_defaults(dut)
    dut.run_i.value = RUN_WARMUP
    dut.phase_i.value = PHASE_TRANSFER
    dut.ly_i.value = 0
    dut.dot_in_line_i.value = 243
    dut.first_frame_blank_i.value = 1

    snapshot = await observe(dut)
    assert snapshot["summary_valid"] is True
    assert snapshot["next_phase"] == PHASE_HBLANK
    assert snapshot["mode3_len"] == 160
    assert snapshot["window_start_valid"] is False
    assert snapshot["obj_count"] == 0
    assert snapshot["line_hash"] == expected_hash(
        ly=0,
        mode3_len=160,
        window_start_x=None,
        window_line_after=0,
        obj_count=0,
        selected_objs=[None, None, None, None, None, None, None, None, None, None],
    )


@cocotb.test()
async def test_non_boundary_transfer_step_emits_no_summary(dut):
    drive_defaults(dut)
    dut.phase_i.value = PHASE_TRANSFER
    dut.ly_i.value = 12
    dut.dot_in_line_i.value = 200

    snapshot = await observe(dut)
    assert snapshot["summary_valid"] is False
    assert snapshot["next_phase"] == PHASE_TRANSFER
