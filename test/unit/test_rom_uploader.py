# top = periph::rom_uploader_test_top::rom_uploader_test_top
from __future__ import annotations

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


BIT_TICKS = 4
HALF_BIT_TICKS = 2
ACK_A = 0x41
ACK_N = 0x4E


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "read_data": value & 0xFF,
        "hold_reset": bool((value >> 8) & 0x1),
        "tx_o": bool((value >> 9) & 0x1),
        "rom_ready": bool((value >> 10) & 0x1),
        "tx_busy": bool((value >> 11) & 0x1),
        "state": (value >> 12) & 0xF,
        "bytes_remaining": (value >> 16) & 0xFFFF,
    }


def decode_output_value(signal) -> dict[str, int | bool]:
    raw = signal.value.binstr.lower()
    width = len(raw)

    def bit_at(index: int, default: bool) -> bool:
        char = raw[width - 1 - index]
        if char == "0":
            return False
        if char == "1":
            return True
        return default

    def uint_at(lsb: int, bits: int, default: int = 0) -> int:
        value = 0
        for offset in range(bits):
            if bit_at(lsb + offset, bool((default >> offset) & 0x1)):
                value |= 1 << offset
        return value

    return {
        "read_data": uint_at(0, 8, 0),
        "hold_reset": bit_at(8, True),
        "tx_o": bit_at(9, True),
        "rom_ready": bit_at(10, False),
        "tx_busy": bit_at(11, False),
        "state": uint_at(12, 4, 0),
        "bytes_remaining": uint_at(16, 16, 0),
    }


async def advance_cycle(
    dut,
    sim: dict[str, int],
    *,
    rx_level: int = 1,
    read_addr: int | None = None,
) -> None:
    dut.rx_i.value = rx_level
    if read_addr is not None:
        dut.read_addr_i.value = read_addr & 0x7FFF
    dut.t_index_i.value = sim["cycle"] & 0x3
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    sim["cycle"] += 1


async def step_cycle(
    dut,
    sim: dict[str, int],
    *,
    rx_level: int = 1,
    read_addr: int | None = None,
) -> dict[str, int | bool]:
    await advance_cycle(dut, sim, rx_level=rx_level, read_addr=read_addr)
    return decode_output_value(dut.output__)


async def reset_dut(dut) -> dict[str, int]:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.rx_i.value = 1
    dut.read_addr_i.value = 0
    dut.bit_ticks_i.value = BIT_TICKS
    dut.half_bit_ticks_i.value = HALF_BIT_TICKS
    dut.rst_i.value = 1
    sim = {"cycle": 0}
    for _ in range(6):
        await advance_cycle(dut, sim, rx_level=1, read_addr=0)
    dut.rst_i.value = 0
    return sim


async def drive_level(
    dut,
    sim: dict[str, int],
    level: int,
    cycles: int,
    *,
    read_addr: int = 0,
) -> list[dict[str, int | bool]]:
    snapshots: list[dict[str, int | bool]] = []
    for _ in range(cycles):
        snapshots.append(await step_cycle(dut, sim, rx_level=level, read_addr=read_addr))
    return snapshots


async def send_uart_byte(
    dut,
    sim: dict[str, int],
    byte: int,
    *,
    read_addr: int = 0,
) -> list[dict[str, int | bool]]:
    snapshots: list[dict[str, int | bool]] = []
    snapshots.extend(await drive_level(dut, sim, 0, BIT_TICKS, read_addr=read_addr))
    for bit_index in range(8):
        snapshots.extend(await drive_level(dut, sim, (byte >> bit_index) & 0x1, BIT_TICKS, read_addr=read_addr))
    snapshots.extend(await drive_level(dut, sim, 1, BIT_TICKS, read_addr=read_addr))
    return snapshots


def payload_checksum(payload: bytes) -> int:
    checksum = 0
    for byte in payload:
        checksum ^= byte
    return checksum


async def send_frame(
    dut,
    sim: dict[str, int],
    payload: bytes,
    *,
    corrupt_checksum: bool = False,
    length_override: int | None = None,
) -> None:
    length = len(payload) if length_override is None else length_override
    checksum = payload_checksum(payload)
    if corrupt_checksum:
        checksum ^= 0x01
    frame = b"ROM!" + length.to_bytes(2, "little") + payload + bytes([checksum])
    for byte in frame:
        await send_uart_byte(dut, sim, byte)


async def recv_uart_byte(
    dut,
    sim: dict[str, int],
    *,
    timeout_cycles: int = 2000,
    read_addr: int = 0,
) -> int:
    for _ in range(timeout_cycles):
        snapshot = await step_cycle(dut, sim, rx_level=1, read_addr=read_addr)
        if snapshot["tx_o"] is False:
            break
    else:
        raise AssertionError("timed out waiting for UART start bit")

    for _ in range(BIT_TICKS + HALF_BIT_TICKS):
        snapshot = await step_cycle(dut, sim, rx_level=1, read_addr=read_addr)

    value = 0
    for bit_index in range(8):
        if snapshot["tx_o"]:
            value |= 1 << bit_index
        for _ in range(BIT_TICKS):
            snapshot = await step_cycle(dut, sim, rx_level=1, read_addr=read_addr)

    assert snapshot["tx_o"] is True
    return value


async def read_memory_byte(dut, sim: dict[str, int], addr: int) -> int:
    snapshot = await step_cycle(dut, sim, rx_level=1, read_addr=addr)
    while (sim["cycle"] - 1) & 0x3 != 1:
        snapshot = await step_cycle(dut, sim, rx_level=1, read_addr=addr)
    return int(snapshot["read_data"])


@cocotb.test()
async def test_happy_path_uploads_1k_payload_and_deasserts_reset(dut):
    sim = await reset_dut(dut)
    payload = bytes((index * 17 + 3) & 0xFF for index in range(1024))

    await send_frame(dut, sim, payload)
    ack = await recv_uart_byte(dut, sim)
    assert ack == ACK_A

    for _ in range(20):
        snapshot = await step_cycle(dut, sim, rx_level=1, read_addr=0)
    assert snapshot["hold_reset"] is False

    for addr, expected in enumerate(payload):
        observed = await read_memory_byte(dut, sim, addr)
        assert observed == expected, (addr, observed, expected)


@cocotb.test()
async def test_checksum_failure_emits_negative_ack_and_keeps_reset_asserted(dut):
    sim = await reset_dut(dut)
    payload = bytes((index * 9 + 1) & 0xFF for index in range(32))

    await send_frame(dut, sim, payload, corrupt_checksum=True)
    ack = await recv_uart_byte(dut, sim)
    assert ack == ACK_N

    for _ in range(20):
        snapshot = await step_cycle(dut, sim, rx_level=1, read_addr=0)
    assert snapshot["hold_reset"] is True


@cocotb.test()
async def test_oversize_length_is_rejected_before_payload(dut):
    sim = await reset_dut(dut)

    for byte in b"ROM!" + (33000).to_bytes(2, "little"):
        await send_uart_byte(dut, sim, byte)
    ack = await recv_uart_byte(dut, sim)
    assert ack == ACK_N

    for _ in range(8):
        snapshot = await step_cycle(dut, sim, rx_level=1, read_addr=0)
    assert snapshot["hold_reset"] is True


@cocotb.test()
async def test_reset_rearms_uploader_for_second_upload(dut):
    sim = await reset_dut(dut)
    first_payload = bytes(range(16))
    second_payload = bytes((0xF0 - index) & 0xFF for index in range(16))

    await send_frame(dut, sim, first_payload)
    assert await recv_uart_byte(dut, sim) == ACK_A
    for _ in range(12):
        snapshot = await step_cycle(dut, sim, rx_level=1, read_addr=0)
    assert snapshot["hold_reset"] is False

    dut.rst_i.value = 1
    for _ in range(4):
        await step_cycle(dut, sim, rx_level=1, read_addr=0)
    dut.rst_i.value = 0

    await send_frame(dut, sim, second_payload)
    assert await recv_uart_byte(dut, sim) == ACK_A
    for _ in range(12):
        snapshot = await step_cycle(dut, sim, rx_level=1, read_addr=0)
    assert snapshot["hold_reset"] is False

    for addr, expected in enumerate(second_payload):
        observed = await read_memory_byte(dut, sim, addr)
        assert observed == expected, (addr, observed, expected)


@cocotb.test()
async def test_garbled_input_does_not_false_trigger_upload_or_ack(dut):
    sim = await reset_dut(dut)
    rng = random.Random(0x2A3F)

    for _ in range(64):
        await send_uart_byte(dut, sim, rng.randrange(256))

    for _ in range(200):
        snapshot = await step_cycle(dut, sim, rx_level=1, read_addr=0)
        assert snapshot["tx_o"] is True
        assert snapshot["hold_reset"] is True
