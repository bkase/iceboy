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
from rom_runner import (
    ABI_RESULT_PASS,
    build_manifest,
    load_manifest_entry,
    run_dut_to_abi_result,
    run_oracle_to_terminal,
)
from spec.profiles import ResetProfile


warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")


@cocotb.test()
async def test_loads_basic_rom_matches_pyboy_signature(dut):
    entry = load_manifest_entry("LOADS_BASIC")
    manifest = build_manifest(entry)
    expected_labels, expected_abi = run_oracle_to_terminal(entry, manifest)

    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)

    actual = await run_dut_to_abi_result(
        driver,
        rom_bytes=entry.rom_path.read_bytes(),
        max_mcycles=min(entry.timeout_commits, 20000),
    )

    assert "__pass" in expected_labels[-1], expected_labels
    assert actual.abi.result == ABI_RESULT_PASS, (
        f"DUT ended with ABI result 0x{actual.abi.result:02X} after {actual.cycles} cycles; "
        f"expected terminal labels {expected_labels}"
    )
    assert actual.abi.signature == expected_abi.signature, (
        f"signature mismatch\nexpected={expected_abi.signature.hex()}\nactual={actual.abi.signature.hex()}"
    )
    assert actual.abi.log == expected_abi.log, (
        f"log mismatch\nexpected={expected_abi.log.hex()}\nactual={actual.abi.log.hex()}"
    )
