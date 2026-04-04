from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
HARNESS = ROOT / "test" / "harness"
for entry in [ROOT, HARNESS]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from ppu_driver import PpuHarnessBase, ppu_lockstep_harness, ppu_test_harness


def ppu_test_dut(driver: Any, *, logger: Any | None = None) -> PpuHarnessBase:
    return ppu_test_harness(driver, logger=logger)


def ppu_lockstep_dut(driver: Any, *, logger: Any | None = None) -> PpuHarnessBase:
    return ppu_lockstep_harness(driver, logger=logger)


__all__ = [
    "PpuHarnessBase",
    "ppu_lockstep_dut",
    "ppu_test_dut",
]
