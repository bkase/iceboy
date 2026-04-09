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
from rom_runner import assert_ppu_soc_rom_matches_reference_grayscale
from spec.profiles import CPU_BRING_UP_PROFILES


DMG_ACID2_ROM = ROOT / "bench" / "external" / "dmg-acid2" / "dmg-acid2.gb"
DMG_ACID2_EXPECTED = ROOT / "bench" / "expected" / "suite_owned" / "dmg-acid2" / "reference-dmg.png"
DMG_ACID2_MAX_MCYCLES = 1_800_000


def _max_mcycles() -> int:
    override = os.environ.get("ICEBOY_DMG_ACID2_MAX_MCYCLES", "").strip()
    if not override:
        return DMG_ACID2_MAX_MCYCLES
    return int(override, 10)


@cocotb.test()
async def test_dmg_acid2_matches_reference(dut):
    driver = soc_rom_dut(dut)
    await driver.reset(CPU_BRING_UP_PROFILES)
    await assert_ppu_soc_rom_matches_reference_grayscale(
        driver,
        rom_path=DMG_ACID2_ROM,
        expected_path=DMG_ACID2_EXPECTED,
        max_mcycles=_max_mcycles(),
    )
