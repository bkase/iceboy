# top = sim::cpu_test_top::cpu_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge


def pack_output(
    *,
    bus_read_data: int,
    irq_pending: int,
    cpu_arch_time_enable: int,
    freeze_arch_time: int,
    cpu_hold_only: int,
) -> int:
    return (
        ((bus_read_data & 0xFF) << 8)
        | ((irq_pending & 0x1F) << 3)
        | ((cpu_arch_time_enable & 0x1) << 2)
        | ((freeze_arch_time & 0x1) << 1)
        | (cpu_hold_only & 0x1)
    )


@cocotb.test()
async def test_spade_cocotb_smoke_pipeline(dut):
    """Exercise the generated Verilog through a trivial Cocotb drive/read cycle."""
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())

    dut.rst_i.value = 1
    dut.stimulus_i.value = 0
    dut.bus_read_data_i.value = 0
    dut.irq_pending_i.value = 0
    await ClockCycles(dut.clk_i, 2)

    dut.rst_i.value = 0
    dut.bus_read_data_i.value = 0xA5
    dut.irq_pending_i.value = 0x12
    dut.stimulus_i.value = 0
    await RisingEdge(dut.clk_i)
    assert int(dut.output__.value) == pack_output(
        bus_read_data=0xA5,
        irq_pending=0x12,
        cpu_arch_time_enable=1,
        freeze_arch_time=0,
        cpu_hold_only=0,
    )

    dut.bus_read_data_i.value = 0x3C
    dut.irq_pending_i.value = 0x05
    dut.stimulus_i.value = 0b11
    await RisingEdge(dut.clk_i)
    assert int(dut.output__.value) == pack_output(
        bus_read_data=0x3C,
        irq_pending=0x05,
        cpu_arch_time_enable=0,
        freeze_arch_time=1,
        cpu_hold_only=1,
    )
