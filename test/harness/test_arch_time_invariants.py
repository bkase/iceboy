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
from power_metrics import append_metrics_artifact, read_power_metrics
from spec.profiles import CPU_BRING_UP_PROFILES


SUITE_LABEL = "test_arch_time_invariants.py"


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
    metrics_start = await read_power_metrics(dut)

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

    metrics = (await read_power_metrics(dut)).subtract(metrics_start)
    append_metrics_artifact(SUITE_LABEL, "test_cpu_hold_only_freezes_cpu_state_while_timebase_advances", metrics)

    assert [obs.sys_counter for obs in observations] == list(range(1, 9))
    assert all(obs.cpu_arch_time_enable is False for obs in observations)
    assert all(obs.peripheral_arch_time_enable is True for obs in observations)
    assert all(obs.bus_req_kind == 0 for obs in observations)
    assert all(obs.bus_owner == 3 for obs in observations)
    assert all(obs.bus_region == 8 for obs in observations)
    assert all(obs.commit_seq == 0 for obs in observations)
    assert all(obs.pc == 0x0100 for obs in observations)
    assert metrics.total_cycles == 8
    assert metrics.bus_active_cycles == 0
    assert metrics.alu_active_cycles == 0
    assert metrics.halted_cycles == 0
    assert metrics.halt_quiescent_cycles == 0
    assert metrics.reg_a_we_cycles == 0
    assert metrics.reg_f_we_cycles == 0
    assert metrics.reg_b_we_cycles == 0
    assert metrics.reg_c_we_cycles == 0
    assert metrics.reg_d_we_cycles == 0
    assert metrics.reg_e_we_cycles == 0
    assert metrics.reg_h_we_cycles == 0
    assert metrics.reg_l_we_cycles == 0
    assert metrics.reg_sp_we_cycles == 0
    assert metrics.reg_pc_we_cycles == 0


@cocotb.test()
async def test_m_ce_zero_freeze_arch_time_holds_core_state_for_100_cycles(dut):
    driver = soc_lockstep_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)
    baseline = await capture_cpu_state(dut)
    metrics_start = await read_power_metrics(dut)

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

    metrics = (await read_power_metrics(dut)).subtract(metrics_start)
    append_metrics_artifact(SUITE_LABEL, "test_m_ce_zero_freeze_arch_time_holds_core_state_for_100_cycles", metrics)

    assert all(obs.cpu_arch_time_enable is False for obs in observations)
    assert all(obs.peripheral_arch_time_enable is False for obs in observations)
    assert all(obs.bus_req_kind == 0 for obs in observations)
    assert all(obs.commit_seq == 0 for obs in observations)
    assert all(obs.pc == 0x0100 for obs in observations)
    assert observations[-1].sys_counter == 100
    assert any(obs.m_ce for obs in observations)
    assert observations[-1].m_index > 0
    assert metrics.total_cycles == 100
    assert metrics.bus_active_cycles == 0
    assert metrics.alu_active_cycles == 0
    assert metrics.halted_cycles == 0
    assert metrics.halt_quiescent_cycles == 0
    assert metrics.reg_a_we_cycles == 0
    assert metrics.reg_f_we_cycles == 0
    assert metrics.reg_b_we_cycles == 0
    assert metrics.reg_c_we_cycles == 0
    assert metrics.reg_d_we_cycles == 0
    assert metrics.reg_e_we_cycles == 0
    assert metrics.reg_h_we_cycles == 0
    assert metrics.reg_l_we_cycles == 0
    assert metrics.reg_sp_we_cycles == 0
    assert metrics.reg_pc_we_cycles == 0
