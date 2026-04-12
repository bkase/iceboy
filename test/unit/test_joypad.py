# top = periph::joypad_test_top::joypad_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


P1_ADDR = 0xFF00

BUTTON_RIGHT = 0x01
BUTTON_LEFT = 0x02
BUTTON_UP = 0x04
BUTTON_DOWN = 0x08
BUTTON_A = 0x10
BUTTON_B = 0x20
BUTTON_SELECT = 0x40
BUTTON_START = 0x80


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "p1": (value >> 1) & 0xFF,
        "joypad_irq": bool(value & 0x1),
    }


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.write_en_i.value = 0
    dut.write_addr_i.value = 0
    dut.write_data_i.value = 0
    dut.buttons_i.value = 0
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
) -> dict[str, int | bool]:
    dut.write_en_i.value = int(write_addr is not None)
    dut.write_addr_i.value = (write_addr or 0) & 0xFFFF
    dut.write_data_i.value = write_data & 0xFF
    dut.buttons_i.value = buttons & 0xFF
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_default_read_with_no_buttons_pressed_is_cf(dut):
    await reset_dut(dut)
    snapshot = await step(dut)
    assert snapshot["p1"] == 0xCF
    assert snapshot["joypad_irq"] is False


@cocotb.test()
async def test_action_group_read_reports_a_pressed_active_low(dut):
    await reset_dut(dut)
    snapshot = await step(dut, write_addr=P1_ADDR, write_data=0x10, buttons=BUTTON_A)
    assert snapshot["p1"] == 0xDE


@cocotb.test()
async def test_dpad_group_read_reports_up_pressed_active_low(dut):
    await reset_dut(dut)
    snapshot = await step(dut, write_addr=P1_ADDR, write_data=0x20, buttons=BUTTON_UP)
    assert snapshot["p1"] == 0xEB


@cocotb.test()
async def test_both_groups_selected_or_active_low_bits(dut):
    await reset_dut(dut)
    snapshot = await step(dut, write_addr=P1_ADDR, write_data=0x00, buttons=BUTTON_A | BUTTON_UP)
    assert snapshot["p1"] == 0xCA


@cocotb.test()
async def test_neither_group_selected_returns_low_nibble_ff(dut):
    await reset_dut(dut)
    snapshot = await step(dut, write_addr=P1_ADDR, write_data=0x30, buttons=BUTTON_A | BUTTON_UP)
    assert snapshot["p1"] == 0xFF


@cocotb.test()
async def test_write_low_nibble_is_ignored(dut):
    await reset_dut(dut)
    snapshot = await step(dut, write_addr=P1_ADDR, write_data=0x2F, buttons=BUTTON_B)
    assert snapshot["p1"] == 0xEF


@cocotb.test()
async def test_irq_fires_on_button_press_in_selected_group(dut):
    await reset_dut(dut)
    await step(dut, write_addr=P1_ADDR, write_data=0x10, buttons=0)
    snapshot = await step(dut, buttons=BUTTON_A)
    assert snapshot["joypad_irq"] is True
    snapshot = await step(dut, buttons=BUTTON_A)
    assert snapshot["joypad_irq"] is False


@cocotb.test()
async def test_irq_does_not_fire_on_button_release(dut):
    await reset_dut(dut)
    await step(dut, write_addr=P1_ADDR, write_data=0x10, buttons=BUTTON_A)
    await step(dut, buttons=BUTTON_A)
    snapshot = await step(dut, buttons=0)
    assert snapshot["joypad_irq"] is False


@cocotb.test()
async def test_irq_does_not_fire_when_group_not_selected(dut):
    await reset_dut(dut)
    await step(dut, write_addr=P1_ADDR, write_data=0x30, buttons=0)
    snapshot = await step(dut, buttons=BUTTON_A)
    assert snapshot["joypad_irq"] is False
