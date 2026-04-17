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


def decode_arch_state_bcdehl(dut) -> tuple[int, int, int, int, int, int]:
    regs = (int(dut.cpu_core_0.arch_state.value) >> 4) & ((1 << 96) - 1)
    return (
        (regs >> 72) & 0xFF,
        (regs >> 64) & 0xFF,
        (regs >> 56) & 0xFF,
        (regs >> 48) & 0xFF,
        (regs >> 40) & 0xFF,
        (regs >> 32) & 0xFF,
    )


async def advance_until(driver, predicate, *, max_cycles: int = 1024):
    last = None
    for _ in range(max_cycles):
        last = await driver.step_mcycle()
        if predicate(last):
            return last
    raise TimeoutError(f"predicate not met within {max_cycles} cycles; last={last!r}")


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

    transfer = await advance_until(driver, lambda obs: obs.ppu_ly == 0 and obs.ppu_mode == 2, max_cycles=128)
    assert transfer.ppu_ly == 0
    assert transfer.ppu_mode == 2
    assert transfer.ppu_dot_in_line >= 80
    assert transfer.ppu_scanout_valid is True
    assert transfer.ppu_scanout_kind == 1
    assert transfer.ppu_scanout_y == 0
    assert transfer.ppu_semantic_valid is True
    assert transfer.ppu_semantic_mode == transfer.ppu_mode


@cocotb.test()
async def test_soc_lockstep_top_packed_cpu_regs_match_arch_state(dut):
    driver = soc_lockstep_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)

    for _ in range(8):
        observation = await driver.step_mcycle(bus_read_data=0x00, irq_pending=0x00)
        assert (
            observation.cpu_b,
            observation.cpu_c,
            observation.cpu_d,
            observation.cpu_e,
            observation.cpu_h,
            observation.cpu_l,
        ) == decode_arch_state_bcdehl(dut)


@cocotb.test()
async def test_soc_lockstep_top_rom_observation_matches_full_view(dut):
    driver = soc_lockstep_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)

    for _ in range(6):
        full = await driver.step_mcycle(bus_read_data=0x31, irq_pending=0x01)
        rom = driver.observe_rom()
        assert rom.ppu_vblank_req_window == full.ppu_vblank_req_window
        assert rom.ppu_stat_req_window == full.ppu_stat_req_window
        assert rom.ppu_mode == full.ppu_mode
        assert rom.ppu_ly == full.ppu_ly
        assert rom.ppu_stat == full.ppu_stat
        assert rom.irq_ack_valid == full.irq_ack_valid
        assert rom.irq_ack_bit == full.irq_ack_bit
        assert rom.pc == full.pc
        assert (rom.cpu_b, rom.cpu_c, rom.cpu_d, rom.cpu_e, rom.cpu_h, rom.cpu_l) == (
            full.cpu_b,
            full.cpu_c,
            full.cpu_d,
            full.cpu_e,
            full.cpu_h,
            full.cpu_l,
        )
        assert (rom.bus_req_kind, rom.bus_req_addr, rom.bus_req_data) == (
            full.bus_req_kind,
            full.bus_req_addr,
            full.bus_req_data,
        )
        assert rom.t_index == full.t_index
        assert rom.m_ce == full.m_ce
        assert (rom.preview_bus_req_kind, rom.preview_bus_req_addr, rom.preview_bus_req_data) == (
            full.preview_bus_req_kind,
            full.preview_bus_req_addr,
            full.preview_bus_req_data,
        )


@cocotb.test()
async def test_soc_lockstep_top_exposes_preview_bus_request_before_commit(dut):
    driver = soc_lockstep_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)

    start = driver.observe()
    assert start.m_ce is False
    assert (start.preview_bus_req_kind, start.preview_bus_req_addr, start.preview_bus_req_data) == (1, 0x0100, 0x00)

    first = await driver.step_mcycle(bus_read_data=0x31, irq_pending=0)
    assert first.m_ce is False
    assert (first.preview_bus_req_kind, first.preview_bus_req_addr, first.preview_bus_req_data) == (1, 0x0100, 0x00)

    second = await driver.step_mcycle(bus_read_data=0x31, irq_pending=0)
    assert second.m_ce is False
    assert (second.preview_bus_req_kind, second.preview_bus_req_addr, second.preview_bus_req_data) == (1, 0x0100, 0x00)

    commit = await driver.step_mcycle(bus_read_data=0x31, irq_pending=0)
    assert commit.m_ce is True
    assert commit.bus_req_kind == 1
    assert commit.bus_req_addr == 0x0100
    assert commit.bus_req_data == 0x00
    assert (commit.preview_bus_req_kind, commit.preview_bus_req_addr, commit.preview_bus_req_data) == (1, 0x0100, 0x00)

    after_commit = await driver.step_mcycle(bus_read_data=0x00, irq_pending=0)
    assert after_commit.m_ce is False
    assert (after_commit.preview_bus_req_kind, after_commit.preview_bus_req_addr, after_commit.preview_bus_req_data) == (1, 0x0101, 0x00)
