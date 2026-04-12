# top = board::icebreaker_alu_loop_top::icebreaker_alu_loop_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly
from spade import SpadeExt


BOARD_RESET_DEBOUNCE_TICKS = 48_000
BOARD_RESET_RELEASE_HOLD_TICKS = 16
BOARD_RESET_RELEASE_MARGIN_TICKS = 4


def decode_pc(arch_state_value: int) -> int:
    regs = (arch_state_value >> 4) & ((1 << 96) - 1)
    return regs & 0xFFFF


def read_dbg_pc(dut) -> int:
    return (
        (int(dut.DBG_PC3.value) << 3)
        | (int(dut.DBG_PC2.value) << 2)
        | (int(dut.DBG_PC1.value) << 1)
        | int(dut.DBG_PC0.value)
    )


def read_dbg_phase(dut) -> int:
    return (
        (int(dut.DBG_PHASE2.value) << 2)
        | (int(dut.DBG_PHASE1.value) << 1)
        | int(dut.DBG_PHASE0.value)
    )


async def reset_dut(dut):
    s = SpadeExt(dut)
    cocotb.start_soon(Clock(dut.CLK, 83, units="ns").start())
    s.i.BTN_D_UP = "false"
    s.i.BTN_D_DOWN = "false"
    s.i.BTN_D_LEFT = "false"
    s.i.BTN_D_RIGHT = "false"
    s.i.DIP_A = "false"
    s.i.DIP_B = "false"
    s.i.DIP_START = "false"
    s.i.DIP_SELECT = "false"
    s.i.BTN_N = "false"
    await ClockCycles(dut.CLK, 5)
    s.i.BTN_N = "true"
    await ClockCycles(
        dut.CLK,
        BOARD_RESET_DEBOUNCE_TICKS + BOARD_RESET_RELEASE_HOLD_TICKS + BOARD_RESET_RELEASE_MARGIN_TICKS,
    )
    await ReadOnly()


async def observe_dbg_mce_values(dut, cycles: int) -> set[int]:
    seen: set[int] = set()
    for _ in range(cycles):
        await ClockCycles(dut.CLK, 1)
        await ReadOnly()
        seen.add(int(dut.DBG_MCE.value))
    return seen


async def observe_dbg_phase_values(dut, cycles: int) -> set[int]:
    seen: set[int] = set()
    for _ in range(cycles):
        await ClockCycles(dut.CLK, 1)
        await ReadOnly()
        seen.add(read_dbg_phase(dut))
    return seen


@cocotb.test()
async def test_cpu_only_top_exposes_pc_phase_and_mce_on_debug_bus(dut):
    await reset_dut(dut)

    core = dut.alu_loop_hardware_core_0
    assert dut.LEDR_N.value == 1
    assert dut.LEDG_N.value == 1
    assert int(core.timebase_0.sys_counter.value) <= BOARD_RESET_RELEASE_MARGIN_TICKS
    assert read_dbg_pc(dut) == (decode_pc(int(core.cpu_core_0.arch_state.value)) & 0xF)
    assert 0 <= read_dbg_phase(dut) <= 7
    assert await observe_dbg_mce_values(dut, 8) == {0, 1}


@cocotb.test()
async def test_cpu_only_top_heartbeat_and_debug_bus_progress(dut):
    await reset_dut(dut)

    core = dut.alu_loop_hardware_core_0
    await ClockCycles(dut.CLK, 16)
    await ReadOnly()
    assert int(core.timebase_0.sys_counter.value) >= 16
    assert dut.LEDG_N.value == 1
    assert read_dbg_pc(dut) == (decode_pc(int(core.cpu_core_0.arch_state.value)) & 0xF)
    assert await observe_dbg_mce_values(dut, 8) == {0, 1}
    assert len(await observe_dbg_phase_values(dut, 32)) >= 2

    await ClockCycles(dut.CLK, 260)
    await ReadOnly()
    assert dut.LEDR_N.value == 0
    assert len(await observe_dbg_phase_values(dut, 32)) >= 2
    assert await observe_dbg_mce_values(dut, 8) == {0, 1}
