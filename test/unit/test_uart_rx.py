# top = periph::uart_rx_test_top::uart_rx_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


BIT_TICKS = 10
HALF_BIT_TICKS = 5


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "rx_byte": output_value & 0xFF,
        "rx_byte_valid": bool((output_value >> 8) & 0x1),
        "rx_framing_error": bool((output_value >> 9) & 0x1),
        "busy": bool((output_value >> 10) & 0x1),
        "sync_rx": bool((output_value >> 11) & 0x1),
        "bit_index": (output_value >> 12) & 0xF,
        "ticks_until_sample": (output_value >> 16) & 0xFF,
    }


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.rx_i.value = 1
    dut.bit_ticks_i.value = BIT_TICKS
    dut.half_bit_ticks_i.value = HALF_BIT_TICKS
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 4)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step_cycle(dut) -> dict[str, int | bool]:
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


async def drive_level(dut, level: int, cycles: int, events: list[dict[str, int | bool]]) -> None:
    dut.rx_i.value = level
    for _ in range(cycles):
        events.append(await step_cycle(dut))


async def drive_uart_frame(
    dut,
    byte: int,
    *,
    stop_bit: int = 1,
    idle_cycles: int = BIT_TICKS,
) -> list[dict[str, int | bool]]:
    events: list[dict[str, int | bool]] = []
    await drive_level(dut, 0, BIT_TICKS, events)
    for bit_index in range(8):
        await drive_level(dut, (byte >> bit_index) & 0x1, BIT_TICKS, events)
    await drive_level(dut, stop_bit, BIT_TICKS, events)
    await drive_level(dut, 1, idle_cycles, events)
    return events


def valid_events(events: list[dict[str, int | bool]]) -> list[dict[str, int | bool]]:
    return [event for event in events if event["rx_byte_valid"]]


def error_events(events: list[dict[str, int | bool]]) -> list[dict[str, int | bool]]:
    return [event for event in events if event["rx_framing_error"]]


@cocotb.test()
async def test_receives_single_byte_lsb_first(dut):
    await reset_dut(dut)

    events = await drive_uart_frame(dut, 0xA5)

    received = valid_events(events)
    assert len(received) == 1, received
    assert received[0]["rx_byte"] == 0xA5, received[0]
    assert error_events(events) == []


@cocotb.test()
async def test_receives_back_to_back_bytes(dut):
    await reset_dut(dut)

    events = await drive_uart_frame(dut, 0x3C, idle_cycles=0)
    events.extend(await drive_uart_frame(dut, 0xC3))

    received = valid_events(events)
    assert [event["rx_byte"] for event in received] == [0x3C, 0xC3], received
    assert error_events(events) == []


@cocotb.test()
async def test_invalid_stop_bit_raises_framing_error_without_valid_byte(dut):
    await reset_dut(dut)

    events = await drive_uart_frame(dut, 0x5A, stop_bit=0, idle_cycles=BIT_TICKS * 2)

    assert valid_events(events) == [], events
    framing_errors = error_events(events)
    assert len(framing_errors) == 1, framing_errors
    assert framing_errors[0]["busy"] is False, framing_errors[0]


@cocotb.test()
async def test_short_glitch_does_not_emit_a_spurious_byte(dut):
    await reset_dut(dut)

    events: list[dict[str, int | bool]] = []
    await drive_level(dut, 0, 1, events)
    await drive_level(dut, 1, BIT_TICKS * 3, events)

    assert valid_events(events) == [], events
    assert error_events(events) == [], events
    assert events[-1]["busy"] is False, events[-1]
