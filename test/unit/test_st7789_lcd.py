# top = periph::st7789_lcd_test_top::st7789_lcd_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "lcd_sck": bool(value & 0x1),
        "lcd_mosi": bool((value >> 1) & 0x1),
        "lcd_cs": bool((value >> 2) & 0x1),
        "lcd_dc": bool((value >> 3) & 0x1),
        "lcd_res": bool((value >> 4) & 0x1),
        "lcd_bl": bool((value >> 5) & 0x1),
        "pixel_advance": bool((value >> 6) & 0x1),
        "init_done": bool((value >> 7) & 0x1),
        "frame_active": bool((value >> 8) & 0x1),
        "tx_active": bool((value >> 9) & 0x1),
        "state_code": (value >> 10) & 0xF,
        "current_byte": (value >> 14) & 0xFF,
        "current_dc": bool((value >> 22) & 0x1),
        "command_index": (value >> 23) & 0xF,
        "data_index": (value >> 27) & 0x7,
        "pixel_count": (value >> 30) & 0x7FFF,
    }


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.reset_ticks_i.value = 2
    dut.post_reset_ticks_i.value = 3
    dut.sleep_out_ticks_i.value = 4
    dut.frame_start_i.value = 0
    dut.pixel_valid_i.value = 0
    dut.pixel_shade_i.value = 0
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step(
    dut,
    *,
    frame_start: bool = False,
    pixel_valid: bool = False,
    pixel_shade: int = 0,
) -> dict[str, int | bool]:
    dut.frame_start_i.value = int(frame_start)
    dut.pixel_valid_i.value = int(pixel_valid)
    dut.pixel_shade_i.value = pixel_shade & 0xFF
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


async def collect_bytes(
    dut,
    *,
    expected_count: int,
    frame_start_at_cycle: int | None = None,
    pixel_valid_after_init: bool = False,
    pixel_shade: int = 0,
    max_cycles: int = 4000,
) -> list[tuple[int, int]]:
    transcript: list[tuple[int, int]] = []
    prev = decode_output(int(dut.output__.value))
    byte = 0
    bit_count = 0
    byte_dc = 0

    for cycle in range(max_cycles):
        snapshot = await step(
            dut,
            frame_start=frame_start_at_cycle is not None and cycle == frame_start_at_cycle,
            pixel_valid=pixel_valid_after_init,
            pixel_shade=pixel_shade,
        )

        if snapshot["lcd_cs"]:
            byte = 0
            bit_count = 0
        elif (not prev["lcd_sck"]) and snapshot["lcd_sck"]:
            if bit_count == 0:
                byte_dc = int(snapshot["lcd_dc"])
            byte = ((byte << 1) | int(snapshot["lcd_mosi"])) & 0xFF
            bit_count += 1
            if bit_count == 8:
                transcript.append((byte_dc, byte))
                if len(transcript) >= expected_count:
                    return transcript
                byte = 0
                bit_count = 0

        prev = snapshot

    raise AssertionError(f"Timed out collecting {expected_count} bytes, got {len(transcript)}")


async def wait_until(dut, predicate, *, max_cycles: int = 4000) -> dict[str, int | bool]:
    for _ in range(max_cycles):
        snapshot = await step(dut)
        if predicate(snapshot):
            return snapshot
    raise AssertionError("condition not reached before timeout")


@cocotb.test()
async def test_reset_and_init_sequence_emit_expected_commands(dut):
    await reset_dut(dut)

    snapshot = await step(dut)
    assert snapshot["lcd_res"] is False
    assert snapshot["lcd_bl"] is False
    assert snapshot["init_done"] is False

    transcript = await collect_bytes(dut, expected_count=19)
    expected = [
        (0, 0x01),
        (0, 0x11),
        (0, 0x3A),
        (1, 0x55),
        (0, 0x36),
        (1, 0x00),
        (0, 0x2A),
        (1, 0x00),
        (1, 0x00),
        (1, 0x01),
        (1, 0x3F),
        (0, 0x2B),
        (1, 0x00),
        (1, 0x00),
        (1, 0x00),
        (1, 0xEF),
        (0, 0x21),
        (0, 0x13),
        (0, 0x29),
    ]
    assert transcript == expected, transcript

    final = await wait_until(dut, lambda snap: bool(snap["init_done"]) and not bool(snap["frame_active"]) and not bool(snap["tx_active"]))
    assert final["lcd_res"] is True
    assert final["lcd_bl"] is True


@cocotb.test()
async def test_frame_start_emits_window_commands_and_first_pixel(dut):
    await reset_dut(dut)
    await wait_until(dut, lambda snap: bool(snap["init_done"]) and not bool(snap["frame_active"]))

    transcript = await collect_bytes(
        dut,
        expected_count=13,
        frame_start_at_cycle=0,
        pixel_valid_after_init=True,
        pixel_shade=0,
        max_cycles=5000,
    )
    expected_prefix = [
        (0, 0x2A),
        (1, 0x00),
        (1, 0x50),
        (1, 0x00),
        (1, 0xEF),
        (0, 0x2B),
        (1, 0x00),
        (1, 0x30),
        (1, 0x00),
        (1, 0xBF),
        (0, 0x2C),
        (1, 0xFF),
        (1, 0xFF),
    ]
    assert transcript == expected_prefix, transcript

    for _ in range(2000):
        advanced = await step(dut, pixel_valid=True, pixel_shade=0)
        if advanced["pixel_advance"]:
            break
    else:
        raise AssertionError("pixel_advance did not pulse while pixel stream was enabled")

    assert advanced["frame_active"] is True
    assert advanced["pixel_count"] >= 1
