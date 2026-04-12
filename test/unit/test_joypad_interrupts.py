# top = periph::joypad_interrupts_test_top::joypad_interrupts_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


IE_ADDR = 0xFFFF
P1_ADDR = 0xFF00

BUTTON_A = 0x10


def decode_output(value: int) -> dict[str, int]:
    return {
        "p1": (value >> 13) & 0xFF,
        "iflags": (value >> 5) & 0xFF,
        "pending": value & 0x1F,
    }


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.write_en_i.value = 0
    dut.write_addr_i.value = 0
    dut.write_data_i.value = 0
    dut.buttons_i_i.value = 0
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step(
    dut,
    *,
    write_addr: int | None = None,
    write_data: int = 0,
    buttons: int = 0,
) -> dict[str, int]:
    dut.write_en_i.value = int(write_addr is not None)
    dut.write_addr_i.value = (write_addr or 0) & 0xFFFF
    dut.write_data_i.value = write_data & 0xFF
    dut.buttons_i_i.value = buttons & 0xFF
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_selected_button_press_sets_joypad_if_and_pending(dut):
    await reset_dut(dut)

    snapshot = await step(dut, write_addr=IE_ADDR, write_data=0x10)
    assert snapshot["iflags"] == 0xE0
    assert snapshot["pending"] == 0x00

    snapshot = await step(dut, write_addr=P1_ADDR, write_data=0x10, buttons=0)
    assert snapshot["p1"] == 0xDF

    snapshot = await step(dut, buttons=BUTTON_A)
    assert snapshot["p1"] == 0xDE
    assert snapshot["iflags"] == 0xE0
    assert snapshot["pending"] == 0x00

    snapshot = await step(dut, buttons=BUTTON_A)
    assert snapshot["iflags"] == 0xF0
    assert snapshot["pending"] == 0x10


@cocotb.test()
async def test_unselected_button_press_does_not_set_joypad_if(dut):
    await reset_dut(dut)

    await step(dut, write_addr=IE_ADDR, write_data=0x10)
    await step(dut, write_addr=P1_ADDR, write_data=0x30, buttons=0)

    snapshot = await step(dut, buttons=BUTTON_A)
    assert snapshot["p1"] == 0xFF
    assert snapshot["iflags"] == 0xE0
    assert snapshot["pending"] == 0x00

    snapshot = await step(dut, buttons=BUTTON_A)
    assert snapshot["iflags"] == 0xE0
    assert snapshot["pending"] == 0x00
