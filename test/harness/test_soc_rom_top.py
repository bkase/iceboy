# top = sim::soc_rom_top::soc_rom_top
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import ClockCycles


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from fixtures import soc_rom_dut
from spec.profiles import CPU_BRING_UP_PROFILES


def decode_arch_state_abcdehl(dut) -> tuple[int, int, int, int, int, int, int]:
    regs = (int(dut.cpu_core_0.arch_state.value) >> 4) & ((1 << 96) - 1)
    return (
        (regs >> 88) & 0xFF,
        (regs >> 72) & 0xFF,
        (regs >> 64) & 0xFF,
        (regs >> 56) & 0xFF,
        (regs >> 48) & 0xFF,
        (regs >> 40) & 0xFF,
        (regs >> 32) & 0xFF,
    )


@cocotb.test()
async def test_soc_rom_top_exposes_preview_bus_request_before_commit(dut):
    driver = soc_rom_dut(dut)
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
    assert commit.pc == 0x0101
    assert commit.ppu_mode == 1
    assert commit.ppu_ly == 0
    assert (commit.preview_bus_req_kind, commit.preview_bus_req_addr, commit.preview_bus_req_data) == (1, 0x0100, 0x00)

    after_commit = await driver.step_mcycle(bus_read_data=0x00, irq_pending=0)
    assert after_commit.m_ce is False
    assert (after_commit.preview_bus_req_kind, after_commit.preview_bus_req_addr, after_commit.preview_bus_req_data) == (
        1,
        0x0101,
        0x00,
    )


@cocotb.test()
async def test_soc_rom_top_ppu_advances_and_packed_regs_match_arch_state(dut):
    driver = soc_rom_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)

    start = await driver.step_mcycle(bus_read_data=0x44, irq_pending=0x03)
    assert start.t_index == 1
    assert start.ppu_mode == 1
    assert start.ppu_ly == 0
    assert start.ppu_scanout_valid is True
    assert start.ppu_scanout_kind == 1
    assert start.ppu_blank_reason == 3
    assert (start.cpu_a, start.cpu_b, start.cpu_c, start.cpu_d, start.cpu_e, start.cpu_h, start.cpu_l) == decode_arch_state_abcdehl(dut)

    await ClockCycles(dut.clk_i, 90)
    transfer = driver.observe()
    assert transfer.ppu_ly == 0
    assert transfer.ppu_mode == 2
    assert transfer.ppu_scanout_valid is True
    assert transfer.ppu_scanout_y == 0
    assert (transfer.cpu_a, transfer.cpu_b, transfer.cpu_c, transfer.cpu_d, transfer.cpu_e, transfer.cpu_h, transfer.cpu_l) == (
        decode_arch_state_abcdehl(dut)
    )


@cocotb.test()
async def test_soc_rom_top_eventually_emits_pixel_scanout(dut):
    driver = soc_rom_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)

    saw_pixel = False
    for _ in range(600):
        observation = await driver.step_mcycle(bus_read_data=0x00, irq_pending=0)
        if observation.ppu_scanout_valid and observation.ppu_scanout_kind == 0:
            saw_pixel = True
            assert observation.ppu_scanout_y < 144
            break

    assert saw_pixel
