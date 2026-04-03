# top = sim::cpu_test_top::cpu_test_top
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import ReadOnly, Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from dut_driver import SimStimulus
from fixtures import cpu_dut
from spec.profiles import ResetProfile


def decode_dut_registers(arch_state_value: int) -> tuple[int, ...]:
    regs = (arch_state_value >> 4) & ((1 << 96) - 1)
    return (
        (regs >> 88) & 0xFF,
        (regs >> 80) & 0xFF,
        (regs >> 72) & 0xFF,
        (regs >> 64) & 0xFF,
        (regs >> 56) & 0xFF,
        (regs >> 48) & 0xFF,
        (regs >> 32) & 0xFFFF,
        (regs >> 16) & 0xFFFF,
        regs & 0xFFFF,
    )


async def capture_registers(dut) -> tuple[int, ...]:
    await ReadOnly()
    snapshot = decode_dut_registers(int(dut.cpu_core_0.arch_state.value))
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_m_ce_zero_hold_keeps_all_arch_registers_stable(dut):
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)
    baseline = await capture_registers(dut)

    for _ in range(12):
        trace = await driver.step_mcycle(
            stimulus=SimStimulus(freeze_arch_time=True, cpu_hold_only=True),
            bus_read_data=0xA5,
            irq_pending=0x12,
        )
        assert await capture_registers(dut) == baseline
        assert trace.cpu_arch_time_enable is False
        assert trace.commit_seq == 0
        assert trace.bus_req_kind == 0
        assert trace.pc == baseline[-1]
