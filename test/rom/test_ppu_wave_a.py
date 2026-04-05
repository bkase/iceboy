# top = sim::cpu_test_top::cpu_test_top
import sys
import warnings
from pathlib import Path

import cocotb


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from fixtures import cpu_dut
from rom_runner import assert_rom_matches_pyboy_signature
from spec.profiles import ResetProfile


warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

PPU_WAVE_A_ROMS = (
    "PPU_OFF_ON_BASIC",
    "LY_LYC_BASIC",
    "STAT_MODE_SEQ",
    "VBLANK_IRQ_BASIC",
    "VRAM_OAM_GATING",
)
PPU_WAVE_A_MAX_MCYCLES = 120000


async def _run_ppu_wave_a_rom(dut, rom_id: str) -> None:
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)
    await assert_rom_matches_pyboy_signature(
        driver,
        rom_id=rom_id,
        max_mcycles=PPU_WAVE_A_MAX_MCYCLES,
    )


@cocotb.test()
async def test_ppu_off_on_basic_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_a_rom(dut, "PPU_OFF_ON_BASIC")


@cocotb.test()
async def test_ly_lyc_basic_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_a_rom(dut, "LY_LYC_BASIC")


@cocotb.test()
async def test_stat_mode_seq_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_a_rom(dut, "STAT_MODE_SEQ")


@cocotb.test()
async def test_vblank_irq_basic_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_a_rom(dut, "VBLANK_IRQ_BASIC")


@cocotb.test()
async def test_vram_oam_gating_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_a_rom(dut, "VRAM_OAM_GATING")
