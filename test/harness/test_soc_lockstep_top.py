# top = sim::soc_lockstep_top::soc_lockstep_top
import sys
from pathlib import Path

import cocotb


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from fixtures import soc_lockstep_dut
from spec.profiles import CPU_BRING_UP_PROFILES


@cocotb.test()
async def test_soc_lockstep_top_surfaces_timebase_and_core_state(dut):
    driver = soc_lockstep_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)

    observations = []
    for _ in range(4):
        observations.append(
            await driver.step_mcycle(
                bus_read_data=0x44,
                irq_pending=0x03,
            )
        )

    assert [obs.sys_counter for obs in observations] == [1, 2, 3, 4]
    assert [obs.t_index for obs in observations] == [1, 2, 3, 0]
    assert [obs.m_ce for obs in observations] == [False, False, True, False]
    assert [obs.commit_seq for obs in observations] == [0, 0, 1, 1]
    assert [obs.pc for obs in observations] == [0x0100, 0x0100, 0x0101, 0x0101]

    final = observations[-1]
    assert final.model_profile == 0
    assert final.reset_profile == 0
    assert final.memory_behavior_profile == 0
    assert final.cpu_arch_time_enable is True
    assert final.peripheral_arch_time_enable is True
    assert final.bus_read_data == 0x44
    assert final.irq_pending == 0x03
    assert final.bus_req_kind == 0
    assert final.bus_req_addr == 0
    assert final.bus_req_data == 0
    assert final.bus_region == 0
    assert final.bus_owner == 0
    assert final.bus_blocked is False
