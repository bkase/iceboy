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
from reset_profile_support import capture_dut_reset_state, expected_reset_state_for
from spec.profiles import CPU_BRING_UP_PROFILES


@cocotb.test()
async def test_skipboot_reset_profile_smoke(dut):
    """Prove reset plumbing is stable before the architectural-state compare lands."""
    driver = cpu_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES.reset)

    trace = await driver.step_mcycle(
        stimulus=SimStimulus.idle(),
        bus_read_data=0,
        irq_pending=0,
    )
    assert_commit_trace_match(
        CpuCommitTrace(
            seq=1,
            bus_read_data=0,
            irq_pending=0,
            cpu_arch_time_enable=True,
            freeze_arch_time=False,
            cpu_hold_only=False,
        ),
        trace,
        "reset_profile.smoke",
    )

    expected = expected_reset_state_for(CPU_BRING_UP_PROFILES)
    assert expected.pc == 0x0100
    assert expected.sp == 0xFFFE
    assert not expected.ime_enabled


@cocotb.test(expect_error=NotImplementedError)
async def test_skipboot_arch_state_compare_scaffold(dut):
    """Keep the missing DUT architectural reset surface explicit and exercised."""
    driver = cpu_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES.reset)
    capture_dut_reset_state(driver)
