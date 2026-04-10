# top = sim::soc_rom_top::soc_rom_top
from __future__ import annotations

import os
import sys
from pathlib import Path

import cocotb


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from fixtures import soc_rom_dut
from rom_runner import assert_mealybug_ppu_soc_rom_matches_pyboy
from spec.profiles import CPU_BRING_UP_PROFILES


MEALYBUG_ROM_ROOT = ROOT / "bench" / "external" / "mealybug-tearoom-tests" / "ppu"
MEALYBUG_MAX_MCYCLES = 400_000
def _max_mcycles_for_rom(rom_name: str) -> int:
    override_key = f"ICEBOY_MEALYBUG_MAX_MCYCLES_{rom_name.upper().replace('-', '_').replace('.', '_')}"
    override = os.environ.get(override_key, "").strip()
    if not override:
        return MEALYBUG_MAX_MCYCLES
    return int(override, 10)


async def _run_mealybug_canary(dut, rom_name: str) -> None:
    driver = soc_rom_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)
    # The vendored Wave B PNGs are useful characterization artifacts, but the
    # live canary must follow PyBoy's own rendered-frame output for this subset.
    await assert_mealybug_ppu_soc_rom_matches_pyboy(
        driver,
        rom_path=MEALYBUG_ROM_ROOT / rom_name,
        max_mcycles=_max_mcycles_for_rom(rom_name),
    )


@cocotb.test()
async def test_scx_low_3_bits_mealybug_matches_reference(dut):
    await _run_mealybug_canary(dut, "m3_scx_low_3_bits.gb")
