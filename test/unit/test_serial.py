# top = periph::serial_test_top::serial_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


SB_ADDR = 0xFF01
SC_ADDR = 0xFF02


def decode_serial(output_value: int) -> dict[str, int | bool]:
    return {
        "sb": (output_value >> 14) & 0xFF,
        "sc": (output_value >> 6) & 0xFF,
        "serial_irq": bool((output_value >> 5) & 0x1),
        "transfer_active": bool((output_value >> 4) & 0x1),
        "cycles_left": output_value & 0xF,
    }


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.m_ce_i.value = 0
    dut.write_en_i.value = 0
    dut.write_addr_i.value = 0
    dut.write_data_i.value = 0
    dut.serial_inject_i.value = 0xFF
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step(
    dut,
    *,
    m_ce: bool = True,
    write_addr: int | None = None,
    write_data: int = 0,
    serial_inject: int = 0xFF,
) -> dict[str, int | bool]:
    dut.m_ce_i.value = int(m_ce)
    dut.write_en_i.value = int(write_addr is not None)
    dut.write_addr_i.value = (write_addr or 0) & 0xFFFF
    dut.write_data_i.value = write_data & 0xFF
    dut.serial_inject_i.value = serial_inject & 0xFF
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_serial(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_sb_read_write_round_trip(dut):
    await reset_dut(dut)

    snapshot = await step(dut, write_addr=SB_ADDR, write_data=0x4D)
    assert snapshot["sb"] == 0x4D
    assert snapshot["sc"] == 0x00
    assert snapshot["serial_irq"] is False


@cocotb.test()
async def test_internal_clock_transfer_completes_after_eight_enabled_cycles(dut):
    await reset_dut(dut)

    await step(dut, write_addr=SB_ADDR, write_data=0x41)
    snapshot = await step(dut, write_addr=SC_ADDR, write_data=0x81)
    assert snapshot["transfer_active"] is True
    assert snapshot["cycles_left"] == 8
    assert snapshot["sc"] == 0x81

    for expected_cycles_left in range(7, 0, -1):
        snapshot = await step(dut)
        assert snapshot["transfer_active"] is True, snapshot
        assert snapshot["cycles_left"] == expected_cycles_left, snapshot
        assert snapshot["serial_irq"] is False, snapshot
        assert snapshot["sb"] == 0x41, snapshot

    snapshot = await step(dut)
    assert snapshot["transfer_active"] is False, snapshot
    assert snapshot["cycles_left"] == 0, snapshot
    assert snapshot["serial_irq"] is True, snapshot
    assert snapshot["sb"] == 0xFF, snapshot
    assert snapshot["sc"] == 0x01, snapshot

    snapshot = await step(dut)
    assert snapshot["serial_irq"] is False, snapshot


@cocotb.test()
async def test_transfer_result_uses_injected_byte_when_present(dut):
    await reset_dut(dut)

    await step(dut, write_addr=SB_ADDR, write_data=0x99)
    await step(dut, write_addr=SC_ADDR, write_data=0x81, serial_inject=0xA5)
    for _ in range(8):
        snapshot = await step(dut, serial_inject=0xA5)

    assert snapshot["sb"] == 0xA5
    assert snapshot["serial_irq"] is True


@cocotb.test()
async def test_external_clock_mode_does_not_start_transfer(dut):
    await reset_dut(dut)

    await step(dut, write_addr=SB_ADDR, write_data=0x52)
    snapshot = await step(dut, write_addr=SC_ADDR, write_data=0x80)
    assert snapshot["transfer_active"] is False
    assert snapshot["cycles_left"] == 0
    assert snapshot["sc"] == 0x80
    assert snapshot["serial_irq"] is False

    for _ in range(4):
        snapshot = await step(dut)
        assert snapshot["transfer_active"] is False
        assert snapshot["serial_irq"] is False
        assert snapshot["sb"] == 0x52


@cocotb.test()
async def test_m_ce_low_holds_transfer_progress(dut):
    await reset_dut(dut)

    await step(dut, write_addr=SC_ADDR, write_data=0x81)
    snapshot = await step(dut, m_ce=False)
    assert snapshot["transfer_active"] is True
    assert snapshot["cycles_left"] == 8
    assert snapshot["serial_irq"] is False

    snapshot = await step(dut, m_ce=True)
    assert snapshot["cycles_left"] == 7
