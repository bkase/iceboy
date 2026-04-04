# top = sim::soc_lockstep_top::soc_lockstep_top
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import ClockCycles


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
    assert final.bus_region == 8
    assert final.bus_owner == 3
    assert final.bus_blocked is False
    assert final.ppu_mode == 1
    assert final.ppu_ly == 0
    assert final.ppu_dot_in_line == 4
    assert final.ppu_semantic_valid is True
    assert final.ppu_semantic_mode == final.ppu_mode
    assert final.ppu_semantic_ly == final.ppu_ly
    assert final.ppu_scanout_valid is True
    assert final.ppu_scanout_kind == 1
    assert final.ppu_scanout_y == 0


@cocotb.test()
async def test_soc_lockstep_top_ppu_advances_through_early_visible_checkpoints(dut):
    driver = soc_lockstep_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)

    start = await driver.step_mcycle()
    assert start.ppu_mode == 1
    assert start.ppu_ly == 0
    assert start.ppu_dot_in_line == 1
    assert start.ppu_scanout_valid is True
    assert start.ppu_scanout_kind == 1
    assert start.ppu_blank_reason == 3

    await ClockCycles(dut.clk_i, 90)
    transfer = driver.observe()
    assert transfer.ppu_ly == 0
    assert transfer.ppu_mode == 2
    assert transfer.ppu_dot_in_line >= 80
    assert transfer.ppu_semantic_valid is True
    assert transfer.ppu_semantic_mode == transfer.ppu_mode

    await ClockCycles(dut.clk_i, 260)
    hblank = driver.observe()
    assert hblank.ppu_ly == 0
    assert hblank.ppu_mode == 3

    await ClockCycles(dut.clk_i, 106)
    next_line = driver.observe()
    assert next_line.ppu_ly == 1
    assert next_line.ppu_mode == 1
    assert next_line.ppu_dot_in_line == 1
    assert next_line.ppu_scanout_valid is True
    assert next_line.ppu_scanout_kind == 1
    assert next_line.ppu_scanout_y == 1

    await ClockCycles(dut.clk_i, 90)
    line1_transfer = driver.observe()
    assert line1_transfer.ppu_ly == 1
    assert line1_transfer.ppu_mode == 2
    assert line1_transfer.ppu_dot_in_line >= 80
    assert line1_transfer.ppu_semantic_valid is True
    assert line1_transfer.ppu_semantic_mode == line1_transfer.ppu_mode
