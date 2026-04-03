# top = sim::cpu_test_top::cpu_test_top
import sys
from pathlib import Path

import cocotb


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from assertions import assert_commit_trace_match
from dut_driver import CpuCommitTrace, SimStimulus
from fixtures import cpu_dut
from spec.profiles import ResetProfile


@cocotb.test()
async def test_spade_cocotb_smoke_pipeline(dut):
    """Exercise the generated Verilog through a trivial Cocotb drive/read cycle."""
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)

    trace = await driver.step_mcycle(
        stimulus=SimStimulus.idle(),
        bus_read_data=0xA5,
        irq_pending=0x12,
    )
    assert_commit_trace_match(
        CpuCommitTrace(
            seq=1,
            bus_read_data=0xA5,
            irq_pending=0x12,
            cpu_arch_time_enable=True,
            freeze_arch_time=False,
            cpu_hold_only=False,
            commit_seq=1,
            pc=0x0101,
            bus_req_kind=1,
            bus_req_addr=0x0100,
            bus_req_data=0,
            bus_region=0,
            bus_owner=0,
            bus_blocked=False,
        ),
        trace,
        "smoke.step_1",
    )

    trace = await driver.step_mcycle(
        stimulus=SimStimulus(freeze_arch_time=True, cpu_hold_only=True),
        bus_read_data=0x3C,
        irq_pending=0x05,
    )
    assert_commit_trace_match(
        CpuCommitTrace(
            seq=2,
            bus_read_data=0x3C,
            irq_pending=0x05,
            cpu_arch_time_enable=False,
            freeze_arch_time=True,
            cpu_hold_only=True,
            commit_seq=1,
            pc=0x0101,
            bus_req_kind=0,
            bus_req_addr=0,
            bus_req_data=0,
            bus_region=8,
            bus_owner=3,
            bus_blocked=False,
        ),
        trace,
        "smoke.step_2",
    )
