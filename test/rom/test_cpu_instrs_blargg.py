# top = sim::cpu_test_top::cpu_test_top
from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

import cocotb


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from fixtures import cpu_dut
from rom_runner import classify_blargg_serial_capture, run_dut_to_serial_capture
from spec.profiles import ResetProfile


warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

CPU_INSTRS_ROM = ROOT / "roms" / "cpu_instrs.gb"
CPU_INSTRS_PYBOY_SERIAL = ROOT / "bench" / "artifacts" / "cpu_instrs" / "pyboy_serial.txt"
CPU_INSTRS_MAX_MCYCLES = int(os.environ.get("ICEBOY_CPU_INSTRS_MAX_MCYCLES", "80000000"))


@cocotb.test()
async def test_cpu_instrs_blargg_matches_pyboy_serial_output(dut):
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)

    expected = CPU_INSTRS_PYBOY_SERIAL.read_bytes()
    state = await run_dut_to_serial_capture(
        driver,
        rom_bytes=CPU_INSTRS_ROM.read_bytes(),
        max_mcycles=CPU_INSTRS_MAX_MCYCLES,
        min_capture_bytes=len(expected),
    )
    actual = bytes(state.capture)
    outcome = classify_blargg_serial_capture(state.capture)

    assert outcome == "pass", f"cpu_instrs.gb serial outcome was {outcome}: {actual.decode('ascii', errors='replace')!r}"
    assert actual == expected, (
        "cpu_instrs.gb serial output mismatch\n"
        f"expected={expected.decode('ascii', errors='replace')!r}\n"
        f"actual={actual.decode('ascii', errors='replace')!r}"
    )
