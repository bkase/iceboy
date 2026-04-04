# top = board::icebreaker_top::icebreaker_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
from spade import SpadeExt


async def reset_dut(dut):
    s = SpadeExt(dut)
    clock = Clock(dut.CLK, 83, units="ns")
    cocotb.start_soon(clock.start())
    s.i.BTN_N = "false"
    await ClockCycles(dut.CLK, 5)
    s.i.BTN_N = "true"
    await RisingEdge(dut.CLK)


@cocotb.test()
async def test_hardware_top_starts_with_live_cpu_and_leds_on(dut):
    await reset_dut(dut)

    assert dut.LEDR_N.value == 1, f"Expected LEDR_N=1 after reset, got {dut.LEDR_N.value}"
    assert dut.LEDG_N.value == 1, f"Expected LEDG_N=1 after reset, got {dut.LEDG_N.value}"
    assert int(dut.hardware_core_0.timebase_0.sys_counter.value) == 0


@cocotb.test()
async def test_hardware_top_cpu_and_heartbeat_progress(dut):
    await reset_dut(dut)

    await ClockCycles(dut.CLK, 16)
    assert int(dut.hardware_core_0.timebase_0.sys_counter.value) >= 16
    assert dut.LEDG_N.value == 1, f"Expected LEDG_N=1 while CPU is running, got {dut.LEDG_N.value}"

    await ClockCycles(dut.CLK, 260)
    assert dut.LEDR_N.value == 0, f"Expected LEDR_N heartbeat to toggle low, got {dut.LEDR_N.value}"
