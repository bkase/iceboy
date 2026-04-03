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


@cocotb.test()
async def test_mem_rwb_rom_matches_pyboy_signature(dut):
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)
    await assert_rom_matches_pyboy_signature(driver, rom_id="MEM_RWB")
