# top = sim::cpu_test_top::cpu_test_top
import sys
from pathlib import Path

import cocotb


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from event_script_support import predicted_traces_for_schedule, striped_stimulus_schedule
from fixtures import cpu_dut
from spec.profiles import CPU_BRING_UP_PROFILES


async def _run_schedule(driver, *, seed: int, commit_count: int) -> tuple[object, tuple[object, ...]]:
    schedule = striped_stimulus_schedule(seed=seed, timeout_commits=max(commit_count + 8, 32))
    await driver.reset(CPU_BRING_UP_PROFILES.reset)

    traces = []
    for commit_index in range(commit_count):
        traces.append(
            await driver.step_mcycle(
                stimulus=schedule.get(commit_index),
                bus_read_data=0,
                irq_pending=0,
            )
        )
    return schedule, tuple(traces)


@cocotb.test()
async def test_event_script_is_deterministic_for_same_seed(dut):
    """Verify commit-indexed event scripts drive repeatable DUT traces."""
    driver = cpu_dut(dut)
    left_schedule, left_traces = await _run_schedule(driver, seed=7, commit_count=16)
    right_schedule, right_traces = await _run_schedule(driver, seed=7, commit_count=16)

    assert left_schedule == right_schedule
    assert left_traces == right_traces
    assert left_traces == predicted_traces_for_schedule(left_schedule, 16)
    assert all(isinstance(commit_index, int) for commit_index in left_schedule)

    other_schedule, _ = await _run_schedule(driver, seed=8, commit_count=16)
    assert left_schedule != other_schedule
