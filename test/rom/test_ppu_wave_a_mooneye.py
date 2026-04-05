# top = sim::soc_rom_top::soc_rom_top
import os
import sys
import warnings
from pathlib import Path

import cocotb


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from fixtures import soc_rom_dut
from rom_runner import assert_mooneye_ppu_soc_rom_passes
from spec.profiles import CPU_BRING_UP_PROFILES


warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

MOONEYE_PPU_ROOT = ROOT / "bench" / "external" / "mooneye-test-suite" / "acceptance" / "ppu"
MOONEYE_WAVE_A_MAX_MCYCLES = 250000
MOONEYE_WAVE_A_MAX_MCYCLES_BY_ROM = {
    "lcdon_timing-GS.gb": 600000,
    "lcdon_write_timing-GS.gb": 800000,
}
INCLUDE_WRITE_TIMING = os.environ.get("ICEBOY_PPU_WAVE_A_INCLUDE_WRITE_TIMING", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


async def _run_mooneye_ppu_rom(dut, rom_name: str) -> None:
    driver = soc_rom_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)
    await assert_mooneye_ppu_soc_rom_passes(
        driver,
        rom_path=MOONEYE_PPU_ROOT / rom_name,
        max_mcycles=MOONEYE_WAVE_A_MAX_MCYCLES_BY_ROM.get(rom_name, MOONEYE_WAVE_A_MAX_MCYCLES),
    )


@cocotb.test()
async def test_vblank_stat_intr_gs_mooneye_passes(dut):
    await _run_mooneye_ppu_rom(dut, "vblank_stat_intr-GS.gb")


@cocotb.test()
async def test_stat_lyc_onoff_mooneye_passes(dut):
    await _run_mooneye_ppu_rom(dut, "stat_lyc_onoff.gb")


@cocotb.test()
async def test_stat_irq_blocking_mooneye_passes(dut):
    await _run_mooneye_ppu_rom(dut, "stat_irq_blocking.gb")


@cocotb.test()
async def test_lcdon_timing_gs_mooneye_passes(dut):
    await _run_mooneye_ppu_rom(dut, "lcdon_timing-GS.gb")


@cocotb.test(skip=not INCLUDE_WRITE_TIMING)
async def test_lcdon_write_timing_gs_mooneye_passes(dut):
    await _run_mooneye_ppu_rom(dut, "lcdon_write_timing-GS.gb")
