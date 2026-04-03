# top = sim::soc_lockstep_top::soc_lockstep_top
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import ReadOnly, Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from dut_driver import SimStimulus
from fixtures import soc_lockstep_dut
from spec.profiles import CPU_BRING_UP_PROFILES


async def capture_cpu_state(dut) -> tuple[str, str, str]:
    await ReadOnly()
    state = (
        dut.cpu_core_0.arch_state.value.binstr,
        dut.cpu_core_0.micro_state.value.binstr,
        dut.cpu_core_0.commit_seq.value.binstr,
    )
    await Timer(1, units="ps")
    return state


@cocotb.test()
async def test_cpu_hold_only_freezes_cpu_state_while_timebase_advances(dut):
    driver = soc_lockstep_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)
    baseline = await capture_cpu_state(dut)

    observations = []
    for _ in range(8):
        observations.append(
            await driver.step_mcycle(
                stimulus=SimStimulus(cpu_hold_only=True),
                bus_read_data=0xA5,
                irq_pending=0x12,
            )
        )
        assert await capture_cpu_state(dut) == baseline

    assert [obs.sys_counter for obs in observations] == list(range(1, 9))
    assert all(obs.cpu_arch_time_enable is False for obs in observations)
    assert all(obs.peripheral_arch_time_enable is True for obs in observations)
    assert all(obs.bus_req_kind == 0 for obs in observations)
    assert all(obs.bus_owner == 3 for obs in observations)
    assert all(obs.bus_region == 8 for obs in observations)
    assert all(obs.commit_seq == 0 for obs in observations)
    assert all(obs.pc == 0x0100 for obs in observations)


@cocotb.test()
async def test_m_ce_zero_freeze_arch_time_holds_core_state_for_100_cycles(dut):
    driver = soc_lockstep_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)
    baseline = await capture_cpu_state(dut)

    observations = []
    for _ in range(100):
        observations.append(
            await driver.step_mcycle(
                stimulus=SimStimulus(freeze_arch_time=True),
                bus_read_data=0x5A,
                irq_pending=0x03,
            )
        )
        assert await capture_cpu_state(dut) == baseline

    assert all(obs.cpu_arch_time_enable is False for obs in observations)
    assert all(obs.peripheral_arch_time_enable is False for obs in observations)
    assert all(obs.bus_req_kind == 0 for obs in observations)
    assert all(obs.commit_seq == 0 for obs in observations)
    assert all(obs.pc == 0x0100 for obs in observations)
    assert observations[-1].sys_counter == 100
    assert any(obs.m_ce for obs in observations)
    assert observations[-1].m_index > 0
