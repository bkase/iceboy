# top = video::frame_sink_test_top::frame_sink_test_top
from __future__ import annotations

import cocotb
from cocotb.triggers import ReadOnly, Timer


EVENT_FRAME_START = 0
EVENT_LINE_START = 1
EVENT_BLANK = 2
EVENT_PIXEL = 3

SOURCE_BG = 0
SOURCE_WINDOW = 1
SOURCE_OBJECT = 2

BLANK_LCD_DISABLED = 0
BLANK_WARMUP = 1
BLANK_NON_VISIBLE_LINE = 2
BLANK_NON_VISIBLE_DOT = 3


def mix_hash(value: int, sample: int) -> int:
    return (((value << 5) ^ value ^ sample ^ 0x9E3779B9) & 0xFFFFFFFF)


def pixel_sample(shade: int, source: int) -> int:
    return shade | (source << 2)


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "line_frame": value & 0xFFFFFFFF,
        "line_frame_started": bool((value >> 32) & 0x1),
        "line_y": (value >> 33) & 0xFF,
        "line_active": bool((value >> 41) & 0x1),
        "line_pixel_count": (value >> 42) & 0xFF,
        "line_blank_count": (value >> 50) & 0xFF,
        "line_hash": (value >> 58) & 0xFFFFFFFF,
        "line_first_diff_valid": bool((value >> 90) & 0x1),
        "line_first_diff_x": (value >> 91) & 0xFF,
        "line_expected_shade": (value >> 99) & 0x3,
        "line_actual_shade": (value >> 101) & 0x3,
        "line_expected_source": (value >> 103) & 0x3,
        "line_actual_source": (value >> 105) & 0x3,
        "frame_frame": (value >> 107) & 0xFFFFFFFF,
        "frame_started": bool((value >> 139) & 0x1),
        "frame_line_count": (value >> 140) & 0xFF,
        "frame_hash": (value >> 148) & 0xFFFFFFFF,
        "hash_sample_count": (value >> 180) & 0xFFFF,
        "hash_value": (value >> 196) & 0xFFFFFFFF,
        "diff_has_diff": bool((value >> 228) & 0x1),
        "diff_frame": (value >> 229) & 0xFFFFFFFF,
        "diff_line": (value >> 261) & 0xFF,
        "diff_x": (value >> 269) & 0xFF,
        "diff_expected_shade": (value >> 277) & 0x3,
        "diff_actual_shade": (value >> 279) & 0x3,
        "diff_expected_source": (value >> 281) & 0x3,
        "diff_actual_source": (value >> 283) & 0x3,
        "line_summary_valid": bool((value >> 285) & 0x1),
        "line_summary_frame": (value >> 286) & 0xFFFFFFFF,
        "line_summary_line": (value >> 318) & 0xFF,
        "line_summary_pixel_count": (value >> 326) & 0xFF,
        "line_summary_blank_count": (value >> 334) & 0xFF,
        "line_summary_hash": (value >> 342) & 0xFFFFFFFF,
        "line_summary_full_width": bool((value >> 374) & 0x1),
        "line_summary_first_diff_valid": bool((value >> 375) & 0x1),
        "line_summary_first_diff_x": (value >> 376) & 0xFF,
        "line_summary_expected_shade": (value >> 384) & 0x3,
        "line_summary_actual_shade": (value >> 386) & 0x3,
        "line_summary_expected_source": (value >> 388) & 0x3,
        "line_summary_actual_source": (value >> 390) & 0x3,
        "frame_summary_valid": bool((value >> 392) & 0x1),
        "frame_summary_frame": (value >> 393) & 0xFFFFFFFF,
        "frame_summary_line_count": (value >> 425) & 0xFF,
        "frame_summary_hash": (value >> 433) & 0xFFFFFFFF,
        "frame_summary_full_frame": bool((value >> 465) & 0x1),
    }


def initial_state() -> dict[str, int | bool]:
    return {
        "line_frame": 0,
        "line_frame_started": False,
        "line_y": 0,
        "line_active": False,
        "line_pixel_count": 0,
        "line_blank_count": 0,
        "line_hash": 0,
        "line_first_diff_valid": False,
        "line_first_diff_x": 0,
        "line_expected_shade": 0,
        "line_actual_shade": 0,
        "line_expected_source": SOURCE_BG,
        "line_actual_source": SOURCE_BG,
        "frame_frame": 0,
        "frame_started": False,
        "frame_line_count": 0,
        "frame_hash": 0,
        "hash_sample_count": 0,
        "hash_value": 0,
        "diff_has_diff": False,
        "diff_frame": 0,
        "diff_line": 0,
        "diff_x": 0,
        "diff_expected_shade": 0,
        "diff_actual_shade": 0,
        "diff_expected_source": SOURCE_BG,
        "diff_actual_source": SOURCE_BG,
    }


async def drive(
    dut,
    state: dict[str, int | bool],
    *,
    event_kind: int,
    x: int = 0,
    y: int = 0,
    shade: int = 0,
    source: int = SOURCE_BG,
    blank_reason: int = BLANK_LCD_DISABLED,
    ref_valid: bool = False,
    ref_shade: int = 0,
    ref_source: int = SOURCE_BG,
) -> dict[str, int | bool]:
    dut.line_frame_i.value = int(state["line_frame"])
    dut.line_frame_started_i.value = int(state["line_frame_started"])
    dut.line_y_i.value = int(state["line_y"])
    dut.line_active_i.value = int(state["line_active"])
    dut.line_pixel_count_i.value = int(state["line_pixel_count"])
    dut.line_blank_count_i.value = int(state["line_blank_count"])
    dut.line_hash_i.value = int(state["line_hash"])
    dut.line_first_diff_valid_i.value = int(state["line_first_diff_valid"])
    dut.line_first_diff_x_i.value = int(state["line_first_diff_x"])
    dut.line_expected_shade_i.value = int(state["line_expected_shade"])
    dut.line_actual_shade_i.value = int(state["line_actual_shade"])
    dut.line_expected_source_i.value = int(state["line_expected_source"])
    dut.line_actual_source_i.value = int(state["line_actual_source"])
    dut.frame_frame_i.value = int(state["frame_frame"])
    dut.frame_started_i.value = int(state["frame_started"])
    dut.frame_line_count_i.value = int(state["frame_line_count"])
    dut.frame_hash_i.value = int(state["frame_hash"])
    dut.hash_sample_count_i.value = int(state["hash_sample_count"])
    dut.hash_value_i.value = int(state["hash_value"])
    dut.diff_has_diff_i.value = int(state["diff_has_diff"])
    dut.diff_frame_i.value = int(state["diff_frame"])
    dut.diff_line_i.value = int(state["diff_line"])
    dut.diff_x_i.value = int(state["diff_x"])
    dut.diff_expected_shade_i.value = int(state["diff_expected_shade"])
    dut.diff_actual_shade_i.value = int(state["diff_actual_shade"])
    dut.diff_expected_source_i.value = int(state["diff_expected_source"])
    dut.diff_actual_source_i.value = int(state["diff_actual_source"])
    dut.event_kind_i.value = event_kind
    dut.pixel_x_i.value = x
    dut.pixel_y_i.value = y
    dut.pixel_shade_i.value = shade
    dut.pixel_source_i.value = source
    dut.blank_reason_i.value = blank_reason
    dut.ref_valid_i.value = int(ref_valid)
    dut.ref_shade_i.value = ref_shade
    dut.ref_source_i.value = ref_source
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


def state_from_snapshot(snapshot: dict[str, int | bool]) -> dict[str, int | bool]:
    return {
        "line_frame": snapshot["line_frame"],
        "line_frame_started": snapshot["line_frame_started"],
        "line_y": snapshot["line_y"],
        "line_active": snapshot["line_active"],
        "line_pixel_count": snapshot["line_pixel_count"],
        "line_blank_count": snapshot["line_blank_count"],
        "line_hash": snapshot["line_hash"],
        "line_first_diff_valid": snapshot["line_first_diff_valid"],
        "line_first_diff_x": snapshot["line_first_diff_x"],
        "line_expected_shade": snapshot["line_expected_shade"],
        "line_actual_shade": snapshot["line_actual_shade"],
        "line_expected_source": snapshot["line_expected_source"],
        "line_actual_source": snapshot["line_actual_source"],
        "frame_frame": snapshot["frame_frame"],
        "frame_started": snapshot["frame_started"],
        "frame_line_count": snapshot["frame_line_count"],
        "frame_hash": snapshot["frame_hash"],
        "hash_sample_count": snapshot["hash_sample_count"],
        "hash_value": snapshot["hash_value"],
        "diff_has_diff": snapshot["diff_has_diff"],
        "diff_frame": snapshot["diff_frame"],
        "diff_line": snapshot["diff_line"],
        "diff_x": snapshot["diff_x"],
        "diff_expected_shade": snapshot["diff_expected_shade"],
        "diff_actual_shade": snapshot["diff_actual_shade"],
        "diff_expected_source": snapshot["diff_expected_source"],
        "diff_actual_source": snapshot["diff_actual_source"],
    }


@cocotb.test()
async def test_line_summary_emits_on_next_line_start_with_visible_hash(dut):
    state = initial_state()
    state = state_from_snapshot(await drive(dut, state, event_kind=EVENT_FRAME_START))
    state = state_from_snapshot(await drive(dut, state, event_kind=EVENT_LINE_START, y=0))

    expected_hash = 0
    for x, shade, source in [(0, 1, SOURCE_BG), (1, 2, SOURCE_WINDOW), (2, 3, SOURCE_OBJECT)]:
        expected_hash = mix_hash(expected_hash, pixel_sample(shade, source))
        state = state_from_snapshot(
            await drive(
                dut,
                state,
                event_kind=EVENT_PIXEL,
                x=x,
                y=0,
                shade=shade,
                source=source,
                ref_valid=True,
                ref_shade=shade,
                ref_source=source,
            )
        )

    boundary = await drive(dut, state, event_kind=EVENT_LINE_START, y=1)
    assert boundary["line_summary_valid"] is True
    assert boundary["line_summary_frame"] == 0
    assert boundary["line_summary_line"] == 0
    assert boundary["line_summary_pixel_count"] == 3
    assert boundary["line_summary_blank_count"] == 0
    assert boundary["line_summary_hash"] == expected_hash
    assert boundary["line_summary_full_width"] is False


@cocotb.test()
async def test_blank_events_increment_blank_count_without_touching_line_hash(dut):
    state = initial_state()
    state = state_from_snapshot(await drive(dut, state, event_kind=EVENT_FRAME_START))
    state = state_from_snapshot(await drive(dut, state, event_kind=EVENT_LINE_START, y=4))
    state = state_from_snapshot(await drive(dut, state, event_kind=EVENT_BLANK, y=4, blank_reason=BLANK_NON_VISIBLE_DOT))
    state = state_from_snapshot(await drive(dut, state, event_kind=EVENT_BLANK, y=4, blank_reason=BLANK_WARMUP))

    pixel_hash = mix_hash(0, pixel_sample(2, SOURCE_WINDOW))
    state = state_from_snapshot(
        await drive(
            dut,
            state,
            event_kind=EVENT_PIXEL,
            x=5,
            y=4,
            shade=2,
            source=SOURCE_WINDOW,
            ref_valid=True,
            ref_shade=2,
            ref_source=SOURCE_WINDOW,
        )
    )
    boundary = await drive(dut, state, event_kind=EVENT_LINE_START, y=5)
    assert boundary["line_summary_valid"] is True
    assert boundary["line_summary_blank_count"] == 2
    assert boundary["line_summary_pixel_count"] == 1
    assert boundary["line_summary_hash"] == pixel_hash


@cocotb.test()
async def test_frame_summary_hashes_visible_line_summaries_on_frame_start(dut):
    state = initial_state()
    state = state_from_snapshot(await drive(dut, state, event_kind=EVENT_FRAME_START))
    state = state_from_snapshot(await drive(dut, state, event_kind=EVENT_LINE_START, y=0))

    line0_hash = mix_hash(0, pixel_sample(1, SOURCE_BG))
    state = state_from_snapshot(
        await drive(
            dut,
            state,
            event_kind=EVENT_PIXEL,
            x=0,
            y=0,
            shade=1,
            source=SOURCE_BG,
            ref_valid=True,
            ref_shade=1,
            ref_source=SOURCE_BG,
        )
    )
    state = state_from_snapshot(await drive(dut, state, event_kind=EVENT_LINE_START, y=1))

    line1_hash = mix_hash(0, pixel_sample(3, SOURCE_OBJECT))
    state = state_from_snapshot(
        await drive(
            dut,
            state,
            event_kind=EVENT_PIXEL,
            x=0,
            y=1,
            shade=3,
            source=SOURCE_OBJECT,
            ref_valid=True,
            ref_shade=3,
            ref_source=SOURCE_OBJECT,
        )
    )

    frame_boundary = await drive(dut, state, event_kind=EVENT_FRAME_START)
    expected_frame_hash = mix_hash(mix_hash(0, line0_hash), line1_hash)
    assert frame_boundary["frame_summary_valid"] is True
    assert frame_boundary["frame_summary_frame"] == 0
    assert frame_boundary["frame_summary_line_count"] == 2
    assert frame_boundary["frame_summary_hash"] == expected_frame_hash
    assert frame_boundary["frame_summary_full_frame"] is False


@cocotb.test()
async def test_hash_and_diff_sinks_track_first_pixel_mismatch_only(dut):
    state = initial_state()
    state = state_from_snapshot(await drive(dut, state, event_kind=EVENT_FRAME_START))
    state = state_from_snapshot(await drive(dut, state, event_kind=EVENT_LINE_START, y=9))

    first = await drive(
        dut,
        state,
        event_kind=EVENT_PIXEL,
        x=10,
        y=9,
        shade=1,
        source=SOURCE_BG,
        ref_valid=True,
        ref_shade=2,
        ref_source=SOURCE_WINDOW,
    )
    assert first["diff_has_diff"] is True
    assert first["diff_frame"] == 0
    assert first["diff_line"] == 9
    assert first["diff_x"] == 10
    assert first["diff_expected_shade"] == 2
    assert first["diff_actual_shade"] == 1
    assert first["diff_expected_source"] == SOURCE_WINDOW
    assert first["diff_actual_source"] == SOURCE_BG
    assert first["hash_sample_count"] == 1
    assert first["hash_value"] == mix_hash(0, pixel_sample(1, SOURCE_BG))

    state = state_from_snapshot(first)
    second = await drive(
        dut,
        state,
        event_kind=EVENT_PIXEL,
        x=11,
        y=9,
        shade=3,
        source=SOURCE_OBJECT,
        ref_valid=True,
        ref_shade=0,
        ref_source=SOURCE_BG,
    )
    assert second["diff_has_diff"] is True
    assert second["diff_x"] == 10
    assert second["hash_sample_count"] == 2
    assert second["hash_value"] == mix_hash(mix_hash(0, pixel_sample(1, SOURCE_BG)), pixel_sample(3, SOURCE_OBJECT))
