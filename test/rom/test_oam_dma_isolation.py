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
from rom_runner import load_manifest_entry, run_dut_to_abi_result
from spec.profiles import ResetProfile


warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")


@cocotb.test()
async def test_oam_dma_isolation_rom_enforces_hram_only_dma_cpu_access(dut):
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)
    entry = load_manifest_entry("OAM_DMA_ISOLATION")
    actual = await run_dut_to_abi_result(
        driver,
        rom_bytes=entry.rom_path.read_bytes(),
        max_mcycles=30000,
        enforce_dma_cpu_restrictions=True,
    )

    assert actual.abi.result == 0x01
    assert actual.abi.signature == bytes.fromhex(
        "010104000400000022e4557700000000444d4149000000000000000000000000"
    )
    assert actual.abi.log == bytes.fromhex("040001777700")
