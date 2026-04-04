from __future__ import annotations

import asyncio
import io
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "test" / "harness"
PPU_ROOT = ROOT / "test" / "ppu"
for entry in [HARNESS, ROOT]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from ppu_driver import (
    FRAME_DOTS,
    PPU_MODE_HBLANK,
    PPU_MODE_OAM,
    PPU_MODE_VBLANK,
    PpuHarnessBase,
    PpuRegWrite,
    PpuStepObservation,
    ppu_lockstep_harness,
    ppu_test_harness,
)
from test.harness.logging_std import TestLogger
from test.ppu.conftest import ppu_lockstep_dut, ppu_test_dut


class _FakePpuDriver:
    def __init__(self) -> None:
        self.reset_calls = 0
        self.reg_writes: list[PpuRegWrite] = []
        self.seq = 0
        self.dot = 0
        self.line = 0

    async def reset(self) -> None:
        self.reset_calls += 1
        self.seq = 0
        self.dot = 0
        self.line = 0

    async def step_dot(self, *, reg_write: PpuRegWrite | None = None) -> PpuStepObservation:
        if reg_write is not None:
            self.reg_writes.append(reg_write)
        mode = PPU_MODE_OAM
        if self.line >= 144:
            mode = PPU_MODE_VBLANK
        elif self.dot >= 252:
            mode = PPU_MODE_HBLANK
        obs = PpuStepObservation(
            commit_seq=self.seq + 1,
            dot_in_line=self.dot,
            line_index=self.line,
            phase_kind=mode,
            mode_kind=mode,
            scanout=("pixel", self.line, self.dot) if self.line < 144 and self.dot < 160 else None,
        )
        self.seq += 1
        self.dot += 1
        if self.dot == 456:
            self.dot = 0
            self.line = (self.line + 1) % 154
        return obs

    async def read_reg(self, addr: int) -> int:
        return addr & 0xFF


class PpuTestInfraTest(unittest.TestCase):
    def test_ppu_directory_structure_exists(self) -> None:
        for path in [
            PPU_ROOT / "__init__.py",
            PPU_ROOT / "conftest.py",
            PPU_ROOT / "unit" / "__init__.py",
            PPU_ROOT / "unit" / "test_tile.py",
            PPU_ROOT / "unit" / "test_ppu_modes.py",
            PPU_ROOT / "unit" / "test_stat_irq.py",
            PPU_ROOT / "unit" / "test_window.py",
            PPU_ROOT / "unit" / "test_obj_priority.py",
            PPU_ROOT / "unit" / "test_ppu_invariants.py",
            PPU_ROOT / "lockstep" / "__init__.py",
            PPU_ROOT / "rom" / "__init__.py",
            PPU_ROOT / "backend_diff" / "__init__.py",
            PPU_ROOT / "raster" / "__init__.py",
            PPU_ROOT / "power" / "__init__.py",
            ROOT / "test" / "harness" / "ppu_driver.py",
        ]:
            self.assertTrue(path.exists(), path)

    def test_conftest_exports_named_harness_constructors(self) -> None:
        driver = _FakePpuDriver()
        logger = TestLogger(suite_name="ppu", stream=io.StringIO(), color=False)
        self.assertIsInstance(ppu_test_dut(driver, logger=logger), PpuHarnessBase)
        self.assertIsInstance(ppu_lockstep_dut(driver, logger=logger), PpuHarnessBase)
        self.assertIsInstance(ppu_test_harness(driver, logger=logger), PpuHarnessBase)
        self.assertIsInstance(ppu_lockstep_harness(driver, logger=logger), PpuHarnessBase)

    def test_harness_helpers_drive_fake_driver(self) -> None:
        async def scenario() -> tuple[int, int, int, tuple[object, ...], tuple[object, ...]]:
            logger = TestLogger(suite_name="ppu", stream=io.StringIO(), color=False)
            driver = _FakePpuDriver()
            harness = ppu_test_harness(driver, logger=logger)
            await harness.reset()
            await harness.write_ppu_reg(0xFF40, 0x91)
            line_obs = await harness.advance_to_line(2)
            mode_obs = await harness.advance_to_mode(PPU_MODE_HBLANK)
            frame_obs = await harness.wait_vblank(max_dots=FRAME_DOTS)
            line_capture = await harness.capture_line(3)
            frame_capture = await harness.capture_frame(max_dots=FRAME_DOTS * 2)
            reg_value = await harness.read_ppu_reg(0xFF43)
            return (
                driver.reset_calls,
                reg_value,
                driver.reg_writes[0].addr,
                line_capture,
                frame_capture,
            )

        reset_calls, reg_value, write_addr, line_capture, frame_capture = asyncio.run(scenario())
        self.assertEqual(reset_calls, 1)
        self.assertEqual(reg_value, 0x43)
        self.assertEqual(write_addr, 0xFF40)
        self.assertTrue(line_capture)
        self.assertTrue(frame_capture)


if __name__ == "__main__":
    unittest.main()
