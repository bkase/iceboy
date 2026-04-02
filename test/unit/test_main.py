# top = board::icebreaker_top::icebreaker_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles
from spade import SpadeExt


@cocotb.test()
async def test_leds_start_on_after_reset(dut):
    """After reset, both LEDs should be on (counters at 0, below threshold)."""
    s = SpadeExt(dut)

    # 12 MHz clock
    clock = Clock(dut.CLK, 83, units="ns")
    cocotb.start_soon(clock.start())

    # Reset (BTN_N active low: false = pressed = reset active)
    s.i.BTN_N = "false"
    await ClockCycles(dut.CLK, 5)
    s.i.BTN_N = "true"
    await RisingEdge(dut.CLK)

    # After reset, counters are 0. 0 < 1_000_000 = true, so LED_fast = 1.
    # The _N suffix is a PCB convention; no inversion in the Verilog.
    assert dut.LEDR_N.value == 1, f"Expected LEDR_N=1 (on), got {dut.LEDR_N.value}"
    assert dut.LEDG_N.value == 1, f"Expected LEDG_N=1 (on), got {dut.LEDG_N.value}"


@cocotb.test()
async def test_leds_stay_on_for_initial_cycles(dut):
    """LEDs should stay on for the first several cycles after reset."""
    s = SpadeExt(dut)

    clock = Clock(dut.CLK, 83, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    s.i.BTN_N = "false"
    await ClockCycles(dut.CLK, 5)
    s.i.BTN_N = "true"

    # Run for 100 cycles - counters still well below threshold
    await ClockCycles(dut.CLK, 100)
    assert dut.LEDR_N.value == 1, f"Expected LEDR_N=1 (on), got {dut.LEDR_N.value}"
    assert dut.LEDG_N.value == 1, f"Expected LEDG_N=1 (on), got {dut.LEDG_N.value}"
